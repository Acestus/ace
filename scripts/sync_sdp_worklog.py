#!/usr/bin/env python3
"""
sync_sdp_worklog.py — Sync WORKLOG, COMMENT, and NUDGE lines from cases/ to ServiceDesk Plus.

Reads a git diff between two SHAs, finds newly added lines in cases/ matching:
    - WORKLOG <time>: <description>
    - COMMENT: <text>          → internal note (show_to_requester=false), technician voice
    - NUDGE: <text>            → public note (show_to_requester=true), end-user voice

Posts each as a worklog or note to the corresponding SDP request via Zoho OAuth.

Usage:
    python3 scripts/sync_sdp_worklog.py --from <sha> --to <sha>

Environment (reads from .env if not already set):
    WWEEKS_SDP — JSON string: {"client_id":"...","client_secret":"...","refresh_token":"..."}
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, http_fail, SDP_COMMON_CAUSES

SDP_BASE = "https://<YOUR_SDP>.sdpondemand.manageengine.com/app/698819937"
ZOHO_TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"


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


def get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    body = urllib.parse.urlencode({
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(
        ZOHO_TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        http_fail(e, api_name="SDP (Zoho OAuth)", operation="POST /oauth/v2/token",
                  common_causes={
                      401: {"causes": ["refresh_token expired or revoked",
                                       "client_id / client_secret mismatch"],
                            "try": ["Regenerate OAuth credentials in Zoho API Console",
                                    "grep WWEEKS_SDP .env"]},
                  })
    token = data.get("access_token", "")
    if not token:
        fail(
            "Zoho OAuth token exchange returned no access_token",
            causes=["refresh_token is expired (Zoho tokens expire after ~1 year)",
                    "client_id or client_secret is wrong"],
            try_=["Regenerate OAuth credentials in Zoho API Console",
                  "grep WWEEKS_SDP .env  # confirm credentials are current"],
        )
    return token


def resolve_sdp_id(folder_id: str) -> str:
    """Read SDP_ID: header from the case markdown file, fall back to folder name."""
    case_dir = Path("cases") / folder_id
    if case_dir.exists():
        for md_file in case_dir.glob("*.md"):
            text = md_file.read_text()
            m = re.search(r"(?m)^SDP_ID:\s*(\S+)", text)
            if m:
                return m.group(1)
    return folder_id


def parse_time(time_str: str) -> tuple[str, str]:
    hours = re.search(r"(\d+)h", time_str)
    minutes = re.search(r"(\d+)m", time_str)
    return (hours.group(1) if hours else "0", minutes.group(1) if minutes else "0")


def sdp_post(url: str, access_token: str, input_data: dict) -> None:
    body = urllib.parse.urlencode({"input_data": json.dumps(input_data)}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Accept": "application/vnd.manageengine.sdp.v3+json",
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            text = resp.read().decode(errors="replace")
            data = json.loads(text) if text.strip() else {}
            status = data.get("response_status", {}).get("status", "")
            if status == "failed":
                fail(
                    f"SDP API reported failure for {url}",
                    causes=["Invalid input_data JSON shape",
                            "Field value not accepted by SDP"],
                    try_=[f"python3 scripts/sdp_fetch_ticket.py --id <ID> --raw  # inspect schema",
                          f"Raw response: {text[:200]}"],
                )
    except urllib.error.HTTPError as e:
        http_fail(e, api_name="SDP", operation=f"POST {url}",
                  common_causes=SDP_COMMON_CAUSES)


def git_diff(from_sha: str, to_sha: str) -> str:
    result = subprocess.run(
        ["git", "--no-pager", "diff", "--unified=0", "--no-color", from_sha, to_sha, "--", "cases/"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def parse_diff(diff: str) -> list[dict]:
    entries = []
    current_id = None
    seen = set()

    for line in diff.splitlines():
        if line.startswith("+++ b/cases/"):
            m = re.match(r"^\+\+\+ b/cases/(\d+)/", line)
            if m:
                current_id = m.group(1)
            continue

        if not current_id:
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue

        content = line[1:]

        m = re.match(r"^\s*[-*]\s*WORKLOG\s+([^:]+):\s*(.+)\s*$", content)
        if m:
            entry = {"type": "worklog", "id": current_id,
                     "timeSpent": m.group(1).strip(), "text": m.group(2).strip()}
            key = (entry["id"], entry["type"], entry["timeSpent"], entry["text"])
            if key not in seen:
                seen.add(key)
                entries.append(entry)
            continue

        m = re.match(r"^\s*[-*]\s*COMMENT:\s*(.+)\s*$", content)
        if m:
            entry = {"type": "comment", "id": current_id, "text": m.group(1).strip()}
            key = (entry["id"], entry["type"], entry["text"])
            if key not in seen:
                seen.add(key)
                entries.append(entry)
            continue

        m = re.match(r"^\s*[-*]\s*NUDGE:\s*(.+)\s*$", content)
        if m:
            entry = {"type": "nudge", "id": current_id, "text": m.group(1).strip()}
            key = (entry["id"], entry["type"], entry["text"])
            if key not in seen:
                seen.add(key)
                entries.append(entry)

    return entries


def main():
    load_env_file()

    parser = argparse.ArgumentParser(description="Sync SDP worklogs from git diff")
    parser.add_argument("--from", dest="from_sha", required=True)
    parser.add_argument("--to", dest="to_sha", required=True)
    args = parser.parse_args()

    require_env("WWEEKS_SDP",
                hint="cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)")
    creds = json.loads(os.environ["WWEEKS_SDP"])
    access_token = get_access_token(creds["client_id"], creds["client_secret"], creds["refresh_token"])
    print("✓ OAuth token acquired")

    try:
        diff = git_diff(args.from_sha, args.to_sha)
    except subprocess.CalledProcessError as e:
        fail(
            f"git diff failed ({args.from_sha}..{args.to_sha})",
            causes=["One or both SHAs do not exist in local repo",
                    "Not running from the repo root"],
            try_=[f"git log --oneline | head -5  # verify SHA exists",
                  "cd /home/wweeks/git/projects && git log --oneline"],
        )

    entries = parse_diff(diff)

    if not entries:
        print("No new WORKLOG/COMMENT/NUDGE lines detected in cases/ changes.")
        return

    print(f"Found {len(entries)} new SDP sync entries.")
    for entry in entries:
        folder_id = entry["id"]
        sdp_id = resolve_sdp_id(folder_id)
        if sdp_id == folder_id:
            print(f"  ⚠ No SDP_ID: header found in cases/{folder_id}/ — using folder name as request ID", file=sys.stderr)
        print(f"  Ticket {folder_id} → SDP request {sdp_id}")

        if entry["type"] == "worklog":
            hours, minutes = parse_time(entry["timeSpent"])
            import time as time_module
            now_ms = int(time_module.time() * 1000)
            payload = {
                "worklog": {
                    "description": entry["text"],
                    "start_time": {"value": now_ms},
                    "time_spent": {"hours": hours, "minutes": minutes},
                    "owner": {"email_id": "<YOUR_EMAIL>"},
                    "include_nonoperational_hours": True,
                    "mark_first_response": False,
                }
            }
            sdp_post(f"{SDP_BASE}/api/v3/requests/{sdp_id}/worklogs", access_token, payload)
            print(f"  ✓ Worklog added to SDP-{sdp_id} ({entry['timeSpent']})")

        elif entry["type"] == "comment":
            payload = {
                "request_note": {
                    "description": entry["text"],
                    "show_to_requester": False,
                    "mark_first_response": False,
                    "add_to_linked_requests": False,
                }
            }
            sdp_post(f"{SDP_BASE}/api/v3/requests/{sdp_id}/notes", access_token, payload)
            print(f"  ✓ Internal note added to SDP-{sdp_id}")

        elif entry["type"] == "nudge":
            payload = {
                "request_note": {
                    "description": entry["text"],
                    "show_to_requester": True,
                    "mark_first_response": False,
                    "add_to_linked_requests": False,
                }
            }
            sdp_post(f"{SDP_BASE}/api/v3/requests/{sdp_id}/notes", access_token, payload)
            print(f"  ✓ Public nudge added to SDP-{sdp_id} (visible to requester)")


if __name__ == "__main__":
    main()
