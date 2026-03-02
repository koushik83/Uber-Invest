"""
Phase 2: SEC EDGAR fetcher.

All requests go through sec_get(), which enforces the 0.15s rate limit and
hard-exits on a 403 to protect the IP.  Nothing in this module ever
re-downloads a filing that already exists on disk.
"""

import sys
import time
import json
import re
from pathlib import Path

import requests

from config import (
    SEC_HEADERS,
    SEC_DELAY,
    HOLDINGS_DIR,
    BACKFILL_QUARTERS,
)

# ---------------------------------------------------------------------------
# Low-level HTTP
# ---------------------------------------------------------------------------

def sec_get(url: str, retries: int = 2) -> requests.Response:
    """
    Rate-limited GET to SEC EDGAR.
    - Hard-exits on 403 (IP-level block -- do not retry).
    - Retries up to `retries` times on 503/429/timeout (transient outages).
    """
    for attempt in range(retries + 1):
        time.sleep(SEC_DELAY)
        try:
            response = requests.get(url, headers=SEC_HEADERS, timeout=45)
        except requests.exceptions.Timeout:
            if attempt < retries:
                wait = 10 * (attempt + 1)
                print(f"    [timeout] attempt {attempt+1} -- retrying in {wait}s")
                time.sleep(wait)
                continue
            raise

        if response.status_code == 403:
            print("[STOP]  SEC rate limit hit (403). Exiting to protect IP.")
            sys.exit(1)

        if response.status_code in (429, 503) and attempt < retries:
            wait = 15 * (attempt + 1)
            print(f"    [{response.status_code}] attempt {attempt+1} -- retrying in {wait}s")
            time.sleep(wait)
            continue

        response.raise_for_status()
        return response

    response.raise_for_status()   # final raise if all retries failed
    return response


# ---------------------------------------------------------------------------
# CIK helpers
# ---------------------------------------------------------------------------

def normalize_cik(cik: str) -> str:
    """Return a 10-digit zero-padded CIK string."""
    return str(int(cik)).zfill(10)


def strip_cik(cik: str) -> str:
    """Return CIK without leading zeros (used in archive URLs)."""
    return str(int(cik))


# ---------------------------------------------------------------------------
# Quarter helpers
# ---------------------------------------------------------------------------

def report_date_to_quarter(report_date: str) -> str:
    """
    Convert a reportDate string to quarter label.

    '2025-09-30' -> '2025-Q3'
    '2025-06-30' -> '2025-Q2'
    '2025-03-31' -> '2025-Q1'
    '2024-12-31' -> '2024-Q4'
    """
    year, month, _ = report_date.split("-")
    month = int(month)
    quarter = (month - 1) // 3 + 1
    return f"{year}-Q{quarter}"


# ---------------------------------------------------------------------------
# Submissions API
# ---------------------------------------------------------------------------

def get_13f_filings(cik: str, num_quarters: int = BACKFILL_QUARTERS) -> list[dict]:
    """
    Fetch the EDGAR submissions JSON for *cik* and return the most recent
    *num_quarters* 13F-HR filings, oldest-first.

    Each entry:
        {
            "accession_number": "0001649339-25-000007",
            "report_date":      "2025-09-30",
            "filing_date":      "2025-11-03",
            "quarter":          "2025-Q3",
        }
    """
    cik_padded = normalize_cik(cik)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    print(f"  Fetching submissions for CIK {cik_padded} ...")
    data = sec_get(url).json()

    # The API may split older filings into separate pages; for 8 quarters we
    # only need recent filings so the main block is sufficient.
    recent = data.get("filings", {}).get("recent", {})
    forms        = recent.get("form", [])
    accessions   = recent.get("accessionNumber", [])
    report_dates = recent.get("reportDate", [])
    filing_dates = recent.get("filingDate", [])

    results = []
    for form, acc, rdate, fdate in zip(forms, accessions, report_dates, filing_dates):
        if form == "13F-HR":
            results.append({
                "accession_number": acc,
                "report_date":      rdate,
                "filing_date":      fdate,
                "quarter":          report_date_to_quarter(rdate),
            })

    # Take the most recent N, then reverse so we process oldest -> newest
    results = results[:num_quarters]
    results.reverse()
    return results


# ---------------------------------------------------------------------------
# Infotable XML fetcher
# ---------------------------------------------------------------------------

def _accession_no_dashes(accession_number: str) -> str:
    return accession_number.replace("-", "")


def _get_infotable_filename(cik: str, accession_number: str) -> str | None:
    """
    Fetch the filing index page and return the filename of the infotable XML.
    Returns None if we cannot determine it.
    """
    cik_plain = strip_cik(cik)
    acc_nodash = _accession_no_dashes(accession_number)
    index_url = (
        f"https://www.sec.gov/Archives/edgar/data/{cik_plain}"
        f"/{acc_nodash}/{accession_number}-index.htm"
    )
    try:
        resp = sec_get(index_url)
        # Look for links to XML files in the index page that are NOT the
        # primary_doc.  Common names: infotable.xml, form13fInfoTable.xml, etc.
        candidates = re.findall(r'href="([^"]+\.xml)"', resp.text, re.IGNORECASE)
        for fname in candidates:
            fname_lower = fname.lower()
            if "primary" not in fname_lower and "xsd" not in fname_lower:
                return Path(fname).name
    except Exception:
        pass
    return None


def get_infotable_xml(cik: str, accession_number: str) -> str:
    """
    Return the raw XML text of the 13F information table for this filing.

    Strategy (most reliable first):
      1. Fetch the filing index and find the infotable XML filename, then fetch it.
      2. Try the common fallback name 'infotable.xml'.
      3. Fetch the full .txt filing and extract the <informationTable> section.
    """
    cik_plain = strip_cik(cik)
    acc_nodash = _accession_no_dashes(accession_number)
    base_url = f"https://www.sec.gov/Archives/edgar/data/{cik_plain}/{acc_nodash}"

    # --- Strategy 1: parse the index page ---
    fname = _get_infotable_filename(cik, accession_number)
    if fname:
        xml_url = f"{base_url}/{fname}"
        print(f"    Fetching infotable: {fname}")
        try:
            resp = sec_get(xml_url)
            if "<informationTable" in resp.text or "<ns1:informationTable" in resp.text:
                return resp.text
        except Exception:
            pass

    # --- Strategy 2: common fallback filenames ---
    for fallback in ("infotable.xml", "form13fInfoTable.xml", "InfoTable.xml"):
        xml_url = f"{base_url}/{fallback}"
        print(f"    Trying fallback filename: {fallback}")
        try:
            resp = sec_get(xml_url)
            if "<informationTable" in resp.text or "<ns1:informationTable" in resp.text:
                return resp.text
        except requests.HTTPError:
            continue

    # --- Strategy 3: full .txt filing, extract XML block ---
    txt_url = f"https://www.sec.gov/Archives/edgar/data/{cik_plain}/{acc_nodash}/{accession_number}.txt"
    print(f"    Falling back to full .txt filing ...")
    resp = sec_get(txt_url)
    text = resp.text

    # The informationTable section is embedded in the .txt file
    match = re.search(
        r"(<informationTable[\s\S]*?</informationTable>)",
        text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)

    raise RuntimeError(
        f"Could not extract infotable XML for {accession_number} (CIK {cik})"
    )


# ---------------------------------------------------------------------------
# Per-investor orchestration
# ---------------------------------------------------------------------------

def fetch_investor_filings(investor: dict, num_quarters: int = BACKFILL_QUARTERS) -> list[dict]:
    """
    For a single investor dict (from investors.json), fetch up to *num_quarters*
    of 13F-HR filings and return a list of dicts:

        {
            "quarter":          "2025-Q3",
            "report_date":      "2025-09-30",
            "filing_date":      "2025-11-03",
            "accession_number": "0001649339-25-000007",
            "xml":              "<informationTable>...</informationTable>",
        }

    Any quarter whose holdings JSON already exists on disk is skipped (cache-hit).
    """
    investor_id = investor["id"]
    cik         = investor["cik"]
    investor_dir = HOLDINGS_DIR / investor_id

    filings = get_13f_filings(cik, num_quarters)
    if not filings:
        print(f"  [WARN]  No 13F-HR filings found for {investor['name']}")
        return []

    results = []
    for filing in filings:
        quarter = filing["quarter"]
        out_path = investor_dir / f"{quarter}.json"

        if out_path.exists():
            print(f"  [OK]  {investor_id}/{quarter}.json already exists -- skipping")
            continue

        print(f"  -> Fetching {investor_id} {quarter} ({filing['accession_number']})")
        xml_text = get_infotable_xml(cik, filing["accession_number"])
        results.append({**filing, "xml": xml_text})

    return results


# ---------------------------------------------------------------------------
# Quick smoke-test (run directly)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Test with Burry -- smallest portfolio, fast to verify
    test_investor = {
        "id": "burry",
        "name": "Michael Burry",
        "cik": "0001649339",
    }
    print("=== Smoke test: Michael Burry ===")
    filings = get_13f_filings(test_investor["cik"], num_quarters=2)
    print(f"Found {len(filings)} filings:")
    for f in filings:
        print(f"  {f['quarter']}  filed {f['filing_date']}  acc={f['accession_number']}")
    if filings:
        latest = filings[-1]
        print(f"\nFetching infotable XML for {latest['quarter']} ...")
        xml = get_infotable_xml(test_investor["cik"], latest["accession_number"])
        print(f"Got {len(xml):,} bytes of XML")
        # Show first 500 chars
        print(xml[:500])
