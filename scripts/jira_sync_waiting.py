#!/usr/bin/env python3
"""
jira_sync_waiting.py — Push notes and next-steps from issue files to Jira for all flow:waiting tickets.

Reads each waiting ticket's issue file, extracts the Follow-up section fields,
and updates the Jira Notes and Next Steps custom fields. Also ensures the outbox
is refreshed.

Usage:
    python3 scripts/jira_sync_waiting.py
    python3 scripts/jira_sync_waiting.py --key <PROJECT>-257       # single ticket
    python3 scripts/jira_sync_waiting.py --dry-run             # preview only
    python3 scripts/jira_sync_waiting.py --refresh-outbox      # also refresh outbox

Environment (reads from .env if not already set):
    CONFLUENCE_EMAIL
    WWEEKS_CONFLUENCE_API_TOKEN
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, http_fail, JIRA_COMMON_CAUSES

REPO_ROOT = Path(__file__).parent.parent
ISSUES_DIR = REPO_ROOT / "issues"
JIRA_BASE = "https://<YOUR_ATLASSIAN>.atlassian.net"


def load_env_file():
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() not in os.environ:
            os.environ[k.strip()] = v.strip()


def auth_header() -> str:
    require_env(
        "CONFLUENCE_EMAIL",
        "WWEEKS_CONFLUENCE_API_TOKEN",
        hint="cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)",
    )
    email = os.environ["CONFLUENCE_EMAIL"]
    token = os.environ["WWEEKS_CONFLUENCE_API_TOKEN"]
    return "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()


def find_issue_file(key: str) -> Path | None:
    for d in ISSUES_DIR.iterdir():
        if d.is_dir() and d.name.startswith(key):
            for f in d.glob("*.md"):
                return f
    return None


def extract_ticket_summary(md_text: str) -> str:
    """Extract a one-liner about what this ticket IS from the Description section."""
    desc_match = re.search(r"## Description.*?(?=\n## |\Z)", md_text, re.DOTALL)
    if not desc_match:
        return ""
    section = desc_match.group(0)
    # Skip header lines, metadata, and scoring lines
    lines = [
        l.strip() for l in section.splitlines()
        if l.strip()
        and not l.strip().startswith("#")
        and not l.strip().startswith("-")
        and not l.strip().startswith("---")
        and not re.match(r"^(Jira:|Epic:|SDP:|Status:|Reference:|Scores:|\*\*)", l.strip())
        and "Agentic:" not in l
    ]
    # First meaningful paragraph line is the summary
    if not lines:
        return ""
    # Truncate to one useful sentence
    summary = lines[0]
    if len(summary) > 200:
        summary = summary[:197] + "…"
    return summary


def extract_notes_from_issue(md_text: str) -> dict:
    """Extract manager-friendly notes and next-steps from an issue file.

    Notes format for backlog meeting:
        What: <one-liner from Description>
        Status: <current state/blocker>
        Waiting on: <stakeholder>
    """
    result = {"notes": "", "next_steps": ""}

    # 1. Get the ticket summary (what is this about?)
    summary = extract_ticket_summary(md_text)

    # 2. Get Follow-up section fields
    followup_match = re.search(r"## Follow-up.*?(?=\n## |\Z)", md_text, re.DOTALL)
    status_line = ""
    waiting_on = ""
    next_action = ""
    if followup_match:
        section = followup_match.group(0)
        status_match = re.search(r"Status:\s*(.+)", section)
        waiting_on_match = re.search(r"Waiting on:\s*(.+)", section)
        next_action_match = re.search(r"Their next action:\s*(.+)", section)

        if status_match:
            status_line = status_match.group(1).strip()
        if waiting_on_match:
            waiting_on = waiting_on_match.group(1).strip()
        if next_action_match:
            next_action = next_action_match.group(1).strip()

    # 3. Build manager-friendly notes
    notes_parts = []
    if summary:
        notes_parts.append(f"What: {summary}")
    if status_line:
        notes_parts.append(f"Status: {status_line}")
    elif waiting_on:
        notes_parts.append(f"Waiting on: {waiting_on}")
    if waiting_on and status_line:
        notes_parts.append(f"Waiting on: {waiting_on}")

    result["notes"] = "\n".join(notes_parts) if notes_parts else ""
    result["next_steps"] = next_action

    # 4. Fallback: if no notes from Follow-up, use last action entry
    if not result["notes"]:
        action_headers = re.findall(
            r"### (\d{4}-\d{2}-\d{2}[^\n]*)\n+(.*?)(?=\n### |\n## |\Z)",
            md_text, re.DOTALL,
        )
        if action_headers:
            last_date, last_body = action_headers[0]
            first_line = last_body.strip().splitlines()[0] if last_body.strip() else ""
            result["notes"] = f"{last_date}: {first_line}"[:200]

    return result


def get_waiting_keys(include_all: bool = False) -> list[str]:
    """Query Jira for flow:waiting tickets (or all non-done) assigned to current user."""
    auth = auth_header()
    if include_all:
        jql = 'project = INFRA AND assignee = currentUser() AND labels in ("flow:waiting", "flow:active", "flow:queue") ORDER BY key ASC'
    else:
        jql = 'project = INFRA AND labels = "flow:waiting" AND assignee = currentUser() ORDER BY key ASC'
    body = json.dumps({
        "jql": jql,
        "fields": ["key"],
        "maxResults": 50,
    }).encode()
    req = urllib.request.Request(
        f"{JIRA_BASE}/rest/api/3/search/jql",
        data=body,
        headers={
            "Authorization": auth,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
        return [issue["key"] for issue in data.get("issues", [])]
    except urllib.error.HTTPError as e:
        http_fail(e, api_name="Jira", operation="POST /rest/api/3/search/jql",
                  common_causes=JIRA_COMMON_CAUSES)


def update_jira_fields(key: str, notes: str, next_steps: str, dry_run: bool = False) -> bool:
    """Push notes and next-steps to Jira custom fields."""
    if dry_run:
        print(f"  [dry-run] {key}")
        if notes:
            print(f"    Notes: {notes[:100]}")
        if next_steps:
            print(f"    Next:  {next_steps[:100]}")
        return True

    cmd = [
        sys.executable, str(REPO_ROOT / "scripts" / "jira_update_fields.py"),
        "--key", key,
    ]
    if notes:
        cmd += ["--notes", notes]
    if next_steps:
        cmd += ["--next-steps", next_steps]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True
        else:
            print(f"  ❌  {key}: {result.stderr.strip()}", file=sys.stderr)
            return False
    except subprocess.TimeoutExpired:
        print(f"  ❌  {key}: timeout", file=sys.stderr)
        return False


def main():
    load_env_file()

    parser = argparse.ArgumentParser(description="Sync waiting ticket notes to Jira")
    parser.add_argument("--key", help="Sync a single ticket (e.g. <PROJECT>-257)")
    parser.add_argument("--all", action="store_true", help="Sync all tickets (waiting + active + queue)")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without updating Jira")
    parser.add_argument("--refresh-outbox", action="store_true", help="Also refresh outbox files")
    args = parser.parse_args()

    if args.key:
        keys = [args.key]
    else:
        label = "all non-done" if args.all else "flow:waiting"
        print(f"🔍  Fetching {label} tickets…")
        keys = get_waiting_keys(include_all=args.all)
        print(f"    Found {len(keys)} tickets\n")

    updated = 0
    skipped = 0
    failed = 0

    for key in keys:
        issue_file = find_issue_file(key)
        if not issue_file:
            print(f"  ⚠  {key}: no issue file found — skipping")
            skipped += 1
            continue

        md_text = issue_file.read_text(encoding="utf-8")
        fields = extract_notes_from_issue(md_text)

        if not fields["notes"] and not fields["next_steps"]:
            print(f"  ⚠  {key}: no notes or next-steps to sync — skipping")
            skipped += 1
            continue

        if update_jira_fields(key, fields["notes"], fields["next_steps"], args.dry_run):
            print(f"  ✓  {key}")
            updated += 1
        else:
            failed += 1

    print(f"\n{'─' * 40}")
    print(f"  ✓ Updated: {updated}  |  ⚠ Skipped: {skipped}  |  ❌ Failed: {failed}")

    if args.refresh_outbox:
        print("\n📬  Refreshing outbox…")
        subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "outbox_refresh.py")],
            cwd=str(REPO_ROOT),
        )


if __name__ == "__main__":
    main()
