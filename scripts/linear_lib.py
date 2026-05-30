#!/usr/bin/env python3
"""
linear_lib.py — Shared helpers for Linear API automation scripts.

Linear uses a GraphQL API at https://api.linear.app/graphql.
Auth: Authorization: {LINEAR_API_KEY}  (Bearer not required — raw key works)

Priority mapping (Linear native → Eisenhower urgency):
  0  = No Priority → urgency:5
  1  = Urgent      → urgency:1
  2  = High        → urgency:2
  3  = Medium      → urgency:3
  4  = Low         → urgency:4

Flow label → Linear state mapping (configure per team in .env or SKILL.md):
  flow:queue   → "Backlog" or "Todo"
  flow:active  → "In Progress"
  flow:waiting → "In Review"
  flow:done    → "Done"
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

LINEAR_API_URL = "https://api.linear.app/graphql"

PRIORITY_TO_URGENCY = {0: 5, 1: 1, 2: 2, 3: 3, 4: 4}
URGENCY_TO_PRIORITY = {5: 0, 1: 1, 2: 2, 3: 3, 4: 4}
PRIORITY_LABELS = {0: "No Priority", 1: "Urgent", 2: "High", 3: "Medium", 4: "Low"}

# Default flow→state name mapping. Override in .env:
# LINEAR_STATE_QUEUE=Backlog
# LINEAR_STATE_ACTIVE=In Progress
# LINEAR_STATE_WAITING=In Review
# LINEAR_STATE_DONE=Done
DEFAULT_STATE_MAP = {
    "queue":   "Backlog",
    "active":  "In Progress",
    "waiting": "In Review",
    "done":    "Done",
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


def get_api_key() -> str:
    load_env_file()
    key = os.environ.get("LINEAR_API_KEY", "")
    if not key:
        sys.exit(
            "LINEAR_API_KEY not set.\n"
            "Add to your .env file:\n"
            "  LINEAR_API_KEY=lin_api_xxxxxxxxxxxx\n"
            "Get a key at: https://linear.app/settings/api"
        )
    return key


def graphql(query: str, variables: dict | None = None) -> dict:
    """Execute a GraphQL query against the Linear API."""
    api_key = get_api_key()
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(LINEAR_API_URL, data=payload, method="POST")
    req.add_header("Authorization", api_key)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        sys.exit(f"Linear API HTTP {e.code}: {body}")
    if "errors" in data:
        msgs = [e.get("message", str(e)) for e in data["errors"]]
        sys.exit(f"Linear API error: {'; '.join(msgs)}")
    return data.get("data", {})


def flow_to_state_name(flow: str) -> str:
    """Map flow:* label to Linear state name, respecting env overrides."""
    load_env_file()
    env_key = f"LINEAR_STATE_{flow.upper()}"
    return os.environ.get(env_key, DEFAULT_STATE_MAP.get(flow, "Backlog"))


def priority_to_urgency(priority: int) -> int:
    return PRIORITY_TO_URGENCY.get(priority, 5)


def urgency_to_priority(urgency: int) -> int:
    return URGENCY_TO_PRIORITY.get(urgency, 0)


def format_issue_header(issue: dict) -> str:
    """Render a compact one-line summary of a Linear issue."""
    ident = issue.get("identifier", "???")
    title = issue.get("title", "")
    state = (issue.get("state") or {}).get("name", "?")
    priority = PRIORITY_LABELS.get(issue.get("priority", 0), "?")
    return f"{ident} [{state}] ({priority}) — {title}"
