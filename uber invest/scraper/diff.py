"""
Phase 5: Quarter-over-quarter diff engine.

Compares two consecutive 13F snapshots for the same investor and produces
changelog entries describing every position change.

Composite key: (cusip, put_call) -- so a PUT and a CALL on the same underlying
are treated as separate, independently tracked positions.

Changelog entries are saved per-investor to data/changelog/{investor_id}.json
and the combined across all investors is used by export.py.
"""

import json
from pathlib import Path

from config import DATA_DIR, HOLDINGS_DIR
from parse import load_quarter, list_quarters

CHANGELOG_DIR = DATA_DIR / "changelog"

# Actions
NEW       = "NEW"
INCREASED = "INCREASED"
REDUCED   = "REDUCED"
UNCHANGED = "UNCHANGED"
EXITED    = "EXITED"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pos_key(holding: dict) -> tuple:
    """
    Composite key for a position: (cusip, normalised_put_call).
    Keeps PUT and CALL legs on the same underlying as distinct positions.
    """
    pc = (holding.get("put_call") or "").upper()
    return (holding["cusip"], pc)


def _pct_change(current: int | float, previous: int | float) -> float | None:
    """Percentage change, None if previous is 0."""
    if not previous:
        return None
    return round(((current - previous) / previous) * 100, 1)


def _best_name(holding: dict) -> str:
    """Return ticker if resolved, else the raw name from the filing."""
    ticker = holding.get("ticker")
    if ticker and ticker != "UNKNOWN":
        return ticker
    return holding.get("name", "")


# ---------------------------------------------------------------------------
# Core diff
# ---------------------------------------------------------------------------

def diff_quarters(
    prev: dict | None,
    curr: dict,
    investor: dict,
) -> list[dict]:
    """
    Compare *prev* (previous quarter snapshot) against *curr* (current quarter).

    If *prev* is None every position is NEW (first quarter we have on file).

    *investor* must have keys: id, name, fund, avatar.

    Returns a list of changelog entry dicts.
    """
    investor_id   = investor["id"]
    investor_name = investor["name"]
    fund          = investor.get("fund", "")
    avatar        = investor.get("avatar", investor_name[:2].upper())
    quarter       = curr["quarter"]
    filing_date   = curr["filing_date"]

    # Build lookup dicts keyed by (cusip, put_call)
    prev_map: dict[tuple, dict] = {}
    if prev:
        for h in prev.get("holdings", []):
            prev_map[_pos_key(h)] = h

    curr_map: dict[tuple, dict] = {}
    for h in curr.get("holdings", []):
        curr_map[_pos_key(h)] = h

    entries: list[dict] = []

    # --- Positions in current quarter ---
    for key, h in curr_map.items():
        ticker     = h.get("ticker") or "UNKNOWN"
        stock_name = h.get("name", "")
        cusip      = h["cusip"]
        put_call   = (h.get("put_call") or "").upper() or None
        cur_shares = h.get("shares", 0)
        cur_value  = h.get("value", 0)

        if key not in prev_map:
            action        = NEW
            prev_shares   = 0
            prev_value    = 0
            change_pct    = None
        else:
            p           = prev_map[key]
            prev_shares = p.get("shares", 0)
            prev_value  = p.get("value", 0)
            if cur_shares > prev_shares:
                action     = INCREASED
                change_pct = _pct_change(cur_shares, prev_shares)
            elif cur_shares < prev_shares:
                action     = REDUCED
                change_pct = _pct_change(cur_shares, prev_shares)
            else:
                action     = UNCHANGED
                change_pct = 0.0

        entries.append({
            "investor_id":        investor_id,
            "investor_name":      investor_name,
            "fund":               fund,
            "avatar":             avatar,
            "quarter":            quarter,
            "ticker":             ticker,
            "cusip":              cusip,
            "stock_name":         stock_name,
            "action":             action,
            "current_shares":     cur_shares,
            "previous_shares":    prev_shares,
            "current_value":      cur_value,
            "previous_value":     prev_value,
            "change_shares_pct":  change_pct,
            "put_call":           put_call,
            "filing_date":        filing_date,
        })

    # --- Positions that were in previous quarter but gone now ---
    for key, p in prev_map.items():
        if key not in curr_map:
            ticker     = p.get("ticker") or "UNKNOWN"
            stock_name = p.get("name", "")
            put_call   = (p.get("put_call") or "").upper() or None
            entries.append({
                "investor_id":        investor_id,
                "investor_name":      investor_name,
                "fund":               fund,
                "avatar":             avatar,
                "quarter":            quarter,
                "ticker":             ticker,
                "cusip":              p["cusip"],
                "stock_name":         stock_name,
                "action":             EXITED,
                "current_shares":     0,
                "previous_shares":    p.get("shares", 0),
                "current_value":      0,
                "previous_value":     p.get("value", 0),
                "change_shares_pct":  -100.0,
                "put_call":           put_call,
                "filing_date":        filing_date,
            })

    return entries


# ---------------------------------------------------------------------------
# All quarters for one investor
# ---------------------------------------------------------------------------

def diff_all_quarters(investor: dict) -> list[dict]:
    """
    Run diffs across every saved quarter for *investor*, oldest to newest.

    For the very first quarter we have, all positions are flagged as NEW
    (we have no prior data to compare against).

    Returns the full changelog list for this investor across all quarters.
    """
    investor_id = investor["id"]
    quarters    = list_quarters(investor_id)

    if not quarters:
        return []

    all_entries: list[dict] = []
    prev_data: dict | None  = None

    for quarter in quarters:
        curr_data = load_quarter(investor_id, quarter)
        if curr_data is None:
            continue
        entries   = diff_quarters(prev_data, curr_data, investor)
        all_entries.extend(entries)
        prev_data = curr_data

    return all_entries


# ---------------------------------------------------------------------------
# Persist per-investor changelog
# ---------------------------------------------------------------------------

def save_investor_changelog(investor_id: str, entries: list[dict]) -> Path:
    """Save all changelog entries for one investor to data/changelog/{id}.json."""
    CHANGELOG_DIR.mkdir(parents=True, exist_ok=True)
    path = CHANGELOG_DIR / f"{investor_id}.json"
    path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return path


def load_investor_changelog(investor_id: str) -> list[dict]:
    """Load saved changelog for one investor, or [] if not yet generated."""
    path = CHANGELOG_DIR / f"{investor_id}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def load_all_changelogs(investor_ids: list[str]) -> list[dict]:
    """
    Load and merge changelogs for every investor.
    Returns entries sorted by filing_date descending (newest first).
    """
    combined: list[dict] = []
    for iid in investor_ids:
        combined.extend(load_investor_changelog(iid))
    combined.sort(key=lambda e: e.get("filing_date", ""), reverse=True)
    return combined


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json as _json

    investor = {
        "id":     "burry",
        "name":   "Michael Burry",
        "fund":   "Scion Asset Management",
        "avatar": "MB",
    }

    print("=== Smoke test: diff Burry Q2 -> Q3 2025 ===\n")

    entries = diff_all_quarters(investor)
    save_investor_changelog("burry", entries)

    # Summarise by action
    from collections import Counter
    action_counts = Counter(e["action"] for e in entries)
    print(f"Total changelog entries across all quarters: {len(entries)}")
    for action, count in sorted(action_counts.items()):
        print(f"  {action:<10} {count}")

    print("\nQ3 2025 changes only:")
    q3 = [e for e in entries if e["quarter"] == "2025-Q3"]
    for e in sorted(q3, key=lambda x: x["action"]):
        pc  = f" [{e['put_call']}]" if e.get("put_call") else ""
        pct = f"  ({e['change_shares_pct']:+.1f}%)" if e.get("change_shares_pct") not in (None, 0.0) else ""
        print(
            f"  {e['action']:<10} {e['ticker']:<8} {e['stock_name']:<35}"
            f"  cur={e['current_shares']:>10,}sh  prev={e['previous_shares']:>10,}sh{pct}{pc}"
        )

    print(f"\nSaved to data/changelog/burry.json")
