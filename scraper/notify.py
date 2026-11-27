"""Uber Invest Telegram digest: one message every DIGEST_DAYS days.

What's in it: 13F filings that landed since the last digest (who filed,
biggest new positions and exits, most bought / sold), the most widely held
stocks right now, and a countdown to the next 13F deadline. Short summary
plus the dashboard link -- not a data dump.

Usage:
    python scraper/notify.py                # send if DIGEST_DAYS have passed
    python scraper/notify.py --force        # send now regardless
    python scraper/notify.py --dry-run      # print the message, send nothing, save nothing
    python scraper/notify.py --test         # one-line test ping

Env:
    TELEGRAM_BOT_TOKEN  token from @BotFather
    TELEGRAM_CHAT_ID    your user id (from @userinfobot); you must /start the bot once
    DASHBOARD_URL       link appended to the message

Reads data/frontend/*.json, so run after `main.py --export-only`.
State (date of last digest) lives in data/digest_state.json.
Never fails the workflow: a notification problem must not block anything.
"""
import datetime as dt
import html
import json
import os
import sys
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "data" / "frontend"
STATE = ROOT / "data" / "digest_state.json"
DASHBOARD = os.environ.get("DASHBOARD_URL", "https://koushik83.github.io/Uber-Invest/")
DIGEST_DAYS = 15
MAX_CHARS = 3500  # Telegram limit is 4096
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def money(v):
    v = v or 0
    for div, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(v) >= div:
            return f"${v / div:.1f}{suffix}"
    return f"${v:.0f}"


def load(name):
    return json.loads((FRONTEND / name).read_text(encoding="utf-8"))


def next_deadline(today):
    """13F-HR is due 45 days after quarter end: ~Feb 14, May 15, Aug 14, Nov 14."""
    for year in (today.year, today.year + 1):
        for month, day, qtr in ((2, 14, f"{year - 1}-Q4"), (5, 15, f"{year}-Q1"),
                                (8, 14, f"{year}-Q2"), (11, 14, f"{year}-Q3")):
            d = dt.date(year, month, day)
            if d >= today:
                return d, qtr


def label(e):
    opt = f" {e['put_call']}" if e.get("put_call") else ""
    return html.escape(f"{e.get('ticker') or e.get('stock_name', '?')}{opt}")


def top(moves, action, n, per_investor=2):
    rows, seen = [], Counter()
    for e in sorted((e for e in moves if e["action"] == action),
                    key=lambda e: e.get("value") or 0, reverse=True):
        if seen[e["investor"]] < per_investor:
            seen[e["investor"]] += 1
            rows.append(f"• {html.escape(e['investor'])}: {label(e)} ({money(e.get('value'))})")
        if len(rows) == n:
            break
    return rows


def crowd(moves, actions):
    """Distinct investors per ticker; unresolved CUSIPs skipped."""
    pairs = {(label(e), e["investor"]) for e in moves
             if e["action"] in actions and e.get("ticker") not in (None, "", "UNKNOWN")}
    return Counter(t for t, _ in pairs)


def build_digest(since, today):
    changelog = load("changelog.json")
    conviction = load("conviction.json")
    summary = load("investors_summary.json")

    moves = [e for e in changelog
             if since.isoformat() < e.get("time", "") <= today.isoformat()
             and e.get("action") not in (None, "UNCHANGED")]
    filers = sorted({e["investor"] for e in moves})

    lines = [f"📈 <b>Uber Invest — {DIGEST_DAYS}-day digest</b>",
             f"<i>{since:%d %b} → {today:%d %b %Y}</i>", ""]

    if filers:
        shown = html.escape(", ".join(filers[:10])) + (f" +{len(filers) - 10} more" if len(filers) > 10 else "")
        lines.append(f"<b>{len(filers)} investor(s) filed new 13Fs:</b> {shown}")
        for title, rows in (("🆕 Biggest new positions", top(moves, "NEW", 5)),
                            ("🚪 Biggest exits", top(moves, "EXITED", 4))):
            if rows:
                lines += ["", f"<b>{title}</b>", *rows]
        bought = [f"{t} ({n})" for t, n in crowd(moves, ("NEW", "INCREASED")).most_common(5) if n > 1]
        sold = [f"{t} ({n})" for t, n in crowd(moves, ("EXITED", "REDUCED")).most_common(5) if n > 1]
        if bought or sold:
            lines.append("")
        if bought:
            lines.append("<b>🔥 Most bought:</b> " + ", ".join(bought))
        if sold:
            lines.append("<b>🧊 Most sold:</b> " + ", ".join(sold))
    else:
        lines.append("😴 No new 13F filings in this window (between filing seasons).")

    held = [f"{html.escape(c['ticker'])} ({c['holder_count']})" for c in
            sorted(conviction, key=lambda c: c.get("holder_count", 0), reverse=True)
            if c.get("ticker") not in (None, "", "UNKNOWN")][:6]
    if held:
        lines += ["", f"<b>🏆 Most held now</b> (of {len(summary)} investors): " + ", ".join(held)]

    deadline, qtr = next_deadline(today)
    filed = sum(1 for s in summary if s.get("latest_quarter") == qtr)
    days = (deadline - today).days
    lines += ["", f"⏳ Next 13F deadline: <b>{deadline:%d %b %Y}</b> for {qtr} ({days} days)"
                  + (f" · {filed}/{len(summary)} filed early" if filed else "")]
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
        return False
    data = urllib.parse.urlencode({"chat_id": chat, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage",
                                    data=data, timeout=30) as r:
            ok = bool(json.loads(r.read()).get("ok"))
        print("Telegram sent." if ok else "Telegram returned ok=false")
        return ok
    except Exception as exc:  # never fail the workflow over a notification
        # don't print exc verbatim: urllib errors can include the URL (token)
        print(f"::warning::Telegram send failed: {type(exc).__name__} {getattr(exc, 'code', '')}")
        return False


def main():
    if "--test" in sys.argv:
        send(f"✅ Uber Invest alerts are connected.\n🔗 {DASHBOARD}")
        return
    today = dt.datetime.now(IST).date()
    try:
        last = dt.date.fromisoformat(json.loads(STATE.read_text(encoding="utf-8"))["last_digest"])
    except (FileNotFoundError, KeyError, ValueError):
        last = None
    since = last or today - dt.timedelta(days=DIGEST_DAYS)

    force, dry = "--force" in sys.argv, "--dry-run" in sys.argv
    if not (force or dry) and last and (today - last).days < DIGEST_DAYS:
        print(f"Last digest {last}; next due {last + dt.timedelta(days=DIGEST_DAYS)} -- nothing to do.")
        return

    msg = build_digest(since, today)
    print(msg)
    if dry:
        return
    if send(msg):
        STATE.write_text(json.dumps({"last_digest": today.isoformat()}, indent=2) + "\n",
                         encoding="utf-8")


if __name__ == "__main__":
    main()
