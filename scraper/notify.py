"""Send a WhatsApp digest of newly scraped 13F filings via CallMeBot.

Usage:
    NEW_FILES="data/holdings/burry/2026-Q3.json ..." python scraper/notify.py
    python scraper/notify.py --dry-run          # print message, don't send
    python scraper/notify.py --test             # send a one-line test ping

Env:
    WHATSAPP_PHONE    your number with country code, e.g. +919876543210
    CALLMEBOT_APIKEY  key CallMeBot sent you on WhatsApp
    NEW_FILES         whitespace-separated holdings files added in this run
    DASHBOARD_URL     link appended to the message

Reads data/frontend/changelog.json, so run after `main.py --export-only`.
Never fails the workflow: a notification problem must not block deploys.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "data" / "frontend" / "changelog.json"
DASHBOARD = os.environ.get("DASHBOARD_URL", "https://koushik83.github.io/Uber-Invest/")
MAX_CHARS = 1500


def money(v):
    v = v or 0
    for div, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(v) >= div:
            return f"${v / div:.1f}{suffix}"
    return f"${v:.0f}"


def new_filings():
    """(investor_id, quarter) pairs from NEW_FILES paths."""
    pairs = set()
    for path in os.environ.get("NEW_FILES", "").split():
        m = re.search(r"holdings/([^/]+)/(\d{4}-Q\d)\.json$", path.replace("\\", "/"))
        if m:
            pairs.add(m.groups())
    return pairs


def build_message(pairs):
    entries = json.loads(CHANGELOG.read_text(encoding="utf-8"))
    moves = [
        e for e in entries
        if (e.get("investor_id"), e.get("quarter")) in pairs
        and e.get("action") not in (None, "UNCHANGED")
    ]
    investors = sorted({e["investor"] for e in moves})
    quarters = sorted({q for _, q in pairs})

    def label(e):
        opt = f" {e['put_call']}" if e.get("put_call") else ""
        return f"{e.get('ticker') or e.get('stock_name', '?')}{opt}"

    def top(action, n, per_investor=2):
        rows, seen = [], Counter()
        for e in sorted((e for e in moves if e["action"] == action),
                        key=lambda e: e.get("value") or 0, reverse=True):
            if seen[e["investor"]] < per_investor:
                seen[e["investor"]] += 1
                rows.append(f"• {e['investor']}: {label(e)} ({money(e.get('value'))})")
            if len(rows) == n:
                break
        return rows

    def crowd(actions):
        # count distinct investors per ticker; skip unresolved CUSIPs
        pairs_ = {(label(e), e["investor"]) for e in moves
                  if e["action"] in actions and e.get("ticker") not in (None, "", "UNKNOWN")}
        return Counter(t for t, _ in pairs_)

    bought = crowd(("NEW", "INCREASED"))
    sold = crowd(("EXITED", "REDUCED"))

    lines = [f"📊 *Uber Invest* — {len(pairs)} new 13F filing(s) ({', '.join(quarters)})"]
    if investors:
        shown = ", ".join(investors[:12]) + (f" +{len(investors) - 12} more" if len(investors) > 12 else "")
        lines.append(f"Filed: {shown}")
    for title, rows in (("🆕 Biggest new positions", top("NEW", 5)),
                        ("🚪 Biggest exits", top("EXITED", 4))):
        if rows:
            lines += ["", f"*{title}*", *rows]
    crowd = [f"{t} ({n})" for t, n in bought.most_common(5) if n > 1]
    if crowd:
        lines += ["", "*🔥 Most bought:* " + ", ".join(crowd)]
    dumped = [f"{t} ({n})" for t, n in sold.most_common(5) if n > 1]
    if dumped:
        lines += ["*🧊 Most sold:* " + ", ".join(dumped)]
    lines += ["", f"🔗 {DASHBOARD}"]

    msg = "\n".join(lines)
    if len(msg) > MAX_CHARS:  # trim detail, never the link
        msg = msg[: MAX_CHARS - len(DASHBOARD) - 10].rsplit("\n", 1)[0] + f"\n…\n🔗 {DASHBOARD}"
    return msg


def send(text):
    phone = os.environ.get("WHATSAPP_PHONE", "").strip()
    key = os.environ.get("CALLMEBOT_APIKEY", "").strip()
    if not phone or not key:
        print("WHATSAPP_PHONE / CALLMEBOT_APIKEY not set -- skipping send.")
        return
    url = "https://api.callmebot.com/whatsapp.php?" + urllib.parse.urlencode(
        {"phone": phone, "text": text, "apikey": key})
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            body = r.read().decode("utf-8", "replace")
        ok = r.status == 200 and "error" not in body.lower()
        print("WhatsApp sent." if ok else f"CallMeBot responded oddly: {r.status} {body[:300]}")
    except Exception as exc:  # never fail the workflow over a notification
        print(f"::warning::WhatsApp send failed: {exc}")


def main():
    if "--test" in sys.argv:
        send(f"✅ Uber Invest alerts are connected.\n🔗 {DASHBOARD}")
        return
    pairs = new_filings()
    if not pairs:
        print("No new filings -- nothing to notify.")
        return
    msg = build_message(pairs)
    print(msg)
    if "--dry-run" not in sys.argv:
        send(msg)


if __name__ == "__main__":
    main()
