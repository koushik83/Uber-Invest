"""
Phase 8: Orchestrator -- ties fetch -> parse -> cusip -> diff -> export together.

Usage
-----
  python main.py                       # incremental: only fetch new quarters
  python main.py --backfill            # fetch up to BACKFILL_QUARTERS per investor
  python main.py --investor burry      # process one investor only
  python main.py --export-only         # skip fetching, just re-run export step
  python main.py --openfigi            # run OpenFIGI pass after enrichment

The fetch layer already skips quarters that exist on disk, so --backfill and
the default incremental mode share the same code path -- the difference is only
how many quarters back we ask the submissions API to look.
"""

import argparse
import json
import sys
import traceback
from pathlib import Path

from config import BACKFILL_QUARTERS, HOLDINGS_DIR, INVESTORS_PATH
from cusip_map import enrich_holdings, load_cusip_map, resolve_unknown_via_openfigi, save_cusip_map
from diff import diff_all_quarters, save_investor_changelog
from export import export_all
from fetch import fetch_investor_filings
from parse import parse_infotable_xml, save_quarter


# ---------------------------------------------------------------------------
# Per-investor pipeline
# ---------------------------------------------------------------------------

def process_investor(investor: dict, num_quarters: int) -> bool:
    """
    Full pipeline for one investor: fetch -> parse -> enrich -> save -> diff.

    Returns True if any new data was processed.
    """
    investor_id = investor["id"]
    name        = investor["name"]
    print(f"\n[{investor_id}] {name}")

    # ---- Fetch (skips quarters already on disk) --------------------------
    try:
        new_filings = fetch_investor_filings(investor, num_quarters)
    except Exception as exc:
        print(f"  ERROR fetching {name}: {exc}")
        traceback.print_exc()
        return False

    if not new_filings:
        print(f"  No new filings to process.")
    else:
        # ---- Parse + enrich + save each new filing -----------------------
        for filing in new_filings:
            quarter = filing["quarter"]
            try:
                holdings = parse_infotable_xml(filing["xml"])
                enrich_holdings(holdings)
                save_quarter(investor, filing, holdings)
            except Exception as exc:
                print(f"  ERROR processing {investor_id}/{quarter}: {exc}")
                traceback.print_exc()
                continue

    # ---- Diff all quarters (recompute from scratch each run) -------------
    try:
        entries = diff_all_quarters(investor)
        save_investor_changelog(investor_id, entries)
        n_new = sum(1 for e in entries if e["action"] == "NEW")
        n_changed = sum(1 for e in entries if e["action"] in ("INCREASED", "REDUCED", "EXITED"))
        print(f"  Changelog: {len(entries)} entries  ({n_new} new, {n_changed} changes)")
    except Exception as exc:
        print(f"  ERROR diffing {investor_id}: {exc}")
        traceback.print_exc()

    return bool(new_filings)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="13F Superinvestor Tracker scraper")
    parser.add_argument(
        "--backfill",
        action="store_true",
        help=f"Fetch up to {BACKFILL_QUARTERS} quarters of history per investor",
    )
    parser.add_argument(
        "--investor",
        metavar="ID",
        help="Process only this investor id (e.g. burry, buffett)",
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Skip fetching; just regenerate frontend JSON files from existing data",
    )
    parser.add_argument(
        "--openfigi",
        action="store_true",
        help="After enrichment, run an OpenFIGI pass to resolve any UNKNOWN tickers",
    )
    args = parser.parse_args()

    # Load investor list
    investors: list[dict] = json.loads(INVESTORS_PATH.read_text(encoding="utf-8"))["investors"]

    if args.investor:
        investors = [i for i in investors if i["id"] == args.investor]
        if not investors:
            print(f"Unknown investor id: {args.investor}")
            sys.exit(1)

    num_quarters = BACKFILL_QUARTERS if args.backfill else 2  # incremental: only look at 2 most recent

    # ---- Per-investor pipeline -------------------------------------------
    if not args.export_only:
        total   = len(investors)
        updated = 0

        for idx, investor in enumerate(investors, 1):
            print(f"\n{'='*60}")
            print(f"  {idx}/{total}  {investor['name']}  (CIK {investor['cik']})")
            print(f"{'='*60}")
            had_new = process_investor(investor, num_quarters)
            if had_new:
                updated += 1

        print(f"\n\nDone. {updated}/{total} investors had new data.")

    # ---- Optional OpenFIGI pass -----------------------------------------
    if args.openfigi:
        print("\nRunning OpenFIGI resolution pass for UNKNOWN tickers ...")
        cmap = load_cusip_map()
        resolved = resolve_unknown_via_openfigi(cmap)
        if resolved:
            save_cusip_map(cmap)
            print(f"Resolved {resolved} additional tickers via OpenFIGI.")

    # ---- Reload full investor list for export (even if --investor was set) --
    all_investors = json.loads(INVESTORS_PATH.read_text(encoding="utf-8"))["investors"]

    # ---- Export frontend JSON files -------------------------------------
    print("\n\nGenerating frontend JSON files ...")
    export_all(all_investors)
    print("All done.")


if __name__ == "__main__":
    main()
