import os
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).parent.parent

# Data directories
DATA_DIR = ROOT / "data"
HOLDINGS_DIR = DATA_DIR / "holdings"
FRONTEND_DIR = DATA_DIR / "frontend"
CUSIP_MAP_PATH = DATA_DIR / "cusip_map.json"
INVESTORS_PATH = Path(__file__).parent / "investors.json"

# SEC EDGAR User-Agent -- SEC fair-access policy REQUIRES a real contact email.
# If the env var is missing or doesn't contain "@", we refuse to start. This
# stops a misconfigured CI run from sending bare requests that SEC will throttle.
_DEFAULT_UA = "SuperinvestorTracker/1.0 koushik@seatsnag.io"
_UA = os.environ.get("SEC_USER_AGENT", _DEFAULT_UA).strip()

if "@" not in _UA or _UA.endswith(" "):
    print(
        "[FATAL] SEC_USER_AGENT must include a real contact email "
        "(SEC fair-access policy). Got: " + repr(_UA),
        file=sys.stderr,
    )
    sys.exit(2)

SEC_HEADERS = {
    "User-Agent":      _UA,
    "Accept-Encoding": "gzip, deflate",
}

# Delay between SEC requests. Default 0.5s (~2 req/sec, 1/5th of SEC's 10/sec
# cap) per project policy — we'd rather wait than risk an IP block on shared
# GitHub Actions runners. Override via SEC_DELAY env var if needed.
SEC_DELAY = float(os.environ.get("SEC_DELAY", "0.5"))

# How many quarters of history to backfill
BACKFILL_QUARTERS = 20
