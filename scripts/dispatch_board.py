#!/usr/bin/env python3
"""
dispatch_board.py — Refresh the daily Kanban Board from Jira.

Deterministic logic:
  1. Load .env credentials
  2. Fetch flow:active tickets from Jira (or use --active override)
  3. Classify each ticket into a lane (urgent / manual / background)
  4. Enforce WIP: keep one per lane; demote extras → flow:queue in Jira
  5. Rebuild the * Kanban Board section in today's daily org note
  6. Preserve * Time Log, * Standup, and * Notes untouched
  7. Auto-start timers for newly active tickets (unless --no-timers)

Usage (AI calls this with parameters):
  python3 scripts/dispatch_board.py                    # full Jira refresh
  python3 scripts/dispatch_board.py --dry-run          # preview, no writes
  python3 scripts/dispatch_board.py --date 2026-05-30  # specific date
  python3 scripts/dispatch_board.py --active <PROJECT>-60 <PROJECT>-406
                                                       # skip Jira fetch, use these keys
  python3 scripts/dispatch_board.py --json             # machine-readable output
  python3 scripts/dispatch_board.py --no-timers        # skip timer auto-start
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import require_env


# ── Constants ────────────────────────────────────────────────────────────────

JIRA_BASE = "https://<YOUR_ATLASSIAN>.atlassian.net"

LANE_ORDER  = {"urgent": 0, "manual": 1, "manual2": 1, "background": 2}
LANE_EMOJI  = {"urgent": "🔴", "manual": "🟠", "manual2": "🟠", "background": "🟡"}
LANE_LABEL  = {"urgent": "Urgent",       "manual": "Manual",        "manual2": "Manual",        "background": "Background"}
LANE_TIMES  = {"urgent": ("07:00","08:00"), "manual": ("09:00","10:00"), "manual2": ("11:00","12:00"), "background": ("13:00","14:00")}
LANE_HOUR   = {"urgent": 7,               "manual": 9,               "manual2": 11,              "background": 13}
# Lane number shown in the org heading: most hands-on → Lane 1
LANE_NUM    = {"urgent": 1, "manual": 2, "manual2": 2, "background": 3}

SCORE_EMOJI = {1: "🟢", 2: "🔵", 3: "🟡", 4: "🟠", 5: "🔴"}

DEFAULT_STANDUP = [
    "* Standup", "",
    "** ✅ Completed Today",
    "- (to be filled at end of day)",
    "",
    "** ⏳ Waiting On",
    "- (to be filled at end of day)",
    "",
    "** 🚫 Blockers",
    "- None",
    "",
    "** 📅 Active / Up Next",
    "- (to be filled at end of day)",
]


# ── Credentials ──────────────────────────────────────────────────────────────

def load_env(projects_dir: Path) -> dict:
    """Parse .env and return a dict of key→value."""
    env_file = projects_dir / ".env"
    result = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', k):
                result[k] = v.strip()
    return result


def make_auth(env: dict) -> str:
    email = env.get("CONFLUENCE_EMAIL") or os.environ.get("CONFLUENCE_EMAIL", "")
    token = env.get("WWEEKS_CONFLUENCE_API_TOKEN") or os.environ.get("WWEEKS_CONFLUENCE_API_TOKEN", "")
    os.environ.setdefault("CONFLUENCE_EMAIL", email)
    os.environ.setdefault("WWEEKS_CONFLUENCE_API_TOKEN", token)
    require_env(
        "CONFLUENCE_EMAIL", "WWEEKS_CONFLUENCE_API_TOKEN",
        hint="Add them to .env at the repo root",
        env_file=str(Path(__file__).parent.parent / ".env"),
    )
    return base64.b64encode(f"{email}:{token}".encode()).decode()


# ── Jira API ─────────────────────────────────────────────────────────────────

def jira_request(method: str, path: str, auth: str, body=None) -> dict:
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(JIRA_BASE + path, data=data, method=method)
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Accept", "application/json")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Jira {method} {path} → {e.code}: {e.read().decode()[:300]}")


def fetch_active(auth: str) -> list:
    return jira_request("POST", "/rest/api/3/search/jql", auth, {
        "jql": 'project = INFRA AND labels = "flow:active" ORDER BY created ASC',
        "fields": ["key", "summary", "labels"],
        "maxResults": 20,
    }).get("issues", [])


def fetch_issue(key: str, auth: str) -> dict:
    return jira_request("GET", f"/rest/api/3/issue/{key}?fields=key,summary,labels", auth)


def set_flow_label(key: str, remove_label: str, add_label: str, auth: str) -> None:
    jira_request("PUT", f"/rest/api/3/issue/{key}", auth, {
        "update": {"labels": [{"remove": remove_label}, {"add": add_label}]}
    })


# ── Lane classification ───────────────────────────────────────────────────────

def parse_scores(labels: list) -> dict:
    nums = {}
    for lbl in labels:
        for p in ("urgency", "importance", "agentic"):
            if lbl.startswith(p + ":"):
                try:
                    nums[p] = int(lbl.split(":")[1])
                except ValueError:
                    pass
    return nums


def classify(labels: list) -> str:
    s = parse_scores(labels)
    u = s.get("urgency", 5)
    a = s.get("agentic", 3)
    if u <= 2:   return "urgent"
    if a <= 2:   return "background"
    return "manual"


def priority_score(issue: dict) -> tuple:
    """Lower = higher priority. U+I sum, then key number as tiebreak."""
    s = parse_scores(issue["fields"]["labels"])
    ui  = s.get("urgency", 5) + s.get("importance", 5)
    num = int(issue["key"].split("-")[1])
    return (ui, num)


# ── WIP enforcement ──────────────────────────────────────────────────────────

def enforce_wip(issues: list, auth: str, dry_run: bool) -> tuple[dict, list]:
    """
    Returns (keep, demoted).
      keep    = {lane_key → issue} — one winner per lane
      demoted = [issue, ...]       — extras pushed to flow:queue
    """
    lanes = {"urgent": [], "manual": [], "background": []}
    for issue in issues:
        lanes[classify(issue["fields"]["labels"])].append(issue)

    keep   = {}
    demote = []

    for lane in ("urgent", "manual", "background"):
        ranked = sorted(lanes[lane], key=priority_score)
        if ranked:
            keep[lane] = ranked[0]
            demote.extend(ranked[1:])

    # Urgent slot empty → promote second-best manual ticket
    if "urgent" not in keep and len(lanes["manual"]) >= 2:
        ranked = sorted(lanes["manual"], key=priority_score)
        keep["manual2"] = ranked[1]
        demote = [t for t in demote if t["key"] != ranked[1]["key"]]

    for t in demote:
        key = t["key"]
        if not dry_run:
            try:
                set_flow_label(key, "flow:active", "flow:queue", auth)
            except Exception as e:
                print(f"⚠️  Could not demote {key}: {e}", file=sys.stderr)

    return keep, demote


# ── Issue file helpers ────────────────────────────────────────────────────────

def issue_file_path(key: str, issues_dir: Path) -> Path | None:
    matches = list(issues_dir.glob(f"{key} - */{key} - *.md"))
    return matches[0] if matches else None


def next_action(key: str, issues_dir: Path) -> str:
    path = issue_file_path(key, issues_dir)
    if path:
        for line in path.read_text().splitlines():
            if line.strip().startswith("- [ ]"):
                return line.strip()[6:].strip()
    return "Review issue and plan next action"


def agentic_tag(labels: list) -> str:
    """'{🟡 AGENTIC-3}' from the ticket's agentic label. Defaults to 3."""
    for lbl in labels:
        if lbl.startswith("agentic:"):
            try:
                n = int(lbl.split(":")[1])
                return f"{{{SCORE_EMOJI.get(n, '⚪')} AGENTIC-{n}}}"
            except ValueError:
                pass
    return f"{{{SCORE_EMOJI[3]} AGENTIC-3}}"


# ── Org section builders ──────────────────────────────────────────────────────

def slot_is_future(lane: str, now: datetime) -> bool:
    slot = now.replace(hour=LANE_HOUR[lane], minute=0, second=0, microsecond=0)
    return now < slot


def sched_stamp(lane: str, key: str, now: datetime, full_date: str, dow: str,
                past_scheduled: dict) -> str:
    start, end = LANE_TIMES[lane]
    if slot_is_future(lane, now):
        return f"<{full_date} {dow} {start}-{end}>"
    return past_scheduled.get(key, f"<{full_date} {dow} {start}-{end}>")


def build_board_section(active: list, issues_dir: Path, now: datetime,
                        full_date: str, dow: str, past_scheduled: dict) -> list:
    lines = [
        f"* Kanban Board — WIP: {len(active)}/5",
        "# Dispatcher always rewrites this section. Status board, not a calendar.",
        "",
    ]
    for lane, t in active:
        key   = t["key"]
        fpath = issue_file_path(key, issues_dir)
        link  = f"[[file:{fpath}][{key}]]" if fpath else key
        tag   = agentic_tag(t["fields"]["labels"])
        stamp = sched_stamp(lane, key, now, full_date, dow, past_scheduled)
        na    = next_action(key, issues_dir)
        lines += [
            f"** Lane {LANE_NUM[lane]}",
            f"*** TODO {link} — {t['fields']['summary']} {tag}",
            f"    SCHEDULED: {stamp}",
            f"    :NEXT: {na}",
            "",
        ]
    return lines


def extract_section(lines: list, start_pattern: str) -> list:
    """Extract one top-level org section (from matching heading to next `* ` heading)."""
    section, capturing = [], False
    for line in lines:
        if re.match(start_pattern, line):
            capturing = True
        elif capturing and re.match(r'^\* ', line):
            break
        if capturing:
            section.append(line)
    return section


def parse_past_scheduled(raw: str) -> dict:
    """Read existing SCHEDULED stamps keyed by Jira ticket key."""
    past = {}
    # Match both file links [[file:...][KEY]] and Jira URL links [[https://.../KEY]]
    for m in re.finditer(r'\[\[(?:file:[^\]]*|https://[^\]]+/browse)/([A-Z]+-\d+)\]\]?', raw):
        key     = m.group(1)
        snippet = raw[m.start(): m.start() + 300]
        sm      = re.search(r'SCHEDULED: (<[^>]+>)', snippet)
        if sm:
            past[key] = sm.group(1)
    return past


def rebuild_org(org_file: Path, board_lines: list, full_date: str) -> str:
    """Reconstruct the full org file content. Returns new content string."""
    raw_lines = org_file.read_text().splitlines() if org_file.exists() \
                else [f"#+title: Daily Note", f"#+date: {full_date}"]

    header   = [l for l in raw_lines if l.startswith("#+")]
    time_log = extract_section(raw_lines, r'^\* Time Log')
    standup  = extract_section(raw_lines, r'^\* Standup') or DEFAULT_STANDUP
    notes    = extract_section(raw_lines, r'^\* Notes') or ["* Notes", ""]

    sections = header + [""]
    if time_log:
        sections += time_log + [""]
    sections += board_lines + [""] + standup + [""] + notes

    return "\n".join(sections) + "\n"


# ── Timer auto-start ─────────────────────────────────────────────────────────

def auto_start_timers(active_keys: set, projects_dir: Path) -> None:
    tl_script   = projects_dir / "scripts" / "tl"
    timers_file = projects_dir / "planner" / ".timers.json"

    if not tl_script.exists():
        return

    running = set()
    if timers_file.exists():
        try:
            running = set(json.loads(timers_file.read_text()).keys())
        except (json.JSONDecodeError, OSError):
            pass

    for key in sorted(active_keys - running):
        subprocess.run([str(tl_script), "start", key], capture_output=True)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Refresh the daily Kanban Board in today's org note from Jira.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--projects-dir", type=Path,
                        default=Path(__file__).resolve().parent.parent,
                        help="Path to the projects repo root (default: auto-detect)")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"),
                        help="Date for the org file (default: today, YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would change without writing anything")
    parser.add_argument("--active", nargs="+", metavar="KEY",
                        help="Override Jira: treat these keys as the active set (no Jira fetch)")
    parser.add_argument("--no-timers", action="store_true",
                        help="Skip timer auto-start")
    parser.add_argument("--json", dest="json_out", action="store_true",
                        help="Machine-readable JSON output (for AI/script callers)")
    args = parser.parse_args()

    projects_dir = args.projects_dir.resolve()
    issues_dir   = projects_dir / "issues"

    now      = datetime.now()
    dt       = datetime.strptime(args.date, "%Y-%m-%d")
    dow      = dt.strftime("%a")
    mmdd     = dt.strftime("%m-%d")
    org_file = projects_dir / "planner" / f"{mmdd}.org"

    env  = load_env(projects_dir)
    auth = make_auth(env)

    # ── 1. Get active issues ─────────────────────────────────────────────────
    if args.active:
        issues = []
        for key in args.active:
            try:
                issue = fetch_issue(key, auth)
                issues.append({
                    "key": issue["key"],
                    "fields": {
                        "summary": issue["fields"]["summary"],
                        "labels":  issue["fields"]["labels"],
                    }
                })
            except Exception as e:
                print(f"⚠️  Could not fetch {key}: {e}", file=sys.stderr)
    else:
        issues = fetch_active(auth)

    # ── 2. Enforce WIP ───────────────────────────────────────────────────────
    keep, demoted = enforce_wip(issues, auth, dry_run=args.dry_run or bool(args.active))

    active = sorted(keep.items(), key=lambda kv: LANE_ORDER[kv[0]])

    # ── 3. Read past SCHEDULED stamps ────────────────────────────────────────
    past_scheduled = parse_past_scheduled(org_file.read_text()) if org_file.exists() else {}

    # ── 4. Build board section ───────────────────────────────────────────────
    board_lines = build_board_section(active, issues_dir, now, args.date, dow, past_scheduled)

    # ── 5. Write org file ────────────────────────────────────────────────────
    new_content = rebuild_org(org_file, board_lines, args.date)

    if args.dry_run:
        print("\n── dry-run: would write ──")
        for line in board_lines:
            print(" ", line)
    else:
        org_file.parent.mkdir(parents=True, exist_ok=True)
        org_file.write_text(new_content)

    # ── 6. Auto-start timers ─────────────────────────────────────────────────
    if not args.no_timers and not args.dry_run:
        auto_start_timers({t["key"] for _, t in active}, projects_dir)

    # ── 7. Output ────────────────────────────────────────────────────────────
    if args.json_out:
        result = {
            "org_file": str(org_file),
            "date": args.date,
            "wip": len(active),
            "active": [
                {
                    "key":      t["key"],
                    "lane":     lane,
                    "lane_num": LANE_NUM[lane],
                    "summary":  t["fields"]["summary"],
                    "tag":      agentic_tag(t["fields"]["labels"]),
                    "next":     next_action(t["key"], issues_dir),
                }
                for lane, t in active
            ],
            "demoted": [t["key"] for t in demoted],
            "dry_run": args.dry_run,
        }
        print(json.dumps(result, indent=2))
    elif args.dry_run:
        print("── dry-run: board would show ──")
        for lane, t in active:
            print(f"\n  {LANE_EMOJI[lane]} Lane {LANE_NUM[lane]}  {t['key']} — {t['fields']['summary']}")
            print(f"     Next: {next_action(t['key'], issues_dir)}")
    else:
        if not active:
            print("No active tickets.")
            return
        for lane, t in active:
            na = next_action(t["key"], issues_dir)
            print(f"{LANE_EMOJI[lane]} {t['key']} — {t['fields']['summary']}")
            print(f"   Next: {na}")
            print()


if __name__ == "__main__":
    main()
