#!/usr/bin/env python3
"""
start_my_day.py — Create today's daily note and report active Jira lane status.

Usage:
    python3 scripts/start_my_day.py
    python3 scripts/start_my_day.py --no-jira

Environment (reads from .env if not already set):
    CONFLUENCE_EMAIL
    WWEEKS_CONFLUENCE_API_TOKEN
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, http_fail, JIRA_COMMON_CAUSES
JIRA_BASE = "https://<YOUR_ATLASSIAN>.atlassian.net"
ACTIVE_JQL = 'project = INFRA AND labels = "flow:active" ORDER BY updated DESC'
LANE_INFO = {
    "urgent": ("🔴", "Urgent"),
    "manual": ("🔵", "Manual"),
    "background": ("🟢", "Background"),
}


def load_env_file():
    env_path = Path(__file__).parent.parent / ".env"
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
        "CONFLUENCE_EMAIL", "WWEEKS_CONFLUENCE_API_TOKEN",
        hint="Add them to .env at the repo root",
        env_file=str(REPO_ROOT / ".env"),
    )
    email = os.environ["CONFLUENCE_EMAIL"]
    token = os.environ["WWEEKS_CONFLUENCE_API_TOKEN"]
    return "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()



def label_value(labels: list[str], prefix: str) -> int | None:
    for label in labels:
        if label.startswith(f"{prefix}:"):
            try:
                return int(label.split(":", 1)[1])
            except ValueError:
                return None
    return None



def classify_lane(labels: list[str]) -> str:
    urgency = label_value(labels, "urgency")
    agentic = label_value(labels, "agentic")
    importance = label_value(labels, "importance")
    if urgency in {1, 2}:
        return "urgent"
    if agentic in {4, 5} and importance in {1, 2, 3}:
        return "manual"
    if agentic in {1, 2}:
        return "background"
    return "manual"



def run_jql(auth: str) -> list[dict]:
    issues = []
    next_page_token = None
    while True:
        payload = {
            "jql": ACTIVE_JQL,
            "fields": ["summary", "labels"],
            "maxResults": 100,
        }
        if next_page_token:
            payload["nextPageToken"] = next_page_token
        req = urllib.request.Request(
            f"{JIRA_BASE}/rest/api/3/search/jql",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": auth,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read())
        except urllib.error.HTTPError as error:
            http_fail(error, api_name="Jira", key="search/jql", operation="POST search/jql",
                      common_causes=JIRA_COMMON_CAUSES)
        batch = result.get("issues", [])
        issues.extend(batch)
        next_page_token = result.get("nextPageToken")
        if result.get("isLast") or not next_page_token or not batch:
            return issues



def run_daily_note_start() -> None:
    result = subprocess.run(
        ["python3", "scripts/daily_note.py", "--start"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        fail(
            "daily_note.py --start failed",
            causes=["daily_note.py returned a non-zero exit code"],
            try_=["Run manually: python3 scripts/daily_note.py --start"],
            exit_code=result.returncode,
        )



def print_active_board(issues: list[dict]) -> None:
    lanes = {"urgent": None, "manual": None, "background": None}
    for issue in issues:
        lane = classify_lane(issue.get("fields", {}).get("labels", []))
        if lanes[lane] is None:
            lanes[lane] = issue

    print()
    print("Active board:")
    for lane in ("urgent", "manual", "background"):
        emoji, label = LANE_INFO[lane]
        issue = lanes[lane]
        if issue is None:
            print(f"  {emoji} {label + ':':<13} (open)")
            continue
        summary = issue.get("fields", {}).get("summary", "")
        print(f"  {emoji} {label + ':':<13} {issue['key']:<9} — {summary}")

    for lane in ("urgent", "manual", "background"):
        if lanes[lane] is None:
            _, label = LANE_INFO[lane]
            print(f"\n⚠  {label} lane is empty — run dispatch to pull the next ticket.")



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create today's note and report active Jira lanes")
    parser.add_argument("--no-jira", action="store_true", help="Skip Jira lane status query")
    return parser.parse_args()



def main():
    load_env_file()
    args = parse_args()
    run_daily_note_start()
    if args.no_jira:
        return
    auth = auth_header()
    issues = run_jql(auth)
    print_active_board(issues)



if __name__ == "__main__":
    main()
