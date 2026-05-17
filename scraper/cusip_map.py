"""
Phase 4: CUSIP -> ticker/sector resolution.

Resolution order (cheapest/fastest first):
  1. cusip_map.json cache hit              -- instant, no network
  2. SEC company_tickers.json name match   -- free, one download cached to disk
  3. OpenFIGI API                          -- free (25 req/min), last resort
  4. Mark as UNKNOWN                       -- manually fixable later

After any new resolutions, the map is saved back to disk so future runs
never re-resolve what is already known.
"""

import json
import re
import time
from difflib import SequenceMatcher
from pathlib import Path

import requests

from config import (
    CUSIP_MAP_PATH,
    DATA_DIR,
    SEC_HEADERS,
    SEC_DELAY,
)

# Cached in memory for the lifetime of one run
_sec_ticker_lookup: dict | None = None   # normalized_name -> {ticker, name}
_SEC_TICKERS_CACHE = DATA_DIR / "sec_tickers_cache.json"

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
OPENFIGI_DELAY = 2.5   # 25 req/min -> 1 req / 2.4s to stay safe


# ---------------------------------------------------------------------------
# cusip_map.json I/O
# ---------------------------------------------------------------------------

def load_cusip_map() -> dict:
    """Load the persistent CUSIP map from disk.  Returns {} if not found."""
    if CUSIP_MAP_PATH.exists():
        return json.loads(CUSIP_MAP_PATH.read_text(encoding="utf-8"))
    return {}


def save_cusip_map(cmap: dict) -> None:
    """Persist the CUSIP map to disk, sorted by CUSIP for readability."""
    CUSIP_MAP_PATH.write_text(
        json.dumps(dict(sorted(cmap.items())), indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Name normalisation
# ---------------------------------------------------------------------------

# Common corporate suffixes that add noise to matching
_SUFFIX_RE = re.compile(
    r"\b(INC|CORP|CO|LTD|LLC|LP|PLC|NV|SA|AG|SE|BV|GROUP|HLDGS?|"
    r"HOLDINGS?|INTERNATIONAL|INTL|TECHNOLOGIES|TECHNOLOGY|TECH|"
    r"BANCORP|BANCSHARES|FINANCIAL|SERVICES|SOLUTIONS|SYSTEMS|"
    r"COMMUNICATIONS|PHARMA|PHARMACEUTICALS|THERAPEUTICS)\b\.?",
    re.IGNORECASE,
)


def _normalize(name: str) -> str:
    """Return an upper-case, stripped, suffix-free token string for matching."""
    name = name.upper()
    name = _SUFFIX_RE.sub(" ", name)
    name = re.sub(r"[^A-Z0-9\s]", " ", name)   # drop punctuation
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# ---------------------------------------------------------------------------
# SEC company_tickers.json  (downloaded once, cached to disk)
# ---------------------------------------------------------------------------

def _load_sec_tickers() -> dict:
    """
    Return a dict: normalized_name -> {"ticker": str, "name": str}.

    Downloads from SEC once per session; on-disk cache avoids re-downloading
    across separate runs.
    """
    global _sec_ticker_lookup
    if _sec_ticker_lookup is not None:
        return _sec_ticker_lookup

    # Use on-disk cache if present
    if _SEC_TICKERS_CACHE.exists():
        raw = json.loads(_SEC_TICKERS_CACHE.read_text(encoding="utf-8"))
    else:
        print("  Downloading SEC company_tickers.json (once) ...")
        time.sleep(SEC_DELAY)
        resp = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers=SEC_HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()
        _SEC_TICKERS_CACHE.write_text(
            json.dumps(raw, indent=2), encoding="utf-8"
        )
        print(f"  Cached {len(raw):,} SEC tickers to disk.")

    lookup: dict[str, dict] = {}
    for entry in raw.values():
        ticker = entry.get("ticker", "").upper()
        title  = entry.get("title", "")
        if not ticker or not title:
            continue
        key = _normalize(title)
        if key:
            lookup[key] = {"ticker": ticker, "name": title}

    _sec_ticker_lookup = lookup
    return lookup


# ---------------------------------------------------------------------------
# Single-CUSIP resolution
# ---------------------------------------------------------------------------

def _match_by_name(raw_name: str, sec_lookup: dict) -> dict | None:
    """
    Try to find a SEC ticker entry whose company name matches *raw_name*.

    Returns {"ticker": ..., "name": ...} or None.
    """
    query = _normalize(raw_name)
    if not query:
        return None

    # 1. Exact match
    if query in sec_lookup:
        return sec_lookup[query]

    # 2. One is a prefix / substring of the other
    for key, val in sec_lookup.items():
        if key.startswith(query) or query.startswith(key):
            if len(query) >= 4 and len(key) >= 4:   # avoid false positives on short names
                return val

    # 3. Best fuzzy match above threshold
    best_ratio = 0.0
    best_val   = None
    for key, val in sec_lookup.items():
        r = _similarity(query, key)
        if r > best_ratio:
            best_ratio = r
            best_val   = val

    if best_ratio >= 0.72:
        return best_val

    return None


def resolve_cusip(cusip: str, name: str, cmap: dict, sec_lookup: dict) -> dict:
    """
    Return the map entry for *cusip*, resolving it if not yet cached.

    Mutates *cmap* in-place so subsequent calls are instant cache hits.
    Entry format: {"ticker": str|"UNKNOWN", "name": str, "sector": str|null}
    """
    if cusip in cmap:
        return cmap[cusip]

    match = _match_by_name(name, sec_lookup)
    if match:
        entry = {"ticker": match["ticker"], "name": match["name"], "sector": None}
    else:
        entry = {"ticker": "UNKNOWN", "name": name, "sector": None}

    cmap[cusip] = entry
    return entry


# ---------------------------------------------------------------------------
# Batch OpenFIGI fallback
# ---------------------------------------------------------------------------

def resolve_unknown_via_openfigi(cmap: dict) -> int:
    """
    For every CUSIP currently marked UNKNOWN in *cmap*, try the OpenFIGI API.
    Mutates *cmap* in-place and returns the number of newly resolved entries.

    Call this after the main enrichment pass if you want extra coverage.
    Rate limit: max 25 req/min -> we use a 2.5s delay between requests.
    """
    unknowns = [c for c, v in cmap.items() if v.get("ticker") == "UNKNOWN"]
    if not unknowns:
        return 0

    print(f"  OpenFIGI: resolving {len(unknowns)} unknown CUSIPs ...")
    resolved = 0

    for cusip in unknowns:
        time.sleep(OPENFIGI_DELAY)
        try:
            resp = requests.post(
                OPENFIGI_URL,
                json=[{"idType": "ID_CUSIP", "idValue": cusip}],
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            if resp.status_code == 429:
                print("  OpenFIGI rate limit hit -- stopping early.")
                break
            resp.raise_for_status()
            data = resp.json()
            if data and data[0].get("data"):
                item   = data[0]["data"][0]
                ticker = item.get("ticker", "UNKNOWN")
                name   = item.get("name", cmap[cusip]["name"])
                sector = item.get("exchCode")   # rough proxy for now
                if ticker and ticker != "UNKNOWN":
                    cmap[cusip] = {"ticker": ticker, "name": name, "sector": sector}
                    resolved += 1
                    print(f"    {cusip} -> {ticker} ({name})")
        except Exception as exc:
            print(f"    OpenFIGI error for {cusip}: {exc}")

    return resolved


# ---------------------------------------------------------------------------
# Enrich a holdings list  (main entry point)
# ---------------------------------------------------------------------------

def enrich_holdings(holdings: list[dict]) -> list[dict]:
    """
    For each holding, fill in "ticker" and "sector" using the CUSIP map.
    Saves any newly discovered mappings back to disk.

    Modifies *holdings* in-place AND returns them for convenience.
    """
    cmap       = load_cusip_map()
    sec_lookup = _load_sec_tickers()
    new_found  = 0

    for h in holdings:
        cusip = h.get("cusip", "")
        name  = h.get("name", "")
        if not cusip:
            continue

        was_unknown = cusip not in cmap
        entry = resolve_cusip(cusip, name, cmap, sec_lookup)

        h["ticker"] = entry["ticker"]
        h["sector"] = entry["sector"]

        if was_unknown:
            new_found += 1
            status = "OK" if entry["ticker"] != "UNKNOWN" else "??"
            print(f"    [{status}] {cusip}  {name:<40} -> {entry['ticker']}")

    if new_found:
        save_cusip_map(cmap)
        print(f"  cusip_map.json updated ({new_found} new entries).")

    return holdings


# ---------------------------------------------------------------------------
# Update on-disk quarter JSON with enriched ticker data
# ---------------------------------------------------------------------------

def enrich_quarter_file(investor_id: str, quarter: str) -> bool:
    """
    Load the quarter JSON, enrich holdings with tickers, and resave.
    Returns True if the file was updated (any new tickers found).
    """
    from config import HOLDINGS_DIR

    path = HOLDINGS_DIR / investor_id / f"{quarter}.json"
    if not path.exists():
        return False

    data = json.loads(path.read_text(encoding="utf-8"))
    before = [h.get("ticker") for h in data["holdings"]]

    enrich_holdings(data["holdings"])

    after = [h.get("ticker") for h in data["holdings"]]
    if before == after:
        return False

    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from parse import load_quarter

    print("=== Smoke test: enrich Burry Q3 2025 ===")
    data = load_quarter("burry", "2025-Q3")
    if not data:
        print("Run parse.py first to generate the quarter file.")
    else:
        holdings = data["holdings"]
        print(f"Holdings before enrichment: {[h['ticker'] for h in holdings]}")
        enrich_holdings(holdings)
        print(f"\nAfter enrichment:")
        for h in holdings:
            pc = f" [{h['put_call']}]" if h.get("put_call") else ""
            print(f"  {h['ticker']:<8} {h['name']:<40} {h['cusip']}{pc}")

        print("\ncusip_map.json contents:")
        cmap = load_cusip_map()
        for cusip, entry in cmap.items():
            print(f"  {cusip}  {entry['ticker']:<8} {entry['name']}")
