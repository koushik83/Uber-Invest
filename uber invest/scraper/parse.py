"""
Phase 3: 13F infotable XML parser.

Parses the raw XML returned by fetch.py and saves structured JSON to
  data/holdings/{investor_id}/{quarter}.json

NOTE on <value> units
---------------------
The SEC 13F form instructions say to report values in thousands of dollars,
but real modern filings (verified against known portfolio sizes) store values
in plain dollars.  We store values as-is from the XML (no multiplication).
If you ever encounter an old filing where values look 1000x too small, that
filer is reporting in thousands and you would need the * 1000 adjustment --
but for all post-2020 filings tested so far, raw dollars is correct.
"""

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from config import HOLDINGS_DIR


# ---------------------------------------------------------------------------
# Namespace handling
# ---------------------------------------------------------------------------

def _strip_namespaces(xml_text: str) -> str:
    """
    Remove XML namespace declarations and prefixes so ElementTree can use
    plain tag names regardless of which namespace URL the filer chose.

    Before:  <n1:informationTable xmlns:n1="http://..." xsi:schemaLocation="...">
    After:   <informationTable>
    """
    # Remove namespace declarations (xmlns="..." and xmlns:foo="...")
    xml_text = re.sub(r'\s+xmlns(?::\w+)?="[^"]*"', "", xml_text)
    # Remove namespace-prefixed attributes (e.g. xsi:schemaLocation="...")
    xml_text = re.sub(r'\s+\w+:\w+="[^"]*"', "", xml_text)
    # Remove namespace prefixes from opening/closing/self-closing tags
    xml_text = re.sub(r"<(/)?([\w]+):([\w]+)", r"<\1\3", xml_text)
    return xml_text


# ---------------------------------------------------------------------------
# Per-entry parsing
# ---------------------------------------------------------------------------

def _text(element, tag: str, default=None):
    """Return stripped text of a child tag, or *default* if absent."""
    child = element.find(tag)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def _parse_info_table_entry(entry: ET.Element) -> dict:
    """Parse one <infoTable> element into a holding dict."""
    # Shares / principal amount block
    shares_block = entry.find("shrsOrPrnAmt")
    if shares_block is not None:
        shares     = int(_text(shares_block, "sshPrnamt", "0").replace(",", ""))
        share_type = _text(shares_block, "sshPrnamtType", "SH")
    else:
        shares, share_type = 0, "SH"

    # Value -- stored as plain dollars in modern filings (see module docstring)
    raw_value = _text(entry, "value", "0").replace(",", "")
    value = int(float(raw_value))          # float() handles rare decimals

    # putCall is optional (only present for options)
    put_call_raw = _text(entry, "putCall")
    put_call = put_call_raw.upper() if put_call_raw else None   # "PUT" / "CALL" / None

    return {
        "cusip":                _text(entry, "cusip", ""),
        "name":                 _text(entry, "nameOfIssuer", ""),
        "title_of_class":       _text(entry, "titleOfClass", ""),
        "value":                value,
        "shares":               shares,
        "share_type":           share_type,
        "put_call":             put_call,
        "investment_discretion": _text(entry, "investmentDiscretion", ""),
    }


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_infotable_xml(xml_text: str) -> list[dict]:
    """
    Parse a 13F infotable XML string and return a list of holding dicts.
    Handles namespace variants found across SEC filings.
    """
    clean_xml = _strip_namespaces(xml_text)

    try:
        root = ET.fromstring(clean_xml)
    except ET.ParseError as exc:
        raise ValueError(f"Failed to parse infotable XML: {exc}") from exc

    # Root might BE informationTable, or it might be wrapped (rare)
    if root.tag == "informationTable":
        table = root
    else:
        table = root.find("informationTable")
        if table is None:
            raise ValueError("Could not find <informationTable> in XML")

    holdings = []
    for entry in table.findall("infoTable"):
        holding = _parse_info_table_entry(entry)
        if holding["cusip"]:          # skip any malformed entries with no CUSIP
            holdings.append(holding)

    # ------------------------------------------------------------------
    # Value-unit normalisation
    # SEC 13F requires values in thousands of dollars, but some filers
    # (e.g. Scion/Burry) report raw dollars instead.
    # Heuristic: if the MEDIAN position value < 500,000 the filer is
    # reporting in thousands and we must multiply by 1000.
    # Using median (not min) avoids false triggers from tiny option legs.
    # ------------------------------------------------------------------
    if holdings:
        pos_vals = sorted(h["value"] for h in holdings if h["value"] > 0)
        if pos_vals:
            mid = len(pos_vals) // 2
            median_val = pos_vals[mid] if len(pos_vals) % 2 else (pos_vals[mid - 1] + pos_vals[mid]) // 2
            if median_val < 500_000:
                for h in holdings:
                    h["value"] *= 1000

    return holdings


# ---------------------------------------------------------------------------
# Save to disk
# ---------------------------------------------------------------------------

def save_quarter(
    investor: dict,
    filing: dict,
    holdings: list[dict],
) -> Path:
    """
    Write the structured quarter JSON to
      data/holdings/{investor_id}/{quarter}.json

    *filing* must have keys: quarter, report_date, filing_date, accession_number
    *holdings* is the list returned by parse_infotable_xml(), optionally already
    enriched with "ticker" / "sector" fields by cusip_map.py.

    Returns the path written.
    """
    investor_id = investor["id"]
    cik         = investor["cik"]
    quarter     = filing["quarter"]

    investor_dir = HOLDINGS_DIR / investor_id
    investor_dir.mkdir(parents=True, exist_ok=True)

    # Add ticker placeholder if not already present
    for h in holdings:
        h.setdefault("ticker", None)
        h.setdefault("sector", None)

    total_value = sum(h["value"] for h in holdings)

    # Build the output structure (strip internal-only fields before saving)
    output_holdings = []
    for h in holdings:
        output_holdings.append({
            "cusip":          h["cusip"],
            "name":           h["name"],
            "ticker":         h.get("ticker"),
            "title_of_class": h["title_of_class"],
            "value":          h["value"],
            "shares":         h["shares"],
            "share_type":     h["share_type"],
            "put_call":       h["put_call"],
            "sector":         h.get("sector"),
        })

    record = {
        "investor_id":      investor_id,
        "cik":              cik,
        "quarter":          quarter,
        "report_date":      filing["report_date"],
        "filing_date":      filing["filing_date"],
        "accession_number": filing["accession_number"],
        "total_value":      total_value,
        "num_holdings":     len(output_holdings),
        "holdings":         output_holdings,
    }

    out_path = investor_dir / f"{quarter}.json"
    out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"  Saved {out_path.relative_to(HOLDINGS_DIR.parent.parent)} "
          f"({len(output_holdings)} holdings, ${total_value:,.0f} total)")
    return out_path


# ---------------------------------------------------------------------------
# Convenience loader
# ---------------------------------------------------------------------------

def load_quarter(investor_id: str, quarter: str) -> dict | None:
    """Load a saved quarter JSON, or return None if it doesn't exist."""
    path = HOLDINGS_DIR / investor_id / f"{quarter}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_quarters(investor_id: str) -> list[str]:
    """Return sorted list of quarter labels that exist on disk for an investor."""
    investor_dir = HOLDINGS_DIR / investor_id
    if not investor_dir.exists():
        return []
    quarters = [p.stem for p in sorted(investor_dir.glob("*.json"))]
    return quarters


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from fetch import get_infotable_xml

    investor = {
        "id":   "burry",
        "name": "Michael Burry",
        "cik":  "0001649339",
    }
    filing = {
        "quarter":          "2025-Q3",
        "report_date":      "2025-09-30",
        "filing_date":      "2025-11-03",
        "accession_number": "0001649339-25-000007",
    }

    print("=== Smoke test: parse Burry Q3 2025 ===")
    xml = get_infotable_xml(investor["cik"], filing["accession_number"])
    holdings = parse_infotable_xml(xml)

    print(f"Parsed {len(holdings)} holdings:")
    for h in holdings:
        pc = f" [{h['put_call']}]" if h["put_call"] else ""
        print(f"  {h['name']:<40} {h['cusip']}  ${h['value']:>15,.0f}  {h['shares']:>10,} sh{pc}")

    total = sum(h["value"] for h in holdings)
    print(f"\nTotal portfolio value: ${total:,.0f}")

    out = save_quarter(investor, filing, holdings)
    print(f"\nSaved to: {out}")

    # Verify round-trip
    loaded = load_quarter("burry", "2025-Q3")
    assert loaded["num_holdings"] == len(holdings)
    assert loaded["total_value"] == total
    print("Round-trip load OK")
