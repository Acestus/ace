#!/usr/bin/env python3
"""
sdp_context_bundle.py — Fetch comprehensive context for an SDP request in one call.

Replaces 4-7 serial script invocations with a single composite fetch.
Used by sdp-rounds, sdp-investigator, start-my-day, weekly-summary.

Modes:
    work    — Full context: request + notes + worklogs + tasks + approvals
              + linked_requests + history + related cases (default)
    review  — Approval-ready: request + recent notes + history (small)
    brief   — Summary only: request metadata + tag/lane state

Usage:
    python3 scripts/sdp_context_bundle.py --id 33903
    python3 scripts/sdp_context_bundle.py --id 33903 --mode review
    python3 scripts/sdp_context_bundle.py --id 33903 --json
    python3 scripts/sdp_context_bundle.py --id 33903 --related
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, SDP_COMMON_CAUSES

from sdp_lib import (
    REPO_ROOT, load_env_file, get_sdp_token, resolve_long_id,
    fetch_request, fetch_notes, fetch_worklogs, fetch_tasks,
    fetch_approval_levels, fetch_approvals, fetch_linked_requests,
    fetch_history, search_requests, request_url, get_tags, _txt,
    parse_case_header, classify_lane,
)


def fetch_related_cases(subject: str, exclude_id: str, token: str) -> list[dict]:
    """Find SDP cases with overlapping keywords in subject."""
    import re
    words = [w for w in re.split(r"\W+", subject or "") if len(w) > 3][:4]
    if not words:
        return []
    try:
        results = search_requests(
            {"search_fields": {"subject": " ".join(words)}},
            token, row_count=10,
            fields=["id", "display_id", "subject", "status", "created_time"],
        )
    except Exception:
        return []
    return [r for r in results if _txt(r.get("id")) != exclude_id][:5]


def find_case_file(display_id: str) -> dict | None:
    """Look for cases/{display_id}/*.md, return {path, header, summary}."""
    case_dir = REPO_ROOT / "cases" / display_id
    if not case_dir.exists():
        return None
    for md in case_dir.glob("*.md"):
        text = md.read_text()
        return {
            "path": str(md.relative_to(REPO_ROOT)),
            "header": parse_case_header(text),
            "first_lines": "\n".join(text.splitlines()[:20]),
        }
    return None


def build_bundle(display_or_long: str, mode: str, include_related: bool, token: str) -> dict:
    long_id = resolve_long_id(display_or_long, token)
    request = fetch_request(long_id, token)
    if not request:
        return {"error": f"Request {display_or_long} not found"}

    display_id = _txt(request.get("display_id"))
    bundle = {
        "request": {
            "id": long_id,
            "display_id": display_id,
            "subject": _txt(request.get("subject")),
            "status": _txt(request.get("status")),
            "priority": _txt(request.get("priority")),
            "urgency": _txt(request.get("urgency")),
            "impact": _txt(request.get("impact")),
            "category": _txt(request.get("category")),
            "subcategory": _txt(request.get("subcategory")),
            "group": _txt(request.get("group")),
            "technician": _txt(request.get("technician")),
            "requester": _txt((request.get("requester") or {}).get("name")),
            "requester_email": _txt((request.get("requester") or {}).get("email_id")),
            "created": _txt((request.get("created_time") or {}).get("display_value")),
            "due_by": _txt((request.get("due_by_time") or {}).get("display_value")),
            "approval_status": _txt(request.get("approval_status")),
            "tags": get_tags(request),
            "description": _txt(request.get("description")),
            "url": request_url(long_id),
        },
        "mode": mode,
    }

    case_file = find_case_file(display_id)
    if case_file:
        bundle["case_file"] = case_file
        bundle["lane"] = classify_lane(case_file["header"])
    else:
        bundle["lane"] = "sdp_approval"

    if mode == "brief":
        return bundle

    # Common: notes + worklogs
    notes = fetch_notes(long_id, token, row_count=20 if mode == "review" else 50)
    bundle["notes"] = [
        {
            "id": _txt(n.get("id")),
            "created": _txt((n.get("created_time") or {}).get("display_value")),
            "by": _txt((n.get("created_by") or {}).get("name")),
            "show_to_requester": n.get("show_to_requester"),
            "description": _txt(n.get("description"))[:1000],
        }
        for n in notes
    ]

    if mode == "review":
        bundle["history"] = fetch_history(long_id, token, row_count=20)
        return bundle

    # work mode: full bundle
    bundle["worklogs"] = [
        {
            "id": _txt(w.get("id")),
            "by": _txt((w.get("owner") or {}).get("name")),
            "time": f"{_txt((w.get('time_spent') or {}).get('hours'))}h{_txt((w.get('time_spent') or {}).get('minutes'))}m",
            "description": _txt(w.get("description"))[:500],
            "start": _txt((w.get("start_time") or {}).get("display_value")),
        }
        for w in fetch_worklogs(long_id, token)
    ]

    tasks = fetch_tasks(long_id, token)
    bundle["tasks"] = [
        {
            "id": _txt(t.get("id")),
            "title": _txt(t.get("title")),
            "status": _txt(t.get("status")),
            "owner": _txt((t.get("owner") or {}).get("name")),
        }
        for t in tasks
    ]

    levels = fetch_approval_levels(long_id, token)
    bundle["approval_levels"] = []
    for lv in levels:
        lv_id = _txt(lv.get("id"))
        approvers = fetch_approvals(long_id, lv_id, token) if lv_id else []
        bundle["approval_levels"].append({
            "id": lv_id,
            "level": lv.get("level"),
            "status": _txt(lv.get("status")),
            "approvers": [
                {
                    "email": _txt((a.get("approver") or {}).get("email_id")),
                    "name": _txt((a.get("approver") or {}).get("name")),
                    "status": _txt(a.get("status")),
                }
                for a in approvers
            ],
        })

    bundle["linked_requests"] = [
        {
            "id": _txt((lr.get("linked_request") or {}).get("id")),
            "display_id": _txt((lr.get("linked_request") or {}).get("display_id")),
            "subject": _txt((lr.get("linked_request") or {}).get("subject")),
            "status": _txt((lr.get("linked_request") or {}).get("status")),
        }
        for lr in fetch_linked_requests(long_id, token)
    ]

    bundle["history"] = fetch_history(long_id, token, row_count=40)

    if include_related:
        bundle["related_cases"] = [
            {
                "id": _txt(r.get("id")),
                "display_id": _txt(r.get("display_id")),
                "subject": _txt(r.get("subject")),
                "status": _txt(r.get("status")),
            }
            for r in fetch_related_cases(bundle["request"]["subject"], long_id, token)
        ]

    return bundle


def print_human(b: dict) -> None:
    r = b["request"]
    print(f"\n📋  SDP #{r['display_id']} — {r['subject']}")
    print(f"    Long ID   : {r['id']}")
    print(f"    Requester : {r['requester']} <{r['requester_email']}>")
    print(f"    Status    : {r['status']}  |  Priority: {r['priority']}  |  Urgency: {r['urgency']}")
    print(f"    Group     : {r['group']}  |  Tech: {r['technician']}")
    print(f"    Tags      : {', '.join(r['tags']) or '—'}")
    print(f"    Lane      : {b.get('lane', '—')}")
    print(f"    Approval  : {r['approval_status'] or '—'}")
    print(f"    Created   : {r['created']}  |  Due: {r['due_by'] or '—'}")
    print(f"    URL       : {r['url']}")

    if cf := b.get("case_file"):
        print(f"\n📁  Case file: {cf['path']}")
        if cf["header"]:
            for k, v in cf["header"].items():
                print(f"    {k}: {v}")

    if b.get("mode") == "brief":
        return

    if notes := b.get("notes"):
        print(f"\n💬  Notes ({len(notes)} recent):")
        for n in notes[:5]:
            visibility = "👤" if n.get("show_to_requester") else "🔒"
            print(f"    {visibility} [{n['created']}] {n['by']}: {n['description'][:120]}")

    if tasks := b.get("tasks"):
        print(f"\n☑  Tasks ({len(tasks)}):")
        for t in tasks:
            mark = "[x]" if "closed" in (t["status"] or "").lower() or "complete" in (t["status"] or "").lower() else "[ ]"
            print(f"    {mark} {t['title']}  ({t['status']})")

    if levels := b.get("approval_levels"):
        print(f"\n🔏  Approvals:")
        for lv in levels:
            print(f"    L{lv['level']} [{lv['status']}]:")
            for a in lv["approvers"]:
                print(f"      - {a['name']} <{a['email']}> [{a['status']}]")

    if links := b.get("linked_requests"):
        print(f"\n🔗  Linked requests ({len(links)}):")
        for lr in links:
            print(f"    SDP-{lr['display_id']} [{lr['status']}] — {lr['subject']}")

    if rel := b.get("related_cases"):
        print(f"\n🔎  Related cases ({len(rel)}):")
        for r in rel:
            print(f"    SDP-{r['display_id']} [{r['status']}] — {r['subject']}")

    if wl := b.get("worklogs"):
        print(f"\n⏱  Worklogs ({len(wl)}):")
        for w in wl[:5]:
            print(f"    [{w['start']}] {w['by']} ({w['time']}): {w['description'][:100]}")


def main():
    load_env_file()
    p = argparse.ArgumentParser(description="Fetch comprehensive SDP request context")
    p.add_argument("--id", required=True, help="SDP display id (33903) or long id")
    p.add_argument("--mode", choices=["work", "review", "brief"], default="work")
    p.add_argument("--related", action="store_true",
                   help="Include related cases (subject keyword search)")
    p.add_argument("--json", action="store_true", help="Output JSON")
    args = p.parse_args()

    token = get_sdp_token()
    bundle = build_bundle(args.id, args.mode, args.related, token)
    if "error" in bundle:
        fail(
            bundle["error"],
            causes=["SDP request ID not found or API error during bundle fetch"],
            try_=[f"python3 scripts/sdp_fetch_ticket.py --id {args.id}",
                  f"python3 scripts/sdp_context_bundle.py --id {args.id} --mode brief"],
        )

    if args.json:
        print(json.dumps(bundle, indent=2, default=str))
    else:
        print_human(bundle)


if __name__ == "__main__":
    main()
