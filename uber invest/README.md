# Uber Invest — Superinvestor 13F Tracker

Track what the world's best hedge fund managers are buying, selling, and holding — straight from SEC EDGAR 13F filings. No subscriptions, no paywalls, fully automated.

![GitHub Actions](https://github.com/koushik83/Uber-Invest/actions/workflows/scrape.yml/badge.svg)

---

## What It Does

- **Scrapes SEC EDGAR** every 6 hours for new 13F-HR filings from 40 of the world's top investors
- **Parses & diffs** holdings quarter-over-quarter to track NEW positions, INCREASED, REDUCED, and EXITED
- **Resolves CUSIPs → tickers** using SEC's company ticker database
- **Publishes a live dashboard** to GitHub Pages — auto-updated on every scrape run

## Live Dashboard

**[uber-invest.github.io](https://koushik83.github.io/Uber-Invest/)** *(deploys via GitHub Actions)*

### Four tabs:

| Tab | What you see |
|-----|--------------|
| **Feed** | Latest moves across all investors — filterable by action type & investor |
| **Conviction** | Cross-investor heatmap — which tickers are held by the most superinvestors |
| **Investors** | Portfolio deep-dive per manager — holdings, weights, quarter-over-quarter changes |
| **Calendar** | 2026 13F filing deadlines with live countdown |

---

## Investors Tracked (40)

<details>
<summary>Click to expand full list</summary>

| Investor | Fund | Style |
|----------|------|-------|
| Warren Buffett | Berkshire Hathaway | Value / Concentrated |
| Michael Burry | Scion Asset Management | Contrarian |
| Stanley Druckenmiller | Duquesne Family Office | Global Macro |
| David Tepper | Appaloosa Management | Distressed / Macro |
| Bill Ackman | Pershing Square | Activist |
| Seth Klarman | Baupost Group | Deep Value |
| Ray Dalio | Bridgewater Associates | Global Macro |
| George Soros | Soros Fund Management | Global Macro |
| Carl Icahn | Icahn Capital Management | Activist |
| James Simons | Renaissance Technologies | Quantitative |
| Ken Griffin | Citadel Advisors | Multi-Strategy |
| Israel Englander | Millennium Management | Multi-Strategy |
| Steve Cohen | Point72 Asset Management | Multi-Strategy |
| Chase Coleman | Tiger Global | Growth / Tech |
| Philippe Laffont | Coatue Management | Growth / Tech |
| Andreas Halvorsen | Viking Global | Long/Short |
| Lee Ainslie | Maverick Capital | Long/Short |
| Steve Mandel | Lone Pine Capital | Long/Short |
| Daniel Sundheim | D1 Capital Partners | Long/Short |
| Dan Loeb | Third Point | Activist / Event-Driven |
| Paul Singer | Elliott Management | Activist |
| Nelson Peltz | Trian Fund Management | Activist |
| Jeff Smith | Starboard Value | Activist |
| Barry Rosenstein | JANA Partners | Activist |
| David Einhorn | Greenlight Capital | Value / Short |
| Howard Marks | Oaktree Capital | Credit / Distressed |
| Larry Robbins | Glenview Capital | Healthcare Focus |
| Terry Smith | Fundsmith | Quality Growth |
| Paul Tudor Jones | Tudor Investment Corp | Global Macro |
| Joel Greenblatt | Gotham Asset Management | Quantitative Value |
| Mohnish Pabrai | Dalal Street LLC | Deep Value |
| Chris Hohn | TCI Fund Management | Concentrated / Activist |
| Li Lu | Himalaya Capital | Deep Value |
| Chuck Akre | Akre Capital Management | Compounders |
| David Abrams | Abrams Capital | Deep Value |
| Ron Baron | Baron Capital Group | Growth |
| Cathie Wood | ARK Investment Management | Disruptive Tech |
| Felix & Julian Baker | Baker Bros Advisors | Biotech |
| Bill Nygren | Harris Associates | Value |
| Jeffrey Ubben | Inclusive Capital | ESG / Activist |

</details>

---

## How It Works

```
SEC EDGAR                GitHub Actions (every 6h)             GitHub Pages
┌─────────┐   fetch.py   ┌──────────────────────────┐  build  ┌──────────────┐
│ 13F-HR  │ ──────────►  │ parse → diff → export    │ ──────► │ React app    │
│ filings │              │ (JSON data files)         │         │ (live site)  │
└─────────┘              └──────────────────────────┘         └──────────────┘
```

1. **`scraper/fetch.py`** — Rate-limited SEC EDGAR fetcher (0.15s delay, respects 403/429/503)
2. **`scraper/parse.py`** — Parses 13F XML infotables, normalizes dollar values
3. **`scraper/cusip_map.py`** — Resolves CUSIPs to tickers via SEC + OpenFIGI
4. **`scraper/diff.py`** — Diffs consecutive quarters to generate NEW/INCREASED/REDUCED/EXITED events
5. **`scraper/export.py`** — Exports JSON files consumed by the frontend
6. **`frontend/`** — Vite + React 18 single-page app

### Data files (auto-generated)

| File | Contents |
|------|----------|
| `data/frontend/changelog.json` | Last 5,000 moves across all investors |
| `data/frontend/conviction.json` | Cross-investor ticker conviction table |
| `data/frontend/latest_holdings.json` | Current top-200 holdings per investor |
| `data/frontend/investors_summary.json` | Metadata for all 40 investors |
| `data/holdings/{investor}/{quarter}.json` | Raw parsed holdings per filing |

---

## Running Locally

**Requirements:** Python 3.11+, Node 18+

```bash
# Clone
git clone https://github.com/koushik83/Uber-Invest.git
cd Uber-Invest

# Scraper — incremental (only fetches new quarters)
pip install requests lxml
python scraper/main.py

# Full backfill (8 quarters per investor)
python scraper/main.py --backfill

# Single investor
python scraper/main.py --investor burry

# Frontend dev server
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

---

## GitHub Actions Setup

The repo uses two jobs in `.github/workflows/scrape.yml`:

1. **`scrape`** — runs `python scraper/main.py` incrementally, commits any new data to `main`
2. **`deploy`** — builds the React app and deploys to `gh-pages` branch via `peaceiris/actions-gh-pages`

**Required secrets** (set in repo Settings → Secrets):

| Secret | Value |
|--------|-------|
| `CONTACT_EMAIL` | Your email — SEC requires it in the User-Agent header |

**Enable GitHub Pages** in repo Settings → Pages → Source: `gh-pages` branch.

---

## SEC Rate Limiting

The scraper strictly respects SEC's [fair access policy](https://www.sec.gov/developer):
- **0.15s minimum delay** between every request
- **Hard exit on 403** (IP-level block) — never retries after a rate-limit block
- **Retry with backoff** on transient 503/429 (15s, 30s)
- **Cache-first** — never re-downloads a filing that already exists on disk

---

## Project Structure

```
uber invest/
├── scraper/
│   ├── main.py          # Orchestrator: fetch → parse → diff → export
│   ├── fetch.py         # SEC EDGAR HTTP client
│   ├── parse.py         # 13F XML parser + value normalizer
│   ├── diff.py          # Quarter-over-quarter diff engine
│   ├── cusip_map.py     # CUSIP → ticker resolver
│   ├── export.py        # JSON export for frontend
│   ├── config.py        # Constants (delay, dirs, quarters)
│   └── investors.json   # Master list of 40 investors + CIKs
├── data/
│   ├── frontend/        # Pre-built JSON files for the React app
│   ├── holdings/        # Raw parsed holdings per investor/quarter
│   └── changelog/       # Diff JSONs per investor
├── frontend/
│   ├── src/
│   │   ├── App.jsx      # Main 4-tab application
│   │   └── index.css    # Dark terminal theme
│   ├── index.html
│   └── package.json
└── .github/
    └── workflows/
        └── scrape.yml   # Cron scrape + Pages deploy
```

---

## Data Source & Disclaimer

All data is sourced from **SEC EDGAR public filings** ([sec.gov](https://www.sec.gov)). 13F filings are due 45 days after quarter-end — holdings shown are **historical**, not real-time. This is a personal research tool, not financial advice.

---

*Built with Python + React. Data from SEC EDGAR.*
