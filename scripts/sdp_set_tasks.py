#!/usr/bin/env python3
"""
sdp_set_tasks.py — Reconcile SDP tasks against markdown `## Tasks` checkboxes.

Reads cases/{display_id}/*.md, parses `- [x]` / `- [ ]` items in the ## Tasks
section, and upserts SDP tasks to match. Stable identity is the task title.

Usage:
    python3 scripts/sdp_set_tasks.py --id 33903
    python3 scripts/sdp_set_tasks.py --id 33903 --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, SDP_COMMON_CAUSES

from sdp_lib import (
    REPO_ROOT, load_env_file, get_sdp_token, resolve_long_id,
    fetch_request, fetch_tasks, create_task, update_task, delete_task,
    extract_section, parse_tasks_section, _txt,
    TASK_STATUS_OPEN, TASK_STATUS_DONE,
)


def reconcile(long_id: str, display_id: str, token: str, dry_run: bool = False) -> dict:
    case_dir = REPO_ROOT / "cases" / display_id
    if not case_dir.exists():
        return {"error": f"cases/{display_id}/ not found"}
    md_files = list(case_dir.glob("*.md"))
    if not md_files:
        return {"error": f"no markdown in cases/{display_id}/"}
    text = md_files[0].read_text()
    body = extract_section(text, "Tasks") or ""
    desired = parse_tasks_section(body)

    existing = fetch_tasks(long_id, token)
    existing_by_title = {(_txt(t.get("title")).strip()): t for t in existing}

    actions = {"create": [], "close": [], "reopen": [], "noop": []}

    for d in desired:
        title = d["text"]
        desired_status = TASK_STATUS_DONE if d["done"] else TASK_STATUS_OPEN
        existing_task = existing_by_title.pop(title, None)
        if not existing_task:
            actions["create"].append({"title": title, "status": desired_status})
        else:
            current_status = _txt(existing_task.get("status"))
            is_done = "closed" in current_status.lower() or "complete" in current_status.lower()
            should_be_done = d["done"]
            if is_done == should_be_done:
                actions["noop"].append(title)
            elif should_be_done:
                actions["close"].append({"id": _txt(existing_task.get("id")), "title": title})
            else:
                actions["reopen"].append({"id": _txt(existing_task.get("id")), "title": title})

    # Tasks present in SDP but not in markdown — leave as-is (don't auto-delete)
    actions["orphans_in_sdp"] = [_txt(t.get("title")) for t in existing_by_title.values()]

    if dry_run:
        return {"dry_run": True, "actions": actions}

    for c in actions["create"]:
        create_task(long_id, c["title"], token, status=c["status"])
    for c in actions["close"]:
        update_task(long_id, c["id"], token, status=TASK_STATUS_DONE)
    for r in actions["reopen"]:
        update_task(long_id, r["id"], token, status=TASK_STATUS_OPEN)

    return {"actions": actions}


def main():
    load_env_file()
    p = argparse.ArgumentParser(description="Reconcile SDP tasks from markdown")
    p.add_argument("--id", required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    token = get_sdp_token()
    long_id = resolve_long_id(args.id, token)
    request = fetch_request(long_id, token)
    display_id = _txt(request.get("display_id"))
    result = reconcile(long_id, display_id, token, dry_run=args.dry_run)
    print(json.dumps(result, indent=2))
    if "error" in result:
        fail(
            result["error"],
            causes=["Case directory or markdown file missing for this SDP ID"],
            try_=[f"python3 scripts/sdp_create_stub.py --id {args.id}",
                  f"ls cases/{display_id}/"],
        )


if __name__ == "__main__":
    main()
