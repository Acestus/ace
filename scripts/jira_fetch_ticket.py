#!/usr/bin/env python3
"""
jira_fetch_ticket.py — Fetch and display a Jira ticket cleanly.

Usage:
    python3 scripts/jira_fetch_ticket.py --key <PROJECT>-366
    python3 scripts/jira_fetch_ticket.py --key <PROJECT>-366 --json   # raw JSON output

Environment (reads from .env if not already set):
    CONFLUENCE_EMAIL
    WWEEKS_CONFLUENCE_API_TOKEN
"""

import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, http_fail, JIRA_COMMON_CAUSES

JIRA_BASE = "https://<YOUR_ATLASSIAN>.atlassian.net"
FIELDS = "summary,status,assignee,labels,description,comment,customfield_10246,customfield_10280,duedate,priority,parent,customfield_10028,customfield_10029,customfield_10060,issuelinks"


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
    require_env(
        "CONFLUENCE_EMAIL",
        "WWEEKS_CONFLUENCE_API_TOKEN",
        hint="cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)",
    )
    email = os.environ["CONFLUENCE_EMAIL"]
    token = os.environ["WWEEKS_CONFLUENCE_API_TOKEN"]
    return "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()


def extract_adf_text(node: dict | None) -> str:
    """Recursively render an ADF doc to plain text.

    - bulletList items render with '  • ' prefix
    - hardBreak renders as newline
    - link marks render as 'text (url)'
    - block boundaries get a trailing newline
    """
    if not node:
        return ""

    def render(n: dict, indent: str = "") -> str:
        t = n.get("type")
        if t == "text":
            text = n.get("text", "")
            for mark in n.get("marks", []) or []:
                if mark.get("type") == "link":
                    href = (mark.get("attrs") or {}).get("href")
                    if href and href != text:
                        text = f"{text} ({href})"
            return text
        if t == "hardBreak":
            return "\n" + indent
        if t == "paragraph":
            return "".join(render(c, indent) for c in n.get("content", []) or [])
        if t == "bulletList":
            lines = []
            for li in n.get("content", []) or []:
                body = "".join(render(c, indent + "    ") for c in li.get("content", []) or [])
                lines.append(f"{indent}  • {body}")
            return "\n".join(lines)
        if t == "orderedList":
            lines = []
            for i, li in enumerate(n.get("content", []) or [], 1):
                body = "".join(render(c, indent + "    ") for c in li.get("content", []) or [])
                lines.append(f"{indent}  {i}. {body}")
            return "\n".join(lines)
        if t in ("listItem", "doc"):
            return "".join(render(c, indent) for c in n.get("content", []) or [])
        return "".join(render(c, indent) for c in n.get("content", []) or [])

    parts = []
    for block in node.get("content", []) or []:
        rendered = render(block)
        if rendered:
            parts.append(rendered)
    return "\n".join(parts).strip()


def main():
    load_env_file()

    parser = argparse.ArgumentParser(description="Fetch a Jira ticket")
    parser.add_argument("--key", required=True, help="Jira issue key, e.g. <PROJECT>-366")
    parser.add_argument("--json", action="store_true", dest="raw_json", help="Output raw JSON")
    args = parser.parse_args()

    auth = auth_header()
    url = f"{JIRA_BASE}/rest/api/3/issue/{args.key}?fields={FIELDS}"
    req = urllib.request.Request(url, headers={"Authorization": auth, "Accept": "application/json"})

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        http_fail(e, api_name="Jira", key=args.key,
                  operation=f"GET /rest/api/3/issue/{args.key}",
                  common_causes=JIRA_COMMON_CAUSES)

    if args.raw_json:
        print(json.dumps(data, indent=2))
        return

    f = data["fields"]

    print(f"{'='*60}")
    print(f"  {args.key}: {f.get('summary', '')}")
    print(f"{'='*60}")
    print(f"  Status   : {f['status']['name']}")
    print(f"  Assignee : {(f.get('assignee') or {}).get('displayName', 'Unassigned')}")
    print(f"  Priority : {(f.get('priority') or {}).get('name', '')}")
    print(f"  Due      : {f.get('duedate', '')}")
    print(f"  Labels   : {' '.join(f.get('labels', []))}")

    parent = f.get("parent")
    if parent:
        print(f"  Parent   : {parent['key']} — {parent['fields'].get('summary', '')}")

    desc = extract_adf_text(f.get("description"))
    if desc:
        print(f"\n--- Description ---\n{desc[:800]}")

    notes = extract_adf_text(f.get("customfield_10246"))
    if notes:
        print(f"\n--- Notes ---\n{notes}")

    next_steps = f.get("customfield_10280")
    if next_steps:
        print(f"\n--- Next Steps ---\n{next_steps}")

    # Checklist (HeroCoders) — view-only field renders the parsed state
    checklist_view = extract_adf_text(f.get("customfield_10060"))
    progress = f.get("customfield_10028") or ""
    pct = f.get("customfield_10029")
    if checklist_view or progress:
        header = "--- Checklist"
        if progress:
            header += f" ({progress}"
            if pct is not None:
                header += f" — {pct}%"
            header += ")"
        header += " ---"
        print(f"\n{header}")
        # Strip zero-width-space artifacts and normalize the markers
        cleaned = checklist_view.replace("\u200b", "")
        for line in cleaned.split("\n"):
            line = line.rstrip()
            if not line:
                continue
            if line.startswith("# "):
                print(f"  {line}")
            elif line.startswith("* [done]"):
                print(f"  ✓ {line[8:].strip()}")
            elif line.startswith("* [open]"):
                print(f"  ☐ {line[8:].strip()}")
            elif line.startswith("* "):
                print(f"  ☐ {line[2:].strip()}")
            else:
                print(f"  {line}")

    # Linked work items (Jira issue links).
    # Note: in the issuelinks payload, the field name describes the OTHER end:
    #   - link has `inwardIssue`  => current is outward source, other is inward target
    #     (so the verb from current's perspective is type.outward, e.g. "blocks")
    #   - link has `outwardIssue` => current is inward target, other is outward source
    #     (so the verb from current's perspective is type.inward, e.g. "is blocked by")
    issuelinks = f.get("issuelinks") or []
    if issuelinks:
        print(f"\n--- Linked work items ({len(issuelinks)}) ---")
        for link in issuelinks:
            t = link.get("type", {}) or {}
            if link.get("inwardIssue"):
                rel = t.get("outward", "relates to")
                other = link["inwardIssue"]
                arrow = "→"
            else:
                rel = t.get("inward", "related to")
                other = link.get("outwardIssue", {})
                arrow = "←"
            of = other.get("fields", {}) or {}
            status = (of.get("status") or {}).get("name", "")
            summary = of.get("summary", "")
            print(f"  {arrow} {rel}: {other.get('key')} [{status}] {summary[:80]}")

    # Web links (remote links — clickable in the Links panel)
    try:
        rl_url = f"{JIRA_BASE}/rest/api/3/issue/{args.key}/remotelink"
        rl_req = urllib.request.Request(rl_url, headers={"Authorization": auth, "Accept": "application/json"})
        with urllib.request.urlopen(rl_req) as rl_resp:
            remote_links = json.loads(rl_resp.read())
    except Exception:
        remote_links = []
    if remote_links:
        print(f"\n--- Web links ({len(remote_links)}) ---")
        for rl in remote_links:
            obj = rl.get("object", {}) or {}
            print(f"  • {obj.get('title','(no title)')}  {obj.get('url','')}")

    comments = (f.get("comment") or {}).get("comments", [])
    if comments:
        print(f"\n--- Comments ({len(comments)}) ---")
        for c in comments[-3:]:
            author = c.get("author", {}).get("displayName", "?")
            created = c.get("created", "")[:10]
            body = extract_adf_text(c.get("body"))
            print(f"  [{created}] {author}: {body[:200]}")

    print()


if __name__ == "__main__":
    main()
