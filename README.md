# 🦈 Shark Watchlist HQ

A live investment watchlist dashboard tracking 10 Indian small & mid-cap equities with asymmetric upside potential.

**7 Tier 1 (Conditional Buy)** · **3 Tier 2 (Watch & Verify)** · **8 Rejected**

## Features

- **Live price fetching** via Anthropic API web search (requires API key)
- Entry zones, triggers, thesis for each stock
- Capital allocation framework
- Broker alert levels
- Collapsible sections for rejected stocks, alerts, allocation
- Dark terminal aesthetic, JetBrains Mono, mobile-responsive

## Deploy to GitHub Pages (5 minutes)

### Step 1: Create a GitHub repo

1. Go to [github.com/new](https://github.com/new)
2. Name it `shark-watchlist` (or anything you want)
3. Set it to **Public** (required for free GitHub Pages)
4. Click **Create repository**

### Step 2: Upload the file

1. Click **"uploading an existing file"** link on the empty repo page
2. Drag and drop `index.html` into the upload area
3. Click **Commit changes**

### Step 3: Enable GitHub Pages

1. Go to **Settings** → **Pages** (left sidebar)
2. Under **Source**, select **Deploy from a branch**
3. Branch: **main**, Folder: **/ (root)**
4. Click **Save**
5. Wait 1-2 minutes

### Step 4: Share the URL

Your dashboard is now live at:
```
https://YOUR-USERNAME.github.io/shark-watchlist/
```

Share this URL with friends. Done.

## Using Live Prices

Click **⚡ REFRESH PRICES** → enter your Anthropic API key when prompted.

- Get a key at [console.anthropic.com](https://console.anthropic.com)
- Key stays in your browser only, never stored on any server
- Each refresh costs ~$0.05-0.10 in API calls (10 web searches)
- Friends need their own API key for live prices

## Updating the Watchlist

Edit the `WATCHLIST` array in `index.html` to add/remove/modify stocks. Push to GitHub and it auto-deploys.

## Tech Stack

- Single HTML file, zero build step
- React 18 via CDN
- Babel standalone for JSX
- Anthropic API for web search (live prices)
- JetBrains Mono font

## Disclaimer

Not investment advice. Do your own research. Zero attachment, zero ego.