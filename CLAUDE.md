# 13F Superinvestor Tracker — Claude Code Build Instructions

## Project Overview

Build a full-stack data pipeline that tracks 13F SEC filings from top institutional investors (superinvestors). The system scrapes SEC EDGAR, parses holdings data, computes diffs between quarters, and serves it to a React frontend via static JSON files. The entire system runs for free on GitHub (Actions + Pages).

**This is NOT a real-time system.** 13F filings happen quarterly. The scraper runs during filing season (4 windows per year). The rest of the time, the data is static.

---

## Tech Stack

- **Backend/Scraper:** Python 3.12+
- **Data Storage:** JSON files in the git repo (no database needed)
- **Frontend:** React (Vite)
- **Automation:** GitHub Actions (cron)
- **Hosting:** GitHub Pages (free)
- **Data Source:** SEC EDGAR public API (no API key needed)

---

## ⚠️ CRITICAL: SEC EDGAR Rate Limits & Fair Access Policy

**DO NOT get us blocked by the SEC.** Follow these rules in ALL scraper code:

### Hard Rules
1. **Max 10 requests per second** — SEC will block your IP if you exceed this
2. **Always include a User-Agent header** in the format: `"SuperinvestorTracker/1.0 your@email.com"`
3. **Add a 0.15 second delay between EVERY request** (this keeps you well under 10/sec)
4. **Never parallelize requests** — always sequential, one at a time
5. **Cache aggressively** — if you already have a filing's data saved locally, never re-fetch it
6. **Check if file exists before fetching** — skip any quarter we already have on disk

### Implementation Pattern
```python
import time
import requests

SEC_HEADERS = {
    "User-Agent": "SuperinvestorTracker/1.0 contact@youremail.com",
    "Accept-Encoding": "gzip, deflate"
}
SEC_DELAY = 0.15  # seconds between requests — NEVER remove this

def sec_get(url):
    """Rate-limited GET request to SEC EDGAR."""
    time.sleep(SEC_DELAY)
    response = requests.get(url, headers=SEC_HEADERS)
    if response.status_code == 403:
        print("⛔ SEC rate limit hit (403). Exiting immediately to protect IP.")
        sys.exit(1)  # Hard exit — GitHub Actions cron will retry next cycle
    response.raise_for_status()
    return response
```

### During Backfill
The initial backfill pulls ~8 quarters x ~25 investors = ~200 filings. At 0.15s delay, that's about 30 seconds of requests plus parsing time. Each filing requires 2 requests (submissions JSON + infotable XML), so ~400 requests total. At 0.15s each, that's ~60 seconds. Completely safe.

---

## Project Structure

```
superinvestor-tracker/
├── scraper/
│   ├── main.py              # Entry point — orchestrates everything
│   ├── config.py             # SEC headers, delays, paths
│   ├── investors.json        # Curated list of investors + CIKs
│   ├── fetch.py              # SEC EDGAR API calls (rate-limited)
│   ├── parse.py              # Parse 13F XML infotables
│   ├── diff.py               # Compare quarters, generate changelog
│   ├── cusip_map.py          # CUSIP-to-ticker resolution
│   └── export.py             # Generate frontend JSON files
├── data/
│   ├── cusip_map.json        # CUSIP → ticker/name lookup
│   ├── holdings/
│   │   ├── burry/
│   │   │   ├── 2025-Q3.json
│   │   │   ├── 2025-Q2.json
│   │   │   └── ...
│   │   ├── druckenmiller/
│   │   │   ├── 2025-Q3.json
│   │   │   └── ...
│   │   └── ... (one folder per investor)
│   └── frontend/             # Generated files the React app reads
│       ├── latest_holdings.json
│       ├── changelog.json
│       ├── conviction.json
│       └── investors_summary.json
├── frontend/                 # React Vite app
│   ├── src/
│   │   ├── App.jsx           # Main tracker component
│   │   └── ...
│   ├── public/
│   │   └── data/             # Symlink or copy of data/frontend/
│   └── package.json
├── .github/
│   └── workflows/
│       └── scrape.yml        # GitHub Actions cron job
└── README.md
```

---

## Phase 1: Investor List (investors.json)

Create `scraper/investors.json` with this structure. Start with these investors:

```json
{
  "investors": [
    {
      "id": "burry",
      "name": "Michael Burry",
      "fund": "Scion Asset Management",
      "cik": "0001649339",
      "category": "og",
      "avatar": "MB"
    },
    {
      "id": "buffett",
      "name": "Warren Buffett",
      "fund": "Berkshire Hathaway",
      "cik": "0001067983",
      "category": "og",
      "avatar": "WB"
    },
    {
      "id": "druckenmiller",
      "name": "Stanley Druckenmiller",
      "fund": "Duquesne Family Office",
      "cik": "0001536411",
      "category": "og",
      "avatar": "SD"
    },
    {
      "id": "tepper",
      "name": "David Tepper",
      "fund": "Appaloosa Management",
      "cik": "0001047644",
      "category": "og",
      "avatar": "DT"
    },
    {
      "id": "ackman",
      "name": "Bill Ackman",
      "fund": "Pershing Square",
      "cik": "0001336528",
      "category": "og",
      "avatar": "BA"
    },
    {
      "id": "klarman",
      "name": "Seth Klarman",
      "fund": "Baupost Group",
      "cik": "0001061768",
      "category": "og",
      "avatar": "SK"
    },
    {
      "id": "coleman",
      "name": "Chase Coleman",
      "fund": "Tiger Global",
      "cik": "0001167483",
      "category": "og",
      "avatar": "CC"
    },
    {
      "id": "loeb",
      "name": "Dan Loeb",
      "fund": "Third Point",
      "cik": "0001040273",
      "category": "og",
      "avatar": "DL"
    },
    {
      "id": "dalio",
      "name": "Ray Dalio",
      "fund": "Bridgewater Associates",
      "cik": "0001350694",
      "category": "og",
      "avatar": "RD"
    },
    {
      "id": "smith",
      "name": "Terry Smith",
      "fund": "Fundsmith",
      "cik": "0001828937",
      "category": "og",
      "avatar": "TS"
    },
    {
      "id": "einhorn",
      "name": "David Einhorn",
      "fund": "Greenlight Capital",
      "cik": "0001079114",
      "category": "og",
      "avatar": "DE"
    },
    {
      "id": "pabrai",
      "name": "Mohnish Pabrai",
      "fund": "Dalal Street LLC",
      "cik": "0001549575",
      "category": "og",
      "avatar": "MP"
    },
    {
      "id": "hohn",
      "name": "Chris Hohn",
      "fund": "TCI Fund Management",
      "cik": "0001647251",
      "category": "og",
      "avatar": "CH"
    },
    {
      "id": "marks",
      "name": "Howard Marks",
      "fund": "Oaktree Capital",
      "cik": "0000949509",
      "category": "og",
      "avatar": "HM"
    },
    {
      "id": "griffin",
      "name": "Ken Griffin",
      "fund": "Citadel Advisors",
      "cik": "0001423053",
      "category": "og",
      "avatar": "KG"
    },
    {
      "id": "robbins",
      "name": "Larry Robbins",
      "fund": "Glenview Capital",
      "cik": "0001138995",
      "category": "og",
      "avatar": "LR"
    },
    {
      "id": "singer",
      "name": "Paul Singer",
      "fund": "Elliott Management",
      "cik": "0001061165",
      "category": "og",
      "avatar": "PS"
    },
    {
      "id": "soros",
      "name": "George Soros",
      "fund": "Soros Fund Management",
      "cik": "0001029160",
      "category": "og",
      "avatar": "GS"
    },
    {
      "id": "peltz",
      "name": "Nelson Peltz",
      "fund": "Trian Fund Management",
      "cik": "0001345471",
      "category": "og",
      "avatar": "NP"
    },
    {
      "id": "viking",
      "name": "Andreas Halvorsen",
      "fund": "Viking Global",
      "cik": "0001103804",
      "category": "og",
      "avatar": "AH"
    }
  ]
}
```

---

## Phase 2: SEC EDGAR Fetcher (fetch.py)

### How the EDGAR API works

1. **Get filing list:** `GET https://data.sec.gov/submissions/CIK{cik}.json`
   - Returns JSON with `filings.recent` containing parallel arrays
   - Filter for `form === "13F-HR"` entries (not 13F-NT, not 13F-HR/A unless you want amendments)
   - Get `accessionNumber` and `reportDate` for each 13F filing

2. **Get infotable URL:** Convert accession number to directory URL:
   - Accession `0001649339-25-000007` → remove dashes → `000164933925000007`
   - URL: `https://www.sec.gov/Archives/edgar/data/{cik_no_leading_zeros}/{accession_no_dashes}/`
   - Fetch the directory listing (HTML) and find the XML file that is NOT `primary_doc.xml`
   - OR construct it as: `https://www.sec.gov/Archives/edgar/data/{cik_no_leading_zeros}/{accession_no_dashes}/infotable.xml`
   - Note: the infotable filename varies — sometimes it's `infotable.xml`, sometimes something else. Safest approach: fetch the `-index.htm` page and parse for the infotable link, OR fetch the `.txt` filing and parse the XML section.

3. **Alternative reliable approach:** Fetch the full text filing at:
   `https://www.sec.gov/Archives/edgar/data/{cik_no_leading_zeros}/{accession_with_dashes}.txt`
   This contains the complete filing as a text document with embedded XML. Parse out the `<informationTable>` section.

### Key Implementation Notes

- `reportDate` tells you the quarter: "2025-09-30" = Q3 2025, "2025-06-30" = Q2 2025, etc.
- Convert to quarter format: extract year and quarter from reportDate for file naming
- **Always check if `data/holdings/{investor_id}/{year}-Q{n}.json` already exists before fetching** — never re-download what you already have
- CIK in URLs sometimes needs leading zeros (10 digits), sometimes doesn't — handle both
- Some investors file 13F-HR/A (amendments) — for v1, skip these and only use 13F-HR

---

## Phase 3: XML Parser (parse.py)

The 13F infotable XML has this structure:

```xml
<informationTable>
  <infoTable>
    <nameOfIssuer>PALANTIR TECHNOLOGIES INC</nameOfIssuer>
    <titleOfClass>CL A</titleOfClass>
    <cusip>69608A108</cusip>
    <value>912000</value>  <!-- value in thousands of dollars -->
    <shrsOrPrnAmt>
      <sshPrnamt>5000000</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shrsOrPrnAmt>
    <putCall>PUT</putCall>  <!-- only present for options -->
    <investmentDiscretion>SOLE</investmentDiscretion>
    <votingAuthority>
      <Sole>5000000</Sole>
      <Shared>0</Shared>
      <None>0</None>
    </votingAuthority>
  </infoTable>
  <!-- more entries... -->
</informationTable>
```

### Parse each entry into this JSON structure:

```json
{
  "cusip": "69608A108",
  "name": "PALANTIR TECHNOLOGIES INC",
  "title_of_class": "CL A",
  "value": 912000000,
  "shares": 5000000,
  "share_type": "SH",
  "put_call": "PUT",
  "investment_discretion": "SOLE"
}
```

**Note:** The `<value>` field in the XML is in THOUSANDS. Multiply by 1000 for actual dollar value.

### Output file format (per quarter per investor):

Save to `data/holdings/{investor_id}/{year}-Q{n}.json`:

```json
{
  "investor_id": "burry",
  "cik": "0001649339",
  "quarter": "2025-Q3",
  "report_date": "2025-09-30",
  "filing_date": "2025-11-03",
  "accession_number": "0001649339-25-000007",
  "total_value": 1381198000,
  "num_holdings": 8,
  "holdings": [
    {
      "cusip": "69608A108",
      "name": "PALANTIR TECHNOLOGIES INC",
      "ticker": "PLTR",
      "title_of_class": "CL A",
      "value": 912000000,
      "shares": 5000000,
      "share_type": "SH",
      "put_call": "PUT"
    }
  ]
}
```

### XML Parsing Notes

- Use Python's `xml.etree.ElementTree` or `lxml`
- Watch out for XML namespaces — the infotable often has a namespace like `http://www.sec.gov/Archives/edgar/xbrl/13finfo-table`
- Handle missing `<putCall>` field gracefully (it's only present for options, not stock positions)
- Some filings use slightly different XML tag names or casing — be defensive

---

## Phase 4: CUSIP Mapping (cusip_map.py)

CUSIPs are the SEC's stock identifiers. Your users think in tickers (AAPL, NVDA). You need a mapping.

### Strategy:
1. Start with an empty `data/cusip_map.json`
2. As you parse filings, for each unknown CUSIP, try to resolve it:
   - First check the SEC's `company_tickers.json` at `https://www.sec.gov/files/company_tickers.json` (maps CIK/ticker/name — download once and cache)
   - Match by company name (fuzzy match `nameOfIssuer` against SEC company names)
   - For common stocks this works well. For options, preferred shares, etc. use the base CUSIP (first 6 digits)
3. If automated resolution fails, flag it as `"ticker": "UNKNOWN"` — you can manually fix later
4. Save resolved mappings to `data/cusip_map.json` so you never re-resolve

### cusip_map.json format:
```json
{
  "69608A108": {
    "ticker": "PLTR",
    "name": "Palantir Technologies Inc",
    "sector": "Technology"
  },
  "67066G104": {
    "ticker": "NVDA",
    "name": "NVIDIA Corp",
    "sector": "Technology"
  }
}
```

### OpenFIGI API (optional, for stubborn CUSIPs):
`https://api.openfigi.com/v3/mapping` — POST with CUSIP to get ticker. Free tier: 25 requests/minute. Only use this as fallback for CUSIPs you can't resolve from SEC data.

---

## Phase 5: Diff Engine (diff.py)

This is the core logic that powers the changelog. Compare two consecutive quarter snapshots for the same investor.

### Input: Two quarter JSON files (e.g., 2025-Q2.json and 2025-Q3.json)

### Logic:
```
For each holding in current quarter:
  - If CUSIP not in previous quarter → action: "NEW"
  - If CUSIP in both, shares increased → action: "INCREASED"
  - If CUSIP in both, shares decreased → action: "REDUCED"
  - If CUSIP in both, shares unchanged → action: "UNCHANGED"

For each holding in previous quarter:
  - If CUSIP not in current quarter → action: "EXITED"
```

### Changelog entry format:
```json
{
  "investor_id": "burry",
  "investor_name": "Michael Burry",
  "fund": "Scion Asset Management",
  "quarter": "2025-Q3",
  "ticker": "PLTR",
  "cusip": "69608A108",
  "stock_name": "Palantir Technologies Inc",
  "action": "NEW",
  "current_shares": 5000000,
  "previous_shares": 0,
  "current_value": 912000000,
  "previous_value": 0,
  "change_shares_pct": null,
  "put_call": "PUT",
  "filing_date": "2025-11-03"
}
```

### For "INCREASED" / "REDUCED", calculate:
- `change_shares_pct`: `((current_shares - previous_shares) / previous_shares) * 100`
- Round to 1 decimal place

---

## Phase 6: Frontend JSON Export (export.py)

Generate the JSON files the React frontend reads. All go in `data/frontend/`.

### 1. `changelog.json` — Powers the Feed tab
Latest changes across all investors, sorted by filing_date descending:
```json
[
  {
    "time": "2025-11-03",
    "investor": "Michael Burry",
    "investor_id": "burry",
    "avatar": "MB",
    "action": "NEW",
    "ticker": "PLTR",
    "stock_name": "Palantir Technologies",
    "detail": "New position — 5.0M shares ($912M)",
    "type": "new",
    "put_call": "PUT",
    "value": 912000000
  }
]
```

The `type` field maps to UI colors: "new" = blue, "buy" = green (INCREASED), "sell" = red (REDUCED/EXITED)

### 2. `conviction.json` — Powers the Conviction tab
Cross-investor analysis. For the LATEST quarter only:
```json
[
  {
    "ticker": "NVDA",
    "name": "NVIDIA Corp",
    "sector": "Technology",
    "holders": ["Michael Burry", "Stanley Druckenmiller", "Chase Coleman"],
    "holder_count": 3,
    "total_value": 4200000000,
    "any_new": true
  }
]
```
Sort by `holder_count` descending.

### 3. `investors_summary.json` — Powers the Investors tab
```json
[
  {
    "id": "burry",
    "name": "Michael Burry",
    "fund": "Scion Asset Management",
    "avatar": "MB",
    "cik": "0001649339",
    "latest_quarter": "2025-Q3",
    "total_value": 1381198000,
    "num_holdings": 8,
    "num_new": 7,
    "top_holdings": [
      {"ticker": "PLTR", "value": 912000000, "weight": 66.0, "put_call": "PUT"}
    ]
  }
]
```

### 4. `latest_holdings.json` — Detailed holdings for investor drill-down
```json
{
  "burry": {
    "quarter": "2025-Q3",
    "holdings": [
      {
        "ticker": "PLTR",
        "name": "Palantir Technologies",
        "shares": 5000000,
        "value": 912000000,
        "weight": 66.0,
        "change_pct": null,
        "is_new": true,
        "put_call": "PUT",
        "sector": "Technology"
      }
    ]
  }
}
```

---

## Phase 7: GitHub Actions Workflow

Create `.github/workflows/scrape.yml`:

```yaml
name: Scrape 13F Filings

on:
  schedule:
    # During filing season (Feb, May, Aug, Nov): every 6 hours
    # Off-season: once daily at midnight UTC
    - cron: '0 */6 * * *'
  workflow_dispatch: # Manual trigger

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install requests lxml

      - name: Run scraper
        run: python scraper/main.py
        env:
          SEC_USER_AGENT: "SuperinvestorTracker/1.0 ${{ secrets.CONTACT_EMAIL }}"

      - name: Commit if data changed
        run: |
          git config user.name "13F Bot"
          git config user.email "bot@users.noreply.github.com"
          git add data/
          git diff --cached --quiet || \
            git commit -m "📊 Update holdings $(date -u +%Y-%m-%d_%H:%M)"
          git push

  deploy:
    needs: scrape
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 20

      - name: Build frontend
        working-directory: ./frontend
        run: |
          npm ci
          npm run build

      - name: Copy data to build
        run: |
          mkdir -p frontend/dist/data
          cp data/frontend/*.json frontend/dist/data/

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./frontend/dist
```

---

## Phase 8: React Frontend

Use the same dark terminal aesthetic from the existing tracker artifact. The frontend reads from `/data/*.json` files.

### Key changes from the mock artifact:
- Replace all `generateHoldings()` / `generateChangelog()` mock functions with `fetch()` calls to the JSON files
- Add loading states
- Add error handling if JSON hasn't been generated yet
- Keep the same 4 tabs: Feed, Conviction, Investors, Calendar
- Keep the filing countdown timer (hardcode 2026 deadlines)
- Keep the same color scheme, typography, animations

### Data fetching pattern:
```jsx
const [data, setData] = useState(null);
const [loading, setLoading] = useState(true);

useEffect(() => {
  Promise.all([
    fetch('/data/changelog.json').then(r => r.json()),
    fetch('/data/conviction.json').then(r => r.json()),
    fetch('/data/investors_summary.json').then(r => r.json()),
    fetch('/data/latest_holdings.json').then(r => r.json()),
  ])
  .then(([changelog, conviction, investors, holdings]) => {
    setData({ changelog, conviction, investors, holdings });
    setLoading(false);
  })
  .catch(err => {
    console.error('Failed to load data:', err);
    setLoading(false);
  });
}, []);
```

---

## Build Order

Execute in this exact sequence:

1. **Set up project structure** — create all directories and placeholder files
2. **Create `investors.json`** — the curated investor list above
3. **Build `fetch.py`** — SEC EDGAR API calls with rate limiting (test with Burry's CIK first since his portfolio is tiny)
4. **Build `parse.py`** — XML infotable parser
5. **Build `cusip_map.py`** — CUSIP resolution logic
6. **Build `diff.py`** — Quarter comparison engine
7. **Build `export.py`** — Frontend JSON generator
8. **Build `main.py`** — Orchestrator that ties 3-7 together
9. **Run the backfill** — Pull 8 quarters of history for all investors, test locally
10. **Build the React frontend** — Port the existing artifact to use real JSON fetches
11. **Set up GitHub Actions** — The cron workflow
12. **Deploy to GitHub Pages** — Ship it

### Testing approach:
- Test with Burry FIRST (CIK: 0001649339) — only 8 holdings, fast to verify
- Then test with Buffett (CIK: 0001067983) — large portfolio, stress-tests parser
- Then run full backfill for all 20 investors
- Verify frontend renders correctly with real data

---

## Important Gotchas

1. **XML namespaces** — 13F infotables have namespaces that vary between filings. Use namespace-agnostic parsing or handle the common variants.

2. **Value is in thousands** — The `<value>` field in the XML is in $1,000s. A value of `912000` means $912,000,000. Always multiply by 1000.

3. **Options vs stocks** — `<putCall>` is only present for options. No tag = regular stock holding. Display PUT/CALL badges in the UI.

4. **13F-HR vs 13F-HR/A** — HR/A is an amendment (correction). For v1, only use 13F-HR. Later you can add logic to prefer HR/A over HR for the same quarter.

5. **Some investors have very large portfolios** — Bridgewater has 1000+ holdings. Make sure your parser handles large infotables and your frontend can paginate.

6. **CIK formatting** — Sometimes 10 digits with leading zeros (0001649339), sometimes without (1649339). The submissions API needs 10 digits. Archive URLs work with or without.

7. **Filing date vs report date** — `reportDate` is the quarter end (Sep 30). `filingDate` is when they actually filed (Nov 3). Show both in the UI but use reportDate for quarter assignment.

8. **CUSIP collisions** — Same company can have multiple CUSIPs (common stock, preferred, options). Group by base CUSIP (first 6 chars) if you want to consolidate.

---

## The Backfill Strategy

For the first run, you need historical data. Here's the approach:

1. For each investor, fetch their submissions JSON (1 request per investor)
2. From the filings list, find the last 8 entries where `form === "13F-HR"` (gives ~2 years)
3. For each of those 8 filings, fetch and parse the infotable (1-2 requests per filing)
4. Save each as `{investor_id}/{year}-Q{n}.json`
5. Run the diff engine across consecutive quarters
6. Generate the frontend JSONs

Total requests for 20 investors × 8 quarters: ~20 (submissions) + ~160 (infotables) = ~180 requests. At 0.15s delay = ~27 seconds. Completely safe.

After backfill, each quarterly update is just 20 investors × 1 new filing = ~40 requests. Trivial.