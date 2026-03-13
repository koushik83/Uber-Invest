# Cloudflare Worker Setup — Shark Watchlist Proxy

## One-time setup (5 minutes)

### 1. Create a free Cloudflare account
Go to https://dash.cloudflare.com/sign-up

### 2. Install Wrangler (Cloudflare CLI)
```bash
npm install -g wrangler
```

### 3. Login to Cloudflare
```bash
wrangler login
```
This opens your browser — click "Allow".

### 4. Deploy the worker
```bash
cd worker
wrangler deploy
```
It will print something like:
```
Published shark-watchlist-proxy (https://shark-watchlist-proxy.koush.workers.dev)
```

### 5. Add your API key as a secret
```bash
wrangler secret put ANTHROPIC_API_KEY
```
Paste your Anthropic API key when prompted. It's now encrypted on Cloudflare — nobody can read it.

### 6. Update the frontend
Open `index.html` and replace:
```
https://shark-watchlist-proxy.YOUR_SUBDOMAIN.workers.dev
```
with the actual URL from step 4 (e.g., `https://shark-watchlist-proxy.koush.workers.dev`).

### 7. Deploy to GitHub Pages
Push everything to GitHub, then enable GitHub Pages in your repo settings (Settings > Pages > Source: main branch).

## That's it!
- Your API key is safe on Cloudflare
- Your site is live on GitHub Pages
- Hit "REFRESH PRICES" and it works
- The worker only accepts requests from your GitHub Pages URL (CORS locked)
