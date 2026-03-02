import os
from pathlib import Path

# Project root
ROOT = Path(__file__).parent.parent

# Data directories
DATA_DIR = ROOT / "data"
HOLDINGS_DIR = DATA_DIR / "holdings"
FRONTEND_DIR = DATA_DIR / "frontend"
CUSIP_MAP_PATH = DATA_DIR / "cusip_map.json"
INVESTORS_PATH = Path(__file__).parent / "investors.json"

# SEC EDGAR rate limiting -- DO NOT modify these values
SEC_HEADERS = {
    "User-Agent": os.environ.get(
        "SEC_USER_AGENT", "SuperinvestorTracker/1.0 contact@youremail.com"
    ),
    "Accept-Encoding": "gzip, deflate",
}
SEC_DELAY = 0.15  # seconds between requests -- NEVER remove this

# How many quarters of history to backfill
BACKFILL_QUARTERS = 8
