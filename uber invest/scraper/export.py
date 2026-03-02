"""
Phase 6: Frontend JSON export.

Generates four static JSON files that the React app reads directly:

  data/frontend/changelog.json         -- Feed tab
  data/frontend/conviction.json        -- Conviction tab
  data/frontend/investors_summary.json -- Investors tab
  data/frontend/latest_holdings.json   -- Investor drill-down
"""

import json
from collections import defaultdict
from pathlib import Path

from config import FRONTEND_DIR, HOLDINGS_DIR
from diff import (
    EXITED, INCREASED, NEW, REDUCED, UNCHANGED,
    load_all_changelogs, load_investor_changelog,
)
from parse import list_quarters, load_quarter


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_shares(n: int | float) -> str:
    """3.5M, 250.0K, 48.3K ..."""
    n = abs(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(int(n))


def _fmt_value(v: int | float) -> str:
    """$1.4B, $912M, $61.5M, $13M ..."""
    v = abs(v)
    if v >= 1_000_000_000:
        return f"${v / 1_000_000_000:.1f}B"
    if v >= 1_000_000:
        m = v / 1_000_000
        return f"${m:.1f}M" if m < 100 else f"${m:.0f}M"
    if v >= 1_000:
        return f"${v / 1_000:.0f}K"
    return f"${v:.0f}"


def _detail(entry: dict) -> str:
    """Human-readable summary string for a changelog entry."""
    action  = entry["action"]
    shares  = entry["current_shares"]
    pshares = entry["previous_shares"]
    val     = entry["current_value"]
    pval    = entry["previous_value"]
    pct     = entry.get("change_shares_pct")

    if action == NEW:
        return f"New position -- {_fmt_shares(shares)} shares ({_fmt_value(val)})"

    if action == INCREASED:
        delta = shares - pshares
        pct_s = f"+{pct:.1f}%" if pct is not None else ""
        return (
            f"Increased {pct_s} -- {_fmt_shares(shares)} shares "
            f"(+{_fmt_shares(delta)})"
        )

    if action == REDUCED:
        delta = pshares - shares
        pct_s = f"{pct:.1f}%" if pct is not None else ""
        return (
            f"Reduced {pct_s} -- {_fmt_shares(shares)} shares "
            f"(-{_fmt_shares(delta)})"
        )

    if action == EXITED:
        return f"Exited position -- was {_fmt_shares(pshares)} shares ({_fmt_value(pval)})"

    # UNCHANGED
    return f"Held {_fmt_shares(shares)} shares (unchanged)"


_ACTION_TYPE = {
    NEW:       "new",
    INCREASED: "buy",
    REDUCED:   "sell",
    EXITED:    "sell",
    UNCHANGED: "hold",
}


# ---------------------------------------------------------------------------
# 1. changelog.json
# ---------------------------------------------------------------------------

_FEED_MAX_ENTRIES = 5000        # hard cap on total feed size
_FEED_MIN_VALUE   = 1_000_000   # skip positions smaller than $1M (noise filter)
_FEED_MAX_QUARTERS_PER_INV = 4  # only include last N quarters per investor

def generate_changelog(investors: list[dict]) -> list[dict]:
    """
    Merge changelogs for all investors and return the feed list.
    Sorted by filing_date descending; UNCHANGED entries are excluded.

    Caps:
    - Only the most recent 4 quarters per investor (avoids deep history noise)
    - Positions with value < $1M are excluded (removes tiny option legs)
    - Hard cap of 5000 total entries (sorted by date then value)
    """
    ids     = [inv["id"] for inv in investors]
    entries = load_all_changelogs(ids)

    # Determine per-investor recent quarters cutoff
    inv_cutoff: dict[str, set] = {}
    for inv in investors:
        qts = list_quarters(inv["id"])
        inv_cutoff[inv["id"]] = set(qts[-_FEED_MAX_QUARTERS_PER_INV:])

    feed = []
    for e in entries:
        if e["action"] == UNCHANGED:
            continue

        # Skip if this quarter is outside the recency window for this investor
        allowed_quarters = inv_cutoff.get(e["investor_id"])
        if allowed_quarters is not None and e["quarter"] not in allowed_quarters:
            continue

        val = e["current_value"] or e["previous_value"]
        if val < _FEED_MIN_VALUE:
            continue

        feed.append({
            "time":        e["filing_date"],
            "investor":    e["investor_name"],
            "investor_id": e["investor_id"],
            "avatar":      e.get("avatar", e["investor_name"][:2].upper()),
            "action":      e["action"],
            "ticker":      e["ticker"],
            "stock_name":  e["stock_name"],
            "detail":      _detail(e),
            "type":        _ACTION_TYPE.get(e["action"], "hold"),
            "put_call":    e.get("put_call"),
            "value":       val,
            "quarter":     e["quarter"],
        })

    # Sort: most recent date first, then largest value first within same date
    feed.sort(key=lambda x: (x["time"], x["value"]), reverse=True)

    return feed[:_FEED_MAX_ENTRIES]


# ---------------------------------------------------------------------------
# 2. conviction.json
# ---------------------------------------------------------------------------

def generate_conviction(investors: list[dict]) -> list[dict]:
    """
    Cross-investor conviction map for the LATEST quarter of each investor.

    Groups by ticker (regardless of put_call) so the view shows "who owns X"
    at the company level. Sorted by holder_count descending.
    """
    # Map investor_id -> set of (quarter, action) entries for latest quarter
    latest_actions: dict[str, dict[str, str]] = {}   # investor_id -> {ticker: action}
    for inv in investors:
        qts = list_quarters(inv["id"])
        if not qts:
            continue
        latest_q = qts[-1]
        cl = load_investor_changelog(inv["id"])
        latest_actions[inv["id"]] = {
            e["ticker"]: e["action"]
            for e in cl
            if e["quarter"] == latest_q and e["action"] != EXITED
        }

    # Aggregate across investors
    # ticker -> { holders, total_value, name, sector, any_new }
    agg: dict[str, dict] = {}

    for inv in investors:
        qts = list_quarters(inv["id"])
        if not qts:
            continue
        data = load_quarter(inv["id"], qts[-1])
        if not data:
            continue

        total_val = data["total_value"] or 1  # avoid div-by-zero
        inv_actions = latest_actions.get(inv["id"], {})

        for h in data["holdings"]:
            ticker = h.get("ticker") or "UNKNOWN"
            if ticker == "UNKNOWN":
                continue

            if ticker not in agg:
                agg[ticker] = {
                    "ticker":       ticker,
                    "name":         h.get("name", ""),
                    "sector":       h.get("sector"),
                    "holders":      [],
                    "holder_count": 0,
                    "total_value":  0,
                    "any_new":      False,
                }

            if inv["name"] not in agg[ticker]["holders"]:
                agg[ticker]["holders"].append(inv["name"])
                agg[ticker]["holder_count"] += 1

            agg[ticker]["total_value"] += h.get("value", 0)

            if inv_actions.get(ticker) == NEW:
                agg[ticker]["any_new"] = True

    result = sorted(agg.values(), key=lambda x: x["holder_count"], reverse=True)
    return result


# ---------------------------------------------------------------------------
# 3. investors_summary.json
# ---------------------------------------------------------------------------

def generate_investors_summary(investors: list[dict]) -> list[dict]:
    """
    One record per investor with their latest-quarter summary and top holdings.
    Investors with no data on disk are included with null fields (not silently
    dropped) so the frontend can show a "pending" state.
    """
    summary = []

    for inv in investors:
        qts = list_quarters(inv["id"])

        if not qts:
            summary.append({
                "id":             inv["id"],
                "name":           inv["name"],
                "fund":           inv.get("fund", ""),
                "avatar":         inv.get("avatar", ""),
                "cik":            inv["cik"],
                "latest_quarter": None,
                "total_value":    None,
                "num_holdings":   None,
                "num_new":        None,
                "top_holdings":   [],
            })
            continue

        latest_q = qts[-1]
        data     = load_quarter(inv["id"], latest_q)
        cl       = load_investor_changelog(inv["id"])

        # Count NEW positions in the latest quarter
        num_new = sum(
            1 for e in cl
            if e["quarter"] == latest_q and e["action"] == NEW
        )

        # Top 5 holdings by value
        holdings_sorted = sorted(
            data["holdings"], key=lambda h: h.get("value", 0), reverse=True
        )
        total_val = data["total_value"] or 1
        top = []
        for h in holdings_sorted[:5]:
            top.append({
                "ticker":   h.get("ticker") or h.get("name", ""),
                "value":    h.get("value", 0),
                "weight":   round(h.get("value", 0) / total_val * 100, 1),
                "put_call": h.get("put_call"),
            })

        summary.append({
            "id":             inv["id"],
            "name":           inv["name"],
            "fund":           inv.get("fund", ""),
            "avatar":         inv.get("avatar", ""),
            "cik":            inv["cik"],
            "latest_quarter": latest_q,
            "total_value":    data["total_value"],
            "num_holdings":   data["num_holdings"],
            "num_new":        num_new,
            "top_holdings":   top,
        })

    return summary


# ---------------------------------------------------------------------------
# 4. latest_holdings.json
# ---------------------------------------------------------------------------

def generate_latest_holdings(investors: list[dict]) -> dict:
    """
    Detailed holdings for every investor's latest quarter, keyed by investor_id.
    Includes weight%, is_new, and change_pct sourced from the diff changelog.
    """
    result: dict[str, dict] = {}

    for inv in investors:
        qts = list_quarters(inv["id"])
        if not qts:
            continue

        latest_q = qts[-1]
        data     = load_quarter(inv["id"], latest_q)
        if not data:
            continue

        cl = load_investor_changelog(inv["id"])

        # Build a lookup: (cusip, put_call) -> changelog entry for latest quarter
        diff_lookup: dict[tuple, dict] = {}
        for e in cl:
            if e["quarter"] == latest_q:
                key = (e["cusip"], (e.get("put_call") or "").upper())
                diff_lookup[key] = e

        total_val = data["total_value"] or 1
        holdings_out = []

        for h in sorted(data["holdings"], key=lambda x: x.get("value", 0), reverse=True):
            pc  = (h.get("put_call") or "").upper()
            key = (h["cusip"], pc)
            de  = diff_lookup.get(key, {})

            holdings_out.append({
                "ticker":     h.get("ticker") or h.get("name", ""),
                "name":       h.get("name", ""),
                "cusip":      h["cusip"],
                "shares":     h.get("shares", 0),
                "value":      h.get("value", 0),
                "weight":     round(h.get("value", 0) / total_val * 100, 1),
                "change_pct": de.get("change_shares_pct"),
                "is_new":     de.get("action") == NEW,
                "put_call":   h.get("put_call"),
                "sector":     h.get("sector"),
            })

        result[inv["id"]] = {
            "quarter":      latest_q,
            "total_value":  data["total_value"],
            "num_holdings": data["num_holdings"],   # true count (before cap)
            "holdings":     holdings_out[:200],     # cap at 200 for frontend perf
        }

    return result


# ---------------------------------------------------------------------------
# Master export
# ---------------------------------------------------------------------------

def export_all(investors: list[dict]) -> None:
    """Generate and write all four frontend JSON files."""
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating changelog.json ...")
    changelog = generate_changelog(investors)
    _write(FRONTEND_DIR / "changelog.json", changelog)
    print(f"  {len(changelog)} feed entries")

    print("Generating conviction.json ...")
    conviction = generate_conviction(investors)
    _write(FRONTEND_DIR / "conviction.json", conviction)
    print(f"  {len(conviction)} tickers tracked")

    print("Generating investors_summary.json ...")
    summary = generate_investors_summary(investors)
    _write(FRONTEND_DIR / "investors_summary.json", summary)
    print(f"  {len(summary)} investors")

    print("Generating latest_holdings.json ...")
    holdings = generate_latest_holdings(investors)
    _write(FRONTEND_DIR / "latest_holdings.json", holdings)
    print(f"  {len(holdings)} investors with holdings data")

    print("Export complete.")


def _write(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))

    # Load investors list
    from config import INVESTORS_PATH
    investors = json.loads(INVESTORS_PATH.read_text(encoding="utf-8"))["investors"]

    export_all(investors)

    # Spot-check each file
    print("\n--- changelog.json (first 3 entries) ---")
    cl = json.loads((FRONTEND_DIR / "changelog.json").read_text(encoding="utf-8"))
    for e in cl[:3]:
        print(f"  [{e['quarter']}] {e['investor']:<20} {e['action']:<10} {e['ticker']:<8} {e['detail']}")

    print("\n--- conviction.json (top 5) ---")
    cv = json.loads((FRONTEND_DIR / "conviction.json").read_text(encoding="utf-8"))
    for e in cv[:5]:
        print(f"  {e['ticker']:<8} holders={e['holder_count']}  {_fmt_value(e['total_value']):<8}  any_new={e['any_new']}")

    print("\n--- investors_summary.json (Burry) ---")
    summ = json.loads((FRONTEND_DIR / "investors_summary.json").read_text(encoding="utf-8"))
    burry = next(s for s in summ if s["id"] == "burry")
    print(f"  latest_quarter: {burry['latest_quarter']}")
    print(f"  total_value:    {_fmt_value(burry['total_value'])}")
    print(f"  num_holdings:   {burry['num_holdings']}")
    print(f"  num_new:        {burry['num_new']}")
    print(f"  top_holdings:   {burry['top_holdings'][:2]}")

    print("\n--- latest_holdings.json (Burry, top 3) ---")
    lh = json.loads((FRONTEND_DIR / "latest_holdings.json").read_text(encoding="utf-8"))
    for h in lh["burry"]["holdings"][:3]:
        print(
            f"  {h['ticker']:<8} {h['weight']:>5.1f}%  "
            f"is_new={h['is_new']}  change_pct={h['change_pct']}"
        )
