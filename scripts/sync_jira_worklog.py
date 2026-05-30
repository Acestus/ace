#!/usr/bin/env python3
"""
sync_jira_worklog.py — Sync WORKLOG, COMMENT, and NUDGE lines from issues/ to Jira.

Reads a git diff between two SHAs, finds newly added lines in issues/ matching:
    - WORKLOG <time>: <description>
    - COMMENT: <text>
    - NUDGE [@user.name [, @user2 ...]]: <text>

WORKLOG → posts a worklog entry with the comment attached (internal time entry).
COMMENT → posts a Jira comment marked JSM-internal (sd.public.comment internal=true).
          Use for technician/internal investigative narrative.
NUDGE   → posts a Jira comment marked JSM-public (sd.public.comment internal=false)
          with inline @mentions resolved to accountIds so the tagged user(s) receive
          a notification. Visible to the reporter in the customer portal. The body
          reads like a Teams message: a short, direct ask of a specific person, or
          a 6–10 sentence end-user-voice status update.

Posts each as a worklog entry or comment to the corresponding Jira issue.

Usage:
    python3 scripts/sync_jira_worklog.py --from <sha> --to <sha>

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
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

JIRA_BASE = "https://<YOUR_ATLASSIAN>.atlassian.net"


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


def auth_header():
    email = os.environ.get("CONFLUENCE_EMAIL", "")
    token = os.environ.get("WWEEKS_CONFLUENCE_API_TOKEN", "")
    if not email or not token:
        print("ERROR: CONFLUENCE_EMAIL and WWEEKS_CONFLUENCE_API_TOKEN must be set", file=sys.stderr)
        sys.exit(1)
    return "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()


def adf_paragraph(text: str) -> dict:
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


# Matches @firstname.lastname, @first.last.middle, or @email-style handles
# (letters, digits, dot, hyphen, underscore — must start with a letter)
MENTION_RE = re.compile(r"@([A-Za-z][A-Za-z0-9._-]*[A-Za-z0-9])")

_user_cache: dict[str, dict | None] = {}


def lookup_jira_user(handle: str, auth: str) -> dict | None:
    """Resolve an @handle to a Jira user record {accountId, displayName}.

    Tries a few query forms because Jira's user search is fuzzy:
      - "firstname.lastname" → "firstname lastname"
      - raw handle as-is
      - email guess "{handle}@<ORG_DOMAIN>"

    Returns the first active match, or None if no match.
    Results are cached for the lifetime of the process.
    """
    if handle in _user_cache:
        return _user_cache[handle]

    candidates = [handle.replace(".", " "), handle, f"{handle}@<ORG_DOMAIN>"]
    found = None
    for query in candidates:
        url = f"{JIRA_BASE}/rest/api/3/user/search?query={urllib.parse.quote(query)}"
        req = urllib.request.Request(
            url,
            headers={"Authorization": auth, "Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                users = json.loads(resp.read())
        except urllib.error.HTTPError:
            continue
        for u in users:
            if u.get("active") and u.get("accountType") == "atlassian":
                found = {"accountId": u["accountId"], "displayName": u.get("displayName", handle)}
                break
        if found:
            break

    _user_cache[handle] = found
    return found


def adf_with_mentions(text: str, auth: str) -> dict:
    """Build an ADF doc whose paragraph splits text around @mentions.

    Unresolved @handles fall back to plain text so the comment still posts —
    a warning is printed but sync does not fail.
    """
    nodes: list[dict] = []
    last = 0
    for m in MENTION_RE.finditer(text):
        if m.start() > last:
            nodes.append({"type": "text", "text": text[last:m.start()]})
        handle = m.group(1)
        user = lookup_jira_user(handle, auth)
        if user:
            nodes.append({
                "type": "mention",
                "attrs": {
                    "id": user["accountId"],
                    "text": f"@{user['displayName']}",
                },
            })
        else:
            print(f"  ⚠ NUDGE: could not resolve @{handle} — leaving as plain text", file=sys.stderr)
            nodes.append({"type": "text", "text": m.group(0)})
        last = m.end()
    if last < len(text):
        nodes.append({"type": "text", "text": text[last:]})
    if not nodes:
        nodes = [{"type": "text", "text": text}]
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": nodes}],
    }


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+0000")


def git_diff(from_sha: str, to_sha: str) -> str:
    result = subprocess.run(
        ["git", "--no-pager", "diff", "--unified=0", "--no-color", from_sha, to_sha, "--", "issues/"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def parse_diff(diff: str) -> list[dict]:
    entries = []
    current_issue = None
    seen = set()

    for line in diff.splitlines():
        # Detect which issue file we're in
        if line.startswith("+++ b/issues/"):
            m = re.match(r"^\+\+\+ b/issues/([A-Z]+-\d+)", line)
            if m:
                current_issue = m.group(1)
            continue

        if not current_issue:
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue

        content = line[1:]  # strip leading +

        # WORKLOG <time>: <description>
        m = re.match(r"^\s*[-*]\s*WORKLOG\s+([^:]+):\s*(.+)\s*$", content)
        if m:
            entry = {
                "type": "worklog",
                "issue": current_issue,
                "timeSpent": m.group(1).strip(),
                "text": m.group(2).strip(),
            }
            key = (entry["issue"], entry["type"], entry["timeSpent"], entry["text"])
            if key not in seen:
                seen.add(key)
                entries.append(entry)
            continue

        # COMMENT: <text>
        m = re.match(r"^\s*[-*]\s*COMMENT:\s*(.+)\s*$", content)
        if m:
            entry = {
                "type": "comment",
                "issue": current_issue,
                "text": m.group(1).strip(),
            }
            key = (entry["issue"], entry["type"], entry["text"])
            if key not in seen:
                seen.add(key)
                entries.append(entry)
            continue

        # NUDGE: <text>  (with optional inline @mentions in the text)
        m = re.match(r"^\s*[-*]\s*NUDGE:\s*(.+)\s*$", content)
        if m:
            entry = {
                "type": "nudge",
                "issue": current_issue,
                "text": m.group(1).strip(),
            }
            key = (entry["issue"], entry["type"], entry["text"])
            if key not in seen:
                seen.add(key)
                entries.append(entry)

    return entries


def post_worklog(issue: str, time_spent: str, text: str, auth: str) -> None:
    payload = json.dumps({
        "timeSpent": time_spent,
        "started": iso_now(),
        "comment": adf_paragraph(text),
    }).encode()
    req = urllib.request.Request(
        f"{JIRA_BASE}/rest/api/3/issue/{issue}/worklog",
        data=payload,
        headers={
            "Authorization": auth,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
        print(f"  ✓ Worklog added to {issue} ({time_spent})")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"  ❌ Worklog failed for {issue}: {e.code} {body[:200]}", file=sys.stderr)
        sys.exit(1)


def post_comment(issue: str, text: str, auth: str, *, with_mentions: bool = False, public: bool = False) -> None:
    body = adf_with_mentions(text, auth) if with_mentions else adf_paragraph(text)
    # sd.public.comment with internal=true → JSM-internal (technician/agent voice).
    # internal=false → visible to the reporter in the portal (NUDGE).
    # Property is ignored on non-JSM projects, so the flag is safe everywhere.
    internal = not public
    payload = json.dumps({
        "body": body,
        "properties": [{"key": "sd.public.comment", "value": {"internal": internal}}],
    }).encode()
    req = urllib.request.Request(
        f"{JIRA_BASE}/rest/api/3/issue/{issue}/comment",
        data=payload,
        headers={
            "Authorization": auth,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
        label = "Nudge comment" if with_mentions else "Comment"
        print(f"  ✓ {label} added to {issue}")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"  ❌ Comment failed for {issue}: {e.code} {body[:200]}", file=sys.stderr)
        sys.exit(1)


def main():
    load_env_file()

    parser = argparse.ArgumentParser(description="Sync Jira worklogs from git diff")
    parser.add_argument("--from", dest="from_sha", required=True, help="Base commit SHA")
    parser.add_argument("--to", dest="to_sha", required=True, help="Head commit SHA")
    args = parser.parse_args()

    auth = auth_header()

    try:
        diff = git_diff(args.from_sha, args.to_sha)
    except subprocess.CalledProcessError as e:
        print(f"ERROR running git diff: {e}", file=sys.stderr)
        sys.exit(1)

    entries = parse_diff(diff)

    if not entries:
        print("No new WORKLOG/COMMENT/NUDGE lines detected in issues/ changes.")
        return

    print(f"Found {len(entries)} new Jira sync entries.")
    for entry in entries:
        if entry["type"] == "worklog":
            post_worklog(entry["issue"], entry["timeSpent"], entry["text"], auth)
        elif entry["type"] == "comment":
            post_comment(entry["issue"], entry["text"], auth)
        elif entry["type"] == "nudge":
            post_comment(entry["issue"], entry["text"], auth, with_mentions=True, public=True)


if __name__ == "__main__":
    main()
