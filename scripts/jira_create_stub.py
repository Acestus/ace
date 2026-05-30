#!/usr/bin/env python3
"""
jira_create_stub.py — Create a local issue file stub for a Jira ticket.

Creates the issues/{KEY} - {summary}/ folder and markdown stub if it doesn't
already exist. Prints the absolute path to the file on stdout.

Usage:
    python3 scripts/jira_create_stub.py --key <PROJECT>-392
    python3 scripts/jira_create_stub.py --key <PROJECT>-392 --force   # overwrite if exists

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
import urllib.request
import urllib.error
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, http_fail, JIRA_COMMON_CAUSES

JIRA_BASE  = "https://<YOUR_ATLASSIAN>.atlassian.net"
JIRA_BROWSE = f"{JIRA_BASE}/browse"
PROJECTS   = Path(__file__).parent.parent
ISSUES     = PROJECTS / "issues"
FIELDS     = "summary,status,assignee,labels,description,customfield_10246,customfield_10280,duedate,priority,parent"


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
    require_env(
        "CONFLUENCE_EMAIL",
        "WWEEKS_CONFLUENCE_API_TOKEN",
        hint="cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)",
    )
    email = os.environ["CONFLUENCE_EMAIL"]
    token = os.environ["WWEEKS_CONFLUENCE_API_TOKEN"]
    return "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()


def fetch_ticket(key: str) -> dict:
    url = f"{JIRA_BASE}/rest/api/3/issue/{key}?fields={FIELDS}"
    req = urllib.request.Request(url, headers={"Authorization": auth_header(), "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        http_fail(e, api_name="Jira", key=key,
                  operation=f"GET /rest/api/3/issue/{key}",
                  common_causes=JIRA_COMMON_CAUSES)


def safe_name(text: str) -> str:
    """Sanitize a string for use in a filesystem path."""
    text = re.sub(r'[<>:"/\\|?*]', '-', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:120]  # cap folder name length


def extract_adf_text(node) -> str:
    if not node:
        return ""
    if isinstance(node, str):
        return node
    if node.get("type") == "text":
        return node.get("text", "")
    parts = []
    for child in node.get("content", []):
        parts.append(extract_adf_text(child))
    return " ".join(p for p in parts if p).strip()


def resolve_sdp_long_id(display_id: str) -> str:
    """Call sdp_fetch_ticket.py to get the long internal SDP API ID. Returns empty string on failure."""
    script = Path(__file__).parent / "sdp_fetch_ticket.py"
    try:
        result = subprocess.run(
            [sys.executable, str(script), "--id", display_id, "--json"],
            capture_output=True, text=True, timeout=20
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("id", "")
    except Exception:
        pass
    return ""


def build_stub(key: str, fields: dict, folder_name: str) -> str:
    summary    = fields.get("summary", "")
    status     = fields.get("status", {}).get("name", "Unknown")
    labels     = fields.get("labels", [])
    parent     = fields.get("parent", {})
    parent_key = parent.get("key", "") if parent else ""
    parent_sum = parent.get("fields", {}).get("summary", "") if parent else ""
    desc_raw   = fields.get("description") or {}
    desc_text  = extract_adf_text(desc_raw)
    next_steps = extract_adf_text(fields.get("customfield_10280") or {})
    due        = fields.get("duedate") or "—"
    today      = date.today().isoformat()

    epic_line = f"- Epic: {parent_key} — {parent_sum}" if parent_key else ""
    sdp_match = re.search(r'SDP\s*#?(\d+)', desc_text + " " + next_steps, re.I)
    if sdp_match:
        sdp_display = sdp_match.group(1)
        sdp_long = resolve_sdp_long_id(sdp_display)
        sdp_line = f"- SDP: #{sdp_display}" + (f"\n- SDP_ID: {sdp_long}" if sdp_long else "")
    else:
        sdp_line = ""

    label_str = "  ".join(labels)

    lines = [
        f"# {folder_name}",
        f"<!-- jira: {key} -->",
        f"<!-- last_synced: 1970-01-01T00:00:00Z -->",
        "",
        "## Description",
        "",
        "------------------------------------------------",
        "",
        f"- Jira: {JIRA_BROWSE}/{key}",
    ]
    if epic_line:
        lines.append(epic_line)
    if sdp_line:
        lines.append(sdp_line)
    lines += [
        f"- Status: {status}",
        f"- Due: {due}",
        f"- Labels: {label_str}",
        "",
    ]
    if desc_text:
        lines += [desc_text, ""]
    if next_steps:
        lines += ["**Next steps (from Jira):** " + next_steps, ""]

    lines += [
        "## Actions",
        "",
        "------------------------------------------------",
        "",
        f"### {today}",
        "",
        "",
        "## Follow-up",
        "",
        "------------------------------------------------",
        f"Status: {next(('flow:' + l.split(':')[1] for l in labels if l.startswith('flow:')), 'unknown')}",
        "TODO:",
    ]

    return "\n".join(lines) + "\n"


def find_existing(key: str) -> Path | None:
    if not ISSUES.exists():
        return None
    for folder in ISSUES.iterdir():
        if folder.is_dir() and (folder.name.startswith(f"{key} ") or folder.name == key):
            md = folder / f"{folder.name}.md"
            if md.exists():
                return md
    return None


def main():
    load_env_file()
    parser = argparse.ArgumentParser(description="Create a local issue file stub for a Jira ticket.")
    parser.add_argument("--key", required=True, help="Jira issue key, e.g. <PROJECT>-392")
    parser.add_argument("--force", action="store_true", help="Overwrite existing stub")
    args = parser.parse_args()

    key = args.key.upper()

    existing = find_existing(key)
    if existing and not args.force:
        print(existing)
        return

    data    = fetch_ticket(key)
    fields  = data.get("fields", {})
    summary = fields.get("summary", key)

    folder_name = safe_name(f"{key} - {summary}")
    folder      = ISSUES / folder_name
    folder.mkdir(parents=True, exist_ok=True)

    stub_path = folder / f"{folder_name}.md"
    stub_path.write_text(build_stub(key, fields, folder_name))

    print(stub_path)


if __name__ == "__main__":
    main()
