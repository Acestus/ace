#!/usr/bin/env python3
"""
daily_note.py — Create and close daily planning notes in planner/MM-DD.org.

Modes:
    --start   Create today's note (or refresh if it exists) with active board
    --refresh Re-query Jira and update the Kanban Board section in today's note
    --end     Close the day: build standup section, print Teams message, commit+push
    --standup Print the standup message only (no file write)

Usage:
    python3 scripts/daily_note.py --start
    python3 scripts/daily_note.py --refresh
    python3 scripts/daily_note.py --end
    python3 scripts/daily_note.py --end --blocker "<PROJECT>-342: waiting for <USER_C>"
    python3 scripts/daily_note.py --standup

Environment (reads from .env if not already set):
    CONFLUENCE_EMAIL
    WWEEKS_CONFLUENCE_API_TOKEN
    TEAMS_WEBHOOK_URL   (optional — posts standup to Teams if set)
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, CONFLUENCE_COMMON_CAUSES

JIRA_BASE   = "https://<YOUR_ATLASSIAN>.atlassian.net"
JIRA_BROWSE = "https://<YOUR_ATLASSIAN>.atlassian.net/browse"
PROJECTS    = Path(__file__).parent.parent
PLANNER     = PROJECTS / "planner"
ISSUES      = PROJECTS / "issues"
CASES       = PROJECTS / "cases"

LANE_EMOJI  = {"lane1": "🔴", "lane2": "🟠", "lane3": "🟡", "lane4": "🔵", "lane5": "🟢"}
LANE_LABEL  = {"lane1": "Agentic-5", "lane2": "Agentic-4", "lane3": "Agentic-3", "lane4": "Agentic-2", "lane5": "Agentic-1"}
CLAIMS_FILE = Path("/tmp/rounds-claims.json")


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

def load_env_file():
    env_path = PROJECTS / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() not in os.environ:
            os.environ[k.strip()] = v.strip()


def auth_header():
    email = require_env("CONFLUENCE_EMAIL",
                        hint="cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)")
    token = require_env("WWEEKS_CONFLUENCE_API_TOKEN",
                        hint="cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)")
    return "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()


# ---------------------------------------------------------------------------
# Jira helpers
# ---------------------------------------------------------------------------

def jira_search(jql: str, fields: list[str], auth: str, max_results: int = 50) -> list[dict]:
    payload = json.dumps({"jql": jql, "fields": fields, "maxResults": max_results}).encode()
    req = urllib.request.Request(
        f"{JIRA_BASE}/rest/api/3/search/jql",
        data=payload,
        headers={"Authorization": auth, "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read()).get("issues", [])
    except urllib.error.HTTPError as e:
        print(f"  WARN: Jira search failed {e.code} — {e.read().decode()[:200]}", file=sys.stderr)
        return []


def label_score(labels: list[str], prefix: str) -> int:
    for lbl in labels:
        if lbl.startswith(f"{prefix}:"):
            try:
                return int(lbl.split(":")[1])
            except ValueError:
                pass
    return 99


def classify_lane(labels: list[str]) -> str:
    """Return lane key (lane1–lane5) based on agentic score.
    Lane 1 = agentic:5 (most manual/hot), Lane 5 = agentic:1 (most autonomous).
    Soft guideline — any ticket can go in any lane."""
    agentic = label_score(labels, "agentic")
    if agentic == 99:
        return "lane1"  # default to hot lane if no score
    score = min(max(agentic, 1), 5)
    return f"lane{6 - score}"  # agentic:5→lane1, agentic:4→lane2, ..., agentic:1→lane5


def flow_label(labels: list[str]) -> str:
    for lbl in labels:
        if lbl.startswith("flow:"):
            return lbl
    return ""


# ---------------------------------------------------------------------------
# Issue file helpers
# ---------------------------------------------------------------------------

def find_next_step(key: str) -> str:
    if not ISSUES.exists():
        return ""
    for folder in ISSUES.iterdir():
        if folder.name.startswith(f"{key} ") or folder.name == key:
            md = folder / f"{folder.name}.md"
            if md.exists():
                for line in md.read_text().splitlines():
                    if re.match(r"^\s*-\s+\[ \]", line):
                        return re.sub(r"^\s*-\s+\[ \]\s*", "", line).strip()
    return ""


def find_issue_file(key: str) -> Path | None:
    """Return the absolute path to the issue markdown file for *key*, or None."""
    if not ISSUES.exists():
        return None
    for folder in ISSUES.iterdir():
        if folder.is_dir() and (folder.name.startswith(f"{key} ") or folder.name == key):
            md = folder / f"{folder.name}.md"
            if md.exists():
                return md
    return None


def _sdp_classify_lane(header: dict) -> str:
    """Classify an SDP case into a lane key (lane1–lane5) based on agentic score.
    An explicit **Lane:** header value of lane1–lane5 wins; otherwise derive from agentic score."""
    explicit = header.get("lane", "").strip().lower()
    if explicit in ("lane1", "lane2", "lane3", "lane4", "lane5"):
        return explicit
    # Legacy values — map to new keys
    if explicit == "sdp_urgent":
        return "lane1"
    if explicit == "sdp_approval":
        return "lane2"
    if explicit == "sdp_background":
        return "lane5"

    def _int(key: str, default: int = 3) -> int:
        try:
            return int(header.get(key, default))
        except (ValueError, TypeError):
            return default

    agentic = _int("agentic", 4)
    score = min(max(agentic, 1), 5)
    return f"lane{6 - score}"  # agentic:5→lane1, agentic:4→lane2, ..., agentic:1→lane5


def scan_sdp_cases(flow: str, exclude_jira_linked: bool = False) -> list[dict]:
    """Scan cases/ for SDP tickets matching a flow tag (e.g. 'flow:active').

    If exclude_jira_linked is True, skip cases that have a linked <PROJECT>- ticket
    (those are already represented in the Jira side of the board/standup).

    Returns list of dicts with keys: display_id, subject, flow, urgency, lane, path.
    """
    results = []
    if not CASES.exists():
        return results
    for case_dir in sorted(CASES.iterdir()):
        if not case_dir.is_dir():
            continue
        md_files = list(case_dir.glob("*.md"))
        if not md_files:
            continue
        md = md_files[0]
        content = md.read_text(errors="replace")
        header = {}
        for line in content.splitlines()[:25]:
            m = re.match(r"^\*{2}([A-Za-z_ ]+?):\*{2}\s*(.*)$", line)
            if m:
                header[m.group(1).strip().lower()] = m.group(2).strip()
            elif line.startswith("# "):
                header["_title"] = line[2:].strip()
        tags = header.get("tags", "")
        if flow not in tags:
            continue
        owner = header.get("owner", "sdp")
        if owner.lower() != "sdp":
            continue
        # Skip if linked to Jira (already shown on Jira side)
        if exclude_jira_linked and re.search(r"INFRA-\d+", content):
            continue
        display_id = case_dir.name
        subject = header.get("_title", "").split(" - ", 1)[-1] if " - " in header.get("_title", "") else header.get("_title", display_id)
        results.append({
            "display_id": display_id,
            "subject": subject,
            "flow": tags,
            "urgency": header.get("urgency", "Medium"),
            "lane": _sdp_classify_lane(header),
            "path": str(md),
        })
    return results


# ---------------------------------------------------------------------------
# Lane slot preferences
# ---------------------------------------------------------------------------

LANE_SLOTS = {
    "lane1": "07:00-08:00",
    "lane2": "08:00-09:00",
    "lane3": "10:00-11:00",
    "lane4": "13:00-14:00",
    "lane5": "15:00-16:00",
}


def format_scheduled(key: str, lane: str, today: date) -> str:
    dow = today.strftime("%a")
    slot = LANE_SLOTS.get(lane, "09:00-10:00")
    return f"<{today} {dow} {slot}>"


# ---------------------------------------------------------------------------
# Build sections
# ---------------------------------------------------------------------------



def _detect_key_type(key: str) -> str:
    """Return 'jira' for <PROJECT>-NNN keys, 'sdp' for numeric display IDs."""
    return "sdp" if key.isdigit() else "jira"


# Default lane slot for each claim key — overridden by a 'slot' field in the claim entry
CLAIM_KEY_DEFAULT_SLOT = {
    "lane1": "1", "lane2": "2", "lane3": "3", "lane4": "4", "lane5": "5",
    # Legacy keys — kept for backward compatibility during transition
    "urgent": "5", "manual": "4", "manual2": "4", "background": "1",
    "sdp_urgent": "5", "sdp_approval": "4", "sdp_background": "1",
}

# Time blocks per slot number
SLOT_TIMES = {
    "1": "07:00-08:00",
    "2": "08:00-09:00",
    "3": "10:00-11:00",
    "4": "13:00-14:00",
    "5": "15:00-16:00",
}


def load_lane_claims() -> dict[str, dict]:
    """Read /tmp/rounds-claims.json and return {slot: {key, type}} for slots 1–5.

    Supports both the legacy form (value is a string) and the dict form
    (value is {key, pid, claimed_at, ...}).  A 'slot' field inside the entry
    overrides the default mapping so either Jira or SDP tickets can occupy
    any of the five lanes.

    Returns e.g. {"1": {"key": "<PROJECT>-368", "type": "jira"},
                  "4": {"key": "33982",     "type": "sdp"}}.
    """
    if not CLAIMS_FILE.exists():
        return {}
    try:
        raw = json.loads(CLAIMS_FILE.read_text())
    except Exception:
        return {}

    slot_map: dict[str, dict] = {}
    for claim_key, v in raw.items():
        key_val = v if isinstance(v, str) else (v.get("key", "") if isinstance(v, dict) else "")
        if not key_val or key_val == "PENDING":
            continue
        # Explicit slot override wins; fall back to the default for this claim key
        explicit_slot = (v.get("slot") if isinstance(v, dict) else None)
        slot = str(explicit_slot) if explicit_slot else CLAIM_KEY_DEFAULT_SLOT.get(claim_key)
        if not slot:
            continue
        if slot not in slot_map:  # first claim wins for a given slot
            slot_map[slot] = {"key": key_val, "type": _detect_key_type(key_val)}
    return slot_map



def build_kanban_board(issues: list[dict], today: date,
                       sdp_active: list[dict] | None = None) -> str:
    """Render the Kanban Board org section for lanes 1–5.

    Only lanes that are explicitly claimed in /tmp/rounds-claims.json are
    shown. Unclaimed active tickets are intentionally omitted — they appear
    in the backlog sections of the daily note instead. Auto-fill was removed
    because it caused closed lanes to reappear with unrelated tickets.
    """
    dow = today.strftime("%a")

    # Build key → issue/case lookup
    jira_by_key: dict[str, dict] = {i["key"]: i for i in issues}
    sdp_by_id: dict[str, dict] = {s["display_id"]: s for s in (sdp_active or [])}

    # Populate slots from claims only — no auto-fill
    claims = load_lane_claims()
    slots: dict[str, dict | None] = {str(n): None for n in range(1, 6)}

    for slot, entry in claims.items():
        if slot not in slots:
            continue
        key = entry["key"]
        kind = entry["type"]
        if kind == "jira" and key in jira_by_key:
            slots[slot] = {"type": "jira", "data": jira_by_key[key]}
        elif kind == "sdp" and key in sdp_by_id:
            slots[slot] = {"type": "sdp", "data": sdp_by_id[key]}

    total_active = sum(1 for v in slots.values() if v is not None)
    lines = [f"* Kanban Board — WIP: {total_active}/5",
             "# Dispatcher always rewrites this section. Status board, not a calendar.", ""]

    for slot in ("1", "2", "3", "4", "5"):
        entry = slots[slot]
        if not entry:
            continue  # hide empty lanes

        slot_time = SLOT_TIMES.get(slot, "10:00-11:00")
        sched = f"<{today} {dow} {slot_time}>"
        lane_key = f"lane{slot}"
        emoji = LANE_EMOJI.get(lane_key, "⬜")
        ltag = LANE_LABEL.get(lane_key, f"Lane {slot}").upper()
        lines.append(f"** Lane {slot}")

        if entry["type"] == "jira":
            issue = entry["data"]
            fields = issue["fields"]
            key = issue["key"]
            summary = fields.get("summary", "")
            next_s = find_next_step(key)
            issue_file = find_issue_file(key)
            key_link = f"[[file:{issue_file}][{key}]]" if issue_file else key
            lines.append(f"*** TODO {key_link} — {summary} {{{emoji} {ltag}}}")
            lines.append(f"    SCHEDULED: {sched}")
            if next_s:
                lines.append(f"    :NEXT: {next_s}")

        else:  # sdp
            case = entry["data"]
            key_link = f"[[file:{case['path']}][SDP-{case['display_id']}]]"
            lines.append(f"*** TODO {key_link} — {case['subject']} {{{emoji} {ltag}}}")
            lines.append(f"    SCHEDULED: {sched}")

        lines.append("")

    return "\n".join(lines)


def build_standup_skeleton() -> str:
    return "\n".join([
        "* Standup",
        "",
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
        "",
    ])


def build_daily_note(active_issues: list[dict], today: date,
                     sdp_active: list[dict] | None = None) -> str:
    parts = [
        "#+title: Daily Note",
        f"#+date: {today}",
        "",
        f"* Time Log — {today}",
        "# Append-only. tl and worklog skill add rows here. Never overwrite past entries.",
        "",
        "| Start | End | Key | Summary | Duration | Worklog |",
        "|-------|-----|-----|---------|----------|---------|",
        "",
        "",
        build_kanban_board(active_issues, today, sdp_active=sdp_active),
        "",
        build_standup_skeleton(),
        "* Notes",
        "",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# End of day — standup content
# ---------------------------------------------------------------------------

def build_standup_content(auth: str, blockers: list[str], today: date) -> dict:
    today_str = str(today)

    completed = jira_search(
        f'project = INFRA AND labels = "flow:done" AND assignee = currentUser() '
        f'AND updated >= "{today_str}" ORDER BY updated DESC',
        ["key", "summary", "labels"], auth,
    )

    waiting = jira_search(
        'project = INFRA AND labels = "flow:waiting" AND assignee = currentUser() ORDER BY updated DESC',
        ["key", "summary", "customfield_10280"], auth,
    )

    active = jira_search(
        'project = INFRA AND labels = "flow:active" '
        'AND (assignee = currentUser() OR assignee IS EMPTY) ORDER BY priority ASC',
        ["key", "summary", "labels"], auth,
    )

    # SDP tickets from cases/ markdown
    sdp_active = scan_sdp_cases("flow:active", exclude_jira_linked=True)
    sdp_waiting = scan_sdp_cases("flow:waiting", exclude_jira_linked=True)
    sdp_done = scan_sdp_cases("flow:done", exclude_jira_linked=True)

    return {
        "completed": completed,
        "waiting":   waiting,
        "active":    active,
        "sdp_active":  sdp_active,
        "sdp_waiting": sdp_waiting,
        "sdp_done":    sdp_done,
        "blockers":  blockers,
        "date":      today,
    }


def format_standup_section(data: dict) -> str:
    lines = ["* Standup", ""]

    lines += ["** ✅ Completed Today"]
    if data["completed"]:
        for i in data["completed"]:
            lines.append(f"- {i['key']} — {i['fields'].get('summary', '')}")
    for s in data.get("sdp_done", []):
        lines.append(f"- SDP #{s['display_id']} — {s['subject']}")
    if not data["completed"] and not data.get("sdp_done"):
        lines.append("- Nothing closed today")
    lines.append("")

    lines += ["** ⏳ Waiting On"]
    if data["waiting"]:
        for i in data["waiting"]:
            next_s = i["fields"].get("customfield_10280", "") or find_next_step(i["key"]) or "pending response"
            lines.append(f"- {i['key']} — {next_s[:100]}")
    for s in data.get("sdp_waiting", []):
        lines.append(f"- SDP #{s['display_id']} — {s['subject'][:80]}")
    if not data["waiting"] and not data.get("sdp_waiting"):
        lines.append("- Nothing in waiting state")
    lines.append("")

    lines += ["** 🚫 Blockers"]
    if data["blockers"]:
        for b in data["blockers"]:
            lines.append(f"- {b}")
    else:
        lines.append("- None")
    lines.append("")

    lines += ["** 📅 Active / Up Next"]
    if data["active"]:
        for i in data["active"]:
            lane = classify_lane(i["fields"].get("labels", []))
            emoji = LANE_EMOJI.get(lane, "•")
            lines.append(f"- {emoji} {i['key']} — {i['fields'].get('summary', '')}")
    for s in data.get("sdp_active", []):
        lines.append(f"- 🟠 SDP #{s['display_id']} — {s['subject'][:60]}")
    if not data["active"] and not data.get("sdp_active"):
        lines.append("- No active tickets")
    lines.append("")

    return "\n".join(lines)


def format_teams_message(data: dict) -> str:
    d = data["date"]
    date_str = d.strftime("%B %-d, %Y")
    lines = [f"📋 **Standup — {date_str}**", ""]

    lines += ["✅ **Completed Today**"]
    if data["completed"]:
        for i in data["completed"]:
            lines.append(f"• {i['key']} — {i['fields'].get('summary', '')}")
    for s in data.get("sdp_done", []):
        lines.append(f"• SDP #{s['display_id']} — {s['subject']}")
    if not data["completed"] and not data.get("sdp_done"):
        lines.append("• Nothing closed today")
    lines.append("")

    lines += ["⏳ **Waiting On**"]
    if data["waiting"]:
        for i in data["waiting"]:
            next_s = i["fields"].get("customfield_10280", "") or find_next_step(i["key"]) or "pending response"
            lines.append(f"• {i['key']} — {next_s[:100]}")
    for s in data.get("sdp_waiting", []):
        lines.append(f"• SDP #{s['display_id']} — {s['subject'][:80]}")
    if not data["waiting"] and not data.get("sdp_waiting"):
        lines.append("• Nothing in waiting state")
    lines.append("")

    lines += ["🚫 **Blockers**"]
    if data["blockers"]:
        for b in data["blockers"]:
            lines.append(f"• {b}")
    else:
        lines.append("• None")
    lines.append("")

    lines += ["📅 **Active / Up Next**"]
    if data["active"]:
        for i in data["active"]:
            lane = classify_lane(i["fields"].get("labels", []))
            emoji = LANE_EMOJI.get(lane, "•")
            lines.append(f"{emoji} {i['key']} — {i['fields'].get('summary', '')}")
    for s in data.get("sdp_active", []):
        lines.append(f"🟠 SDP #{s['display_id']} — {s['subject'][:60]}")
    if not data["active"] and not data.get("sdp_active"):
        lines.append("• No active tickets")

    return "\n".join(lines)


def post_to_teams(message: str, webhook_url: str) -> None:
    payload = json.dumps({
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "themeColor": "0078D4",
        "text": message.replace("**", "**"),
    }).encode()
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
        print("✓ Standup posted to Teams")
    except urllib.error.HTTPError as e:
        print(f"  WARN: Teams post failed {e.code}: {e.read().decode()[:200]}", file=sys.stderr)


# ---------------------------------------------------------------------------
# File surgery — replace * Standup section
# ---------------------------------------------------------------------------

def replace_kanban_section(org_text: str, new_board: str) -> str:
    """Replace the Kanban Board section in the org file, preserving everything else."""
    pattern = re.compile(r"^\* Kanban Board.*?(?=^\* |\Z)", re.MULTILINE | re.DOTALL)
    if pattern.search(org_text):
        return pattern.sub(new_board + "\n", org_text)
    # No board section yet — insert before * Standup or * Notes
    for marker in ["* Standup", "* Notes"]:
        match = re.search(rf"^({re.escape(marker)})", org_text, re.MULTILINE)
        if match:
            return org_text[:match.start()] + new_board + "\n\n" + org_text[match.start():]
    return org_text + "\n" + new_board


def replace_standup_section(org_text: str, new_standup: str) -> str:
    # Replace from "* Standup" to the next top-level heading or end of file
    pattern = re.compile(r"^\* Standup.*?(?=^\* |\Z)", re.MULTILINE | re.DOTALL)
    if pattern.search(org_text):
        return pattern.sub(new_standup + "\n", org_text)
    # No standup section yet — append before * Notes if present
    notes_match = re.search(r"^(\* Notes)", org_text, re.MULTILINE)
    if notes_match:
        return org_text[:notes_match.start()] + new_standup + "\n" + org_text[notes_match.start():]
    return org_text + "\n" + new_standup


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def git_has_changes() -> bool:
    result = subprocess.run(["git", "status", "--porcelain"],
                            capture_output=True, text=True, cwd=PROJECTS)
    return bool(result.stdout.strip())


def git_commit_push(today: date) -> None:
    msg = f"chore(planner): EOD {today} — standup + worklog\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
    subprocess.run(["git", "add", "-A"], cwd=PROJECTS, check=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=PROJECTS, check=True)
    subprocess.run(["git", "push"], cwd=PROJECTS, check=True)
    print("✓ Committed and pushed — worklog CI/CD triggered")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def cmd_start(today: date, auth: str) -> None:
    PLANNER.mkdir(exist_ok=True)
    org_file = PLANNER / f"{today.strftime('%m-%d')}.org"

    if org_file.exists() and org_file.stat().st_size > 200:
        print(f"  Note already exists: {org_file}")
        print("  Use --end to close the day or edit directly.")
        return

    # Reconcile flow tags with Jira status before loading the board
    import subprocess
    sync_script = Path(__file__).parent / "jira_sync_flow_tags.py"
    if sync_script.exists():
        result = subprocess.run(
            [sys.executable, str(sync_script), "--apply"],
            capture_output=True, text=True
        )
        for line in result.stdout.splitlines():
            if "drift" in line or "Fixed" in line or "✓" in line.strip()[:2]:
                print(line)

    print("  Fetching active tickets from Jira...")
    active = jira_search(
        'project = INFRA AND labels = "flow:active" AND assignee = currentUser() '
        'AND status != Done ORDER BY priority ASC',
        ["summary", "status", "labels"], auth,
    )

    # Load SDP active cases from cases/ markdown (exclude Jira-linked to avoid dupes)
    sdp_active = scan_sdp_cases("flow:active", exclude_jira_linked=True)

    content = build_daily_note(active, today, sdp_active=sdp_active)
    org_file.write_text(content)
    print(f"  ✓ Daily note created: {org_file}")
    print(f"  ✓ {len(active)} Jira active ticket(s) loaded")
    for i in active:
        lane = classify_lane(i["fields"].get("labels", []))
        print(f"    {LANE_EMOJI[lane]} {i['key']} — {i['fields'].get('summary', '')[:60]}")
    if sdp_active:
        print(f"  ✓ {len(sdp_active)} SDP active ticket(s)")
        for s in sdp_active:
            print(f"    🟠 SDP #{s['display_id']} — {s['subject'][:60]}")


def cmd_refresh(today: date, auth: str) -> None:
    """Re-query Jira and update the Kanban Board section in today's note."""
    org_file = PLANNER / f"{today.strftime('%m-%d')}.org"

    if not org_file.exists():
        fail(
            f"{org_file} not found — run --start first",
            causes=["Today's planning note has not been created yet"],
            try_=[f"python3 scripts/daily_note.py --start",
                  f"ls planner/*.org  # list existing notes"],
        )

    print("  Refreshing board from Jira...")
    active = jira_search(
        'project = INFRA AND labels = "flow:active" '
        'AND (assignee = currentUser() OR assignee IS EMPTY) '
        'AND status != Done ORDER BY priority ASC',
        ["summary", "status", "labels"], auth,
    )

    sdp_active = scan_sdp_cases("flow:active", exclude_jira_linked=True)
    new_board = build_kanban_board(active, today, sdp_active=sdp_active)
    org_text = org_file.read_text()
    # Remove stale Active Work Items section if present
    active_pattern = re.compile(r"^\* Active Work Items.*?(?=^\* |\Z)", re.MULTILINE | re.DOTALL)
    org_text = active_pattern.sub("", org_text)
    updated = replace_kanban_section(org_text, new_board)
    org_file.write_text(updated)
    print(f"  ✓ Kanban Board refreshed — {len(active)} Jira + {len(sdp_active)} SDP active ticket(s)")
    for i in active:
        lane = classify_lane(i["fields"].get("labels", []))
        print(f"    {LANE_EMOJI[lane]} {i['key']} — {i['fields'].get('summary', '')[:60]}")
    for s in sdp_active:
        emoji = LANE_EMOJI.get(_sdp_classify_lane({"lane": s.get("lane", ""), "agentic": s.get("agentic", 4)}), "🟠")
        print(f"    {emoji} SDP #{s['display_id']} — {s['subject'][:60]}")

    # Refresh stakeholder outbox files from flow:waiting issue files
    outbox_script = PROJECTS / "scripts" / "outbox_refresh.py"
    if outbox_script.exists():
        subprocess.run(
            [sys.executable, str(outbox_script)],
            cwd=PROJECTS,
            check=False,
        )


def cmd_end(today: date, auth: str, blockers: list[str], skip_push: bool) -> None:
    org_file = PLANNER / f"{today.strftime('%m-%d')}.org"

    if not org_file.exists():
        fail(
            f"{org_file} not found — run --start first",
            causes=["Today's planning note has not been created yet"],
            try_=[f"python3 scripts/daily_note.py --start",
                  f"ls planner/*.org  # list existing notes"],
        )

    print("  Fetching Jira board state...")
    data = build_standup_content(auth, blockers, today)

    standup_section = format_standup_section(data)
    teams_message   = format_teams_message(data)

    org_text = org_file.read_text()
    updated  = replace_standup_section(org_text, standup_section)
    org_file.write_text(updated)
    print(f"  ✓ Standup section written to {org_file}")

    print()
    print("─" * 60)
    print("  TEAMS STANDUP MESSAGE")
    print("─" * 60)
    print(teams_message)
    print("─" * 60)

    webhook = os.environ.get("TEAMS_WEBHOOK_URL", "")
    if webhook:
        post_to_teams(teams_message, webhook)
    else:
        print()
        print("  (Set TEAMS_WEBHOOK_URL in .env to auto-post to Teams)")

    if not skip_push and git_has_changes():
        print()
        git_commit_push(today)
    elif not skip_push:
        print("  (No uncommitted changes — nothing to push)")


def cmd_standup(today: date, auth: str, blockers: list[str]) -> None:
    print("  Fetching Jira board state...")
    data = build_standup_content(auth, blockers, today)
    print()
    print(format_teams_message(data))


def main():
    load_env_file()
    auth = auth_header()
    today = date.today()

    parser = argparse.ArgumentParser(description="Daily note manager")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--start",   action="store_true", help="Create today's daily note")
    group.add_argument("--refresh", action="store_true", help="Refresh Kanban Board section from Jira")
    group.add_argument("--end",     action="store_true", help="Close the day — standup + push")
    group.add_argument("--standup", action="store_true", help="Print standup message only")
    parser.add_argument("--blocker", action="append", dest="blockers", metavar="TEXT",
                        help="Blocker to include (repeat for multiple)")
    parser.add_argument("--no-push", action="store_true", help="Skip git commit+push on --end")
    args = parser.parse_args()

    blockers = args.blockers or []

    if args.start:
        cmd_start(today, auth)
    elif args.refresh:
        cmd_refresh(today, auth)
    elif args.end:
        cmd_end(today, auth, blockers, args.no_push)
    elif args.standup:
        cmd_standup(today, auth, blockers)


if __name__ == "__main__":
    main()
