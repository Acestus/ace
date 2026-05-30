#!/usr/bin/env python3
"""tl — 3-lane time log.

Tracks up to 3 concurrent timers (one per swim lane) and writes to today's
planner org file.

Usage:
    tl.py                        Show running timers with elapsed time
    tl.py start <PROJECT>-123        Start timer for a ticket
    tl.py stop <PROJECT>-123         Stop timer, write duration to org Time Log
    tl.py status                 Same as bare tl.py
    tl.py summary                Show today's work rollup (total hours, by ticket)
    tl.py away [reason]          Pause all timers (lunch / break / research / …)
    tl.py back                   Resume all paused timers
"""

import argparse
import json
import os
import re
import sys
import urllib.request
import base64
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail

PROJECTS_DIR = Path("/home/wweeks/git/projects")
TIMERS_FILE = PROJECTS_DIR / "planner" / ".timers.json"
AWAY_FILE   = PROJECTS_DIR / "planner" / ".away.json"
TODAY = date.today().strftime("%m-%d")
ORG_FILE = PROJECTS_DIR / "planner" / f"{TODAY}.org"

LANE_EMOJIS = {"urgent": "🔴", "manual": "🔵", "background": "🟢"}


def load_env():
    """Load .env file into os.environ if not already set."""
    env_file = PROJECTS_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key not in os.environ:
            os.environ[key] = value


def read_timers() -> dict:
    """Read timers JSON; return empty dict if file missing or empty."""
    if TIMERS_FILE.exists() and TIMERS_FILE.stat().st_size > 0:
        try:
            return json.loads(TIMERS_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def write_timers(data: dict):
    """Write timers dict to state file."""
    TIMERS_FILE.write_text(json.dumps(data, indent=2) + "\n")


def elapsed_seconds(start_iso: str) -> int:
    """Seconds between an ISO timestamp and now."""
    start = datetime.fromisoformat(start_iso)
    return int((datetime.now() - start).total_seconds())


def format_duration(secs: int) -> str:
    """Human-readable duration (e.g. '1h 23m' or '45m')."""
    h, rem = divmod(secs, 3600)
    m = rem // 60
    if h > 0 and m > 0:
        return f"{h}h {m}m"
    elif h > 0:
        return f"{h}h"
    return f"{m}m"


def format_jira(secs: int) -> str:
    """Jira-format duration (e.g. '1h30m')."""
    h, rem = divmod(secs, 3600)
    m = rem // 60
    if h > 0 and m > 0:
        return f"{h}h{m}m"
    elif h > 0:
        return f"{h}h"
    return f"{m}m"


def detect_lane(ticket: str) -> str:
    """Detect lane from Jira labels. Falls back to 'manual'."""
    load_env()
    email = os.environ.get("CONFLUENCE_EMAIL", "")
    token = os.environ.get("WWEEKS_CONFLUENCE_API_TOKEN", "")
    if not email or not token:
        return "manual"

    auth = base64.b64encode(f"{email}:{token}".encode()).decode()
    url = f"https://<YOUR_ATLASSIAN>.atlassian.net/rest/api/3/issue/{ticket}?fields=labels"
    req = urllib.request.Request(
        url, headers={"Authorization": f"Basic {auth}", "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            labels = json.load(r)["fields"]["labels"]
    except Exception:
        return "manual"

    urgency = next(
        (int(l.split(":")[1]) for l in labels if l.startswith("urgency:")), 5
    )
    agentic = next(
        (int(l.split(":")[1]) for l in labels if l.startswith("agentic:")), 3
    )
    importance = next(
        (int(l.split(":")[1]) for l in labels if l.startswith("importance:")), 3
    )

    if urgency <= 2:
        return "urgent"
    elif agentic >= 4 and importance <= 3:
        return "manual"
    elif agentic <= 2:
        return "background"
    return "manual"


def fetch_summary(ticket: str) -> str:
    """Fetch ticket summary from Jira. Falls back to ticket key."""
    load_env()
    email = os.environ.get("CONFLUENCE_EMAIL", "")
    token = os.environ.get("WWEEKS_CONFLUENCE_API_TOKEN", "")
    if not email or not token:
        return ticket

    auth = base64.b64encode(f"{email}:{token}".encode()).decode()
    url = f"https://<YOUR_ATLASSIAN>.atlassian.net/rest/api/3/issue/{ticket}?fields=summary"
    req = urllib.request.Request(
        url, headers={"Authorization": f"Basic {auth}", "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.load(r)["fields"]["summary"]
    except Exception:
        return ticket


def format_org_row(start, end, key, summary, duration, jira):
    """Format a time log row with fixed-width columns for org-mode alignment."""
    return (
        f"| {start:<5} "
        f"| {end:<5} "
        f"| {key:<9} "
        f"| {summary:<62} "
        f"| {duration:<8} "
        f"| {jira:<5} |\n"
    )


def append_org_row(ticket: str, start_hhmm: str, summary: str):
    """Append a row to the Time Log in today's org file."""
    if not ORG_FILE.exists():
        print(f"Org file not found: {ORG_FILE} — run 'dn' first.", file=sys.stderr)
        return

    content = ORG_FILE.read_text()
    new_row = format_org_row(start_hhmm, "", ticket, summary[:62], "active", "")

    if "* Time Log" in content:
        lines = content.splitlines(keepends=True)
        last_table_line = -1
        in_timelog = False
        for i, line in enumerate(lines):
            if "* Time Log" in line:
                in_timelog = True
            if in_timelog and line.strip().startswith("|"):
                last_table_line = i
            if in_timelog and last_table_line >= 0 and not line.strip().startswith("|") and i > last_table_line:
                break
        if last_table_line >= 0:
            lines.insert(last_table_line + 1, new_row)
            ORG_FILE.write_text("".join(lines))
        else:
            ORG_FILE.write_text(content + "\n" + new_row)
    else:
        header = format_org_row("Start", "End", "Key", "Summary", "Duration", "Jira")
        separator = (
            "|-------"
            "|-------"
            "|-----------"
            "|----------------------------------------------------------------"
            "|----------"
            "|-------|\n"
        )
        section = (
            f"\n* Time Log — {date.today().strftime('%Y-%m-%d')}\n"
            "# Append-only. tl start/stop manages rows here.\n\n"
            + header
            + separator
            + new_row
        )
        ORG_FILE.write_text(content + section)


def close_org_row(ticket: str, end_hhmm: str, duration_human: str, duration_jira: str):
    """Fill in End + Duration for a running row."""
    if not ORG_FILE.exists():
        return

    content = ORG_FILE.read_text()
    # Match the row with this ticket that has "active" in the duration column
    pattern = (
        r'(\| \d{2}:\d{2}) \| {5} (\| '
        + re.escape(ticket)
        + r'\s*\|.*?\|) active\s*\|[^|]*\|'
    )

    def replacement(m):
        return format_org_row(
            m.group(1).strip("| "),
            end_hhmm,
            ticket,
            "",  # placeholder — will be replaced below
            duration_human,
            duration_jira,
        ).rstrip("\n")

    # Simpler approach: find the active row for this ticket and rebuild it
    lines = content.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if f"| {ticket}" in line and "active" in line:
            # Parse out the summary from the existing row
            parts = [p.strip() for p in line.split("|")]
            # parts: ['', start, end, key, summary, duration, jira, '']
            if len(parts) >= 7:
                summary = parts[4] if len(parts) > 4 else ""
                lines[i] = format_org_row(
                    parts[1], end_hhmm, ticket, summary, duration_human, duration_jira
                )
            break
    ORG_FILE.write_text("".join(lines))


def cmd_status():
    """Show running timers."""
    timers = read_timers()
    if not timers:
        print("⏱  No timers running.")
        return

    print("⏱  Running timers:")
    for ticket, info in timers.items():
        start = datetime.fromisoformat(info["start"])
        secs = int((datetime.now() - start).total_seconds())
        duration = format_duration(secs)
        lane = info.get("lane", "manual")
        emoji = LANE_EMOJIS.get(lane, "⚪")
        print(f"  {emoji}  {ticket}  —  {duration} (since {start.strftime('%H:%M')})")


def cmd_start(ticket: str):
    """Start a timer for a ticket."""
    if not ticket:
        fail("Usage: tl.py start <PROJECT>-123")

    ticket = ticket.upper()
    timers = read_timers()

    if ticket in timers:
        start_time = timers[ticket]["start"][11:16]
        print(f"⚠  Timer already running for {ticket} (since {start_time})")
        return

    print(f"🔍 Detecting lane for {ticket}...")
    lane = detect_lane(ticket)
    emoji = LANE_EMOJIS.get(lane, "⚪")

    summary = fetch_summary(ticket)

    start_iso = datetime.now().isoformat(timespec="seconds")
    start_hhmm = datetime.now().strftime("%H:%M")

    timers[ticket] = {"lane": lane, "start": start_iso}
    write_timers(timers)

    append_org_row(ticket, start_hhmm, summary)
    print(f"{emoji}  Timer started — {ticket} ({lane}) at {start_hhmm}")


def cmd_stop(ticket: str):
    """Stop a timer and log duration."""
    if not ticket:
        fail("Usage: tl.py stop <PROJECT>-123")

    ticket = ticket.upper()
    timers = read_timers()

    if ticket not in timers:
        fail(f"No running timer for {ticket}",
             try_=["tl.py status  # see running timers"])

    info = timers[ticket]
    lane = info.get("lane", "manual")
    emoji = LANE_EMOJIS.get(lane, "⚪")

    secs = elapsed_seconds(info["start"])
    end_hhmm = datetime.now().strftime("%H:%M")
    duration_human = format_duration(secs)
    duration_jira = format_jira(secs)

    close_org_row(ticket, end_hhmm, duration_human, duration_jira)

    del timers[ticket]
    write_timers(timers)

    print(f"{emoji}  Timer stopped — {ticket}")
    print(f"   Duration : {duration_human} ({duration_jira} Jira format)")
    print(f"   Use in worklog: WORKLOG {duration_jira}: ...")


def cmd_summary():
    """Show today's work rollup."""
    if not ORG_FILE.exists():
        fail(f"No planner file for today ({TODAY}.org)",
             try_=["python3 scripts/daily_note.py --start"])

    content = ORG_FILE.read_text()
    rows = re.findall(
        r'^\|\s*(\d{2}:\d{2})\s*\|\s*(\d{2}:\d{2})?\s*\|\s*([A-Z]+-\d+)\s*\|\s*(.+?)\s*\|\s*([^|]*)\s*\|\s*([^|]*)\s*\|',
        content, re.MULTILINE,
    )

    if not rows:
        print("📋  No time logged today yet.")
        return

    tickets: dict = defaultdict(lambda: {"summary": "", "minutes": 0, "worklog_h": 0.0})

    for start, end, key, summary, duration, worklog in rows:
        tickets[key]["summary"] = summary.strip()[:50]
        dur = duration.strip().lstrip("~")
        mins = 0
        if "h" in dur and "m" in dur:
            parts = re.match(r'(\d+(?:\.\d+)?)h\s*(\d+)m', dur)
            if parts:
                mins = int(float(parts.group(1)) * 60) + int(parts.group(2))
        elif "h" in dur:
            mins = int(float(dur.replace("h", "")) * 60)
        elif "m" in dur:
            mins = int(dur.replace("m", ""))
        tickets[key]["minutes"] += mins

        wl = worklog.strip()
        if wl:
            try:
                tickets[key]["worklog_h"] += float(wl.replace("h", ""))
            except ValueError:
                pass

    total_mins = sum(t["minutes"] for t in tickets.values())
    total_worklog = sum(t["worklog_h"] for t in tickets.values())

    print(f"📋  Today's Work — {total_mins // 60}h {total_mins % 60}m tracked, {total_worklog:.1f}h logged to Jira")
    print("─" * 60)

    for key, info in tickets.items():
        h, m = divmod(info["minutes"], 60)
        dur_str = f"{h}h {m}m" if h else f"{m}m"
        wl_str = f" (logged {info['worklog_h']:.1f}h)" if info["worklog_h"] > 0 else ""
        print(f"  {key:12s}  {dur_str:>6s}{wl_str}  {info['summary']}")

    # Show running timers
    timers = read_timers()
    if timers:
        print("\n⏱  Still running:")
        for ticket, info in timers.items():
            start = datetime.fromisoformat(info["start"])
            secs = int((datetime.now() - start).total_seconds())
            dur = format_duration(secs)
            print(f"  {ticket:12s}  {dur:>6s}  (since {start.strftime('%H:%M')})")


def cmd_away(reason: str):
    """Pause all running timers. Saves state for 'back' to resume."""
    timers = read_timers()
    if not timers:
        label = reason or "away"
        print(f"⏸  No timers running — enjoy your {label}.")
        return

    now_hhmm = datetime.now().strftime("%H:%M")
    now_iso   = datetime.now().isoformat(timespec="seconds")
    reason    = reason or "break"

    # Stop each timer and close its org row
    paused = []
    for ticket, info in timers.items():
        lane  = info.get("lane", "manual")
        secs  = elapsed_seconds(info["start"])
        close_org_row(ticket, now_hhmm, format_duration(secs), format_jira(secs))
        paused.append({"key": ticket, "lane": lane})

    # Save away state
    AWAY_FILE.write_text(json.dumps({
        "reason":     reason,
        "away_since": now_iso,
        "tickets":    paused,
    }, indent=2) + "\n")

    write_timers({})

    names = ", ".join(p["key"] for p in paused)
    print(f"⏸  Away ({reason}) — {len(paused)} timer(s) paused at {now_hhmm}")
    print(f"   {names}")


def cmd_back():
    """Resume all timers that were paused with 'away'."""
    if not AWAY_FILE.exists():
        print("⚠  No paused session found. Use 'tl.py away <reason>' before stepping away.")
        return

    state     = json.loads(AWAY_FILE.read_text())
    reason    = state.get("reason", "break")
    away_since = state.get("away_since", "")[:16].replace("T", " ")
    tickets   = state.get("tickets", [])

    if not tickets:
        AWAY_FILE.unlink(missing_ok=True)
        print("⚠  Away file had no tickets. Nothing to resume.")
        return

    now_hhmm = datetime.now().strftime("%H:%M")
    now_iso   = datetime.now().isoformat(timespec="seconds")
    timers    = read_timers()

    resumed = []
    for entry in tickets:
        key  = entry["key"]
        lane = entry.get("lane", "manual")
        if key in timers:
            continue  # already running (shouldn't happen, but be safe)
        summary = fetch_summary(key)
        timers[key] = {"lane": lane, "start": now_iso}
        append_org_row(key, now_hhmm, summary)
        resumed.append(key)

    write_timers(timers)
    AWAY_FILE.unlink(missing_ok=True)

    names = ", ".join(resumed)
    print(f"▶  Back from {reason} (was away since {away_since})")
    print(f"   Resumed: {names}")


def main():
    parser = argparse.ArgumentParser(description="3-lane time log")
    parser.add_argument("command", nargs="?", default="status",
                        choices=["start", "stop", "status", "summary", "away", "back"])
    parser.add_argument("ticket", nargs="?", default="",
                        help="Ticket key (start/stop) or away reason (away)")
    args = parser.parse_args()

    if args.command == "start":
        cmd_start(args.ticket)
    elif args.command == "stop":
        cmd_stop(args.ticket)
    elif args.command == "summary":
        cmd_summary()
    elif args.command == "away":
        cmd_away(args.ticket)
    elif args.command == "back":
        cmd_back()
    else:
        cmd_status()


if __name__ == "__main__":
    main()
