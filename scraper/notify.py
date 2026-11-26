"""Send a Telegram digest of newly scraped 13F filings.

Usage:
    NEW_FILES="data/holdings/burry/2026-Q3.json ..." python scraper/notify.py
    python scraper/notify.py --dry-run          # print message, don't send
    python scraper/notify.py --test             # send a one-line test ping

Env:
    TELEGRAM_BOT_TOKEN  token from @BotFather
    TELEGRAM_CHAT_ID    your user id (from @userinfobot); you must /start the bot once
    NEW_FILES         whitespace-separated holdings files added in this run
    DASHBOARD_URL     link appended to the message

Reads data/frontend/changelog.json, so run after `main.py --export-only`.
Never fails the workflow: a notification problem must not block deploys.
"""
import json
import os
import re
import sys
import html
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "data" / "frontend" / "changelog.json"
DASHBOARD = os.environ.get("DASHBOARD_URL", "https://koushik83.github.io/Uber-Invest/")
MAX_CHARS = 3500  # Telegram limit is 4096


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
        return html.escape(f"{e.get('ticker') or e.get('stock_name', '?')}{opt}")

    def top(action, n, per_investor=2):
        rows, seen = [], Counter()
        for e in sorted((e for e in moves if e["action"] == action),
                        key=lambda e: e.get("value") or 0, reverse=True):
            if seen[e["investor"]] < per_investor:
                seen[e["investor"]] += 1
                rows.append(f"• {html.escape(e['investor'])}: {label(e)} ({money(e.get('value'))})")
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

    lines = [f"📊 <b>Uber Invest</b> — {len(pairs)} new 13F filing(s) ({', '.join(quarters)})"]
    if investors:
        shown = html.escape(", ".join(investors[:12])) + (f" +{len(investors) - 12} more" if len(investors) > 12 else "")
        lines.append(f"Filed: {shown}")
    for title, rows in (("🆕 Biggest new positions", top("NEW", 5)),
                        ("🚪 Biggest exits", top("EXITED", 4))):
        if rows:
            lines += ["", f"<b>{title}</b>", *rows]
    crowd = [f"{t} ({n})" for t, n in bought.most_common(5) if n > 1]
    if crowd:
        lines += ["", "<b>🔥 Most bought:</b> " + ", ".join(crowd)]
    dumped = [f"{t} ({n})" for t, n in sold.most_common(5) if n > 1]
    if dumped:
        lines += ["<b>🧊 Most sold:</b> " + ", ".join(dumped)]
    lines += ["", f"🔗 {DASHBOARD}"]

    msg = "\n".join(lines)
    if len(msg) > MAX_CHARS:  # trim detail, never the link
        msg = msg[: MAX_CHARS - len(DASHBOARD) - 10].rsplit("\n", 1)[0] + f"\n…\n🔗 {DASHBOARD}"
    return msg


def send(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set -- skipping send.")
        return
    data = urllib.parse.urlencode({"chat_id": chat, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage",
                                    data=data, timeout=30) as r:
            ok = json.loads(r.read()).get("ok")
        print("Telegram sent." if ok else "Telegram returned ok=false")
    except Exception as exc:  # never fail the workflow over a notification
        # don't print exc verbatim: urllib errors can include the URL (token)
        print(f"::warning::Telegram send failed: {type(exc).__name__} {getattr(exc, 'code', '')}")


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
