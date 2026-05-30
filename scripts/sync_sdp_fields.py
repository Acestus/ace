#!/usr/bin/env python3
"""
sync_sdp_fields.py — Reconcile structured SDP state from case markdown.

Parses a `cases/<DISPLAY_ID>/<DISPLAY_ID> - <summary>.md` file and pushes the
declared state to SDP:

  ## Clerk Card + ## Web Links
                  → SDP note (HTML context card posted once as an internal note;
                    idempotent — skipped if a "📰 Context Card" note already exists).
                    The original SDP description is never modified.

  Header (Tags:)  → SDP tags (only the Tags: line; scoring labels stay markdown-only)

  ## Tasks        → SDP tasks (markdown-driven; missing in MD = leave in SDP,
                    new in MD = create, status toggles bidirectional)

  ## Linked Requests → SDP linked_requests (additive — never auto-delete)

  ## Approval     → SDP approval_levels + approvers (additive)

The file is the source of truth (for tasks: bidirectional). Re-running on an
unchanged file is a no-op. All API calls use a single cached OAuth token
(3600s lifetime, refreshed once at start).

Mirror of sync_jira_fields.py for SDP.

Usage:
    python3 scripts/sync_sdp_fields.py --file 'cases/33903/33903 - .....md'
    python3 scripts/sync_sdp_fields.py --id 33903     # auto-locate file
    python3 scripts/sync_sdp_fields.py --changed-since <SHA>
    python3 scripts/sync_sdp_fields.py --all
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

from sdp_lib import (
    REPO_ROOT, load_env_file, get_sdp_token, resolve_long_id, fetch_request,
    get_tags, put_tags, _txt, parse_case_header, FLOW_TAGS,
    extract_section, parse_links_section, build_html_description, fetch_notes, add_note,
    FLOW_STATUS_MAP, WAITING_STATUSES, transition_status,
)

# Reuse reconciliation functions from per-area scripts
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from lib.errors import fail, require_env, SDP_COMMON_CAUSES
from sdp_set_tasks import reconcile as reconcile_tasks
from sdp_set_links import reconcile as reconcile_links
from sdp_approval import reconcile_from_markdown as reconcile_approval

CASES_DIR = REPO_ROOT / "cases"
SDP_ID_RE = re.compile(r"^(\d{4,8})\b")


def find_file_for_id(display_id: str) -> Path | None:
    case_dir = CASES_DIR / display_id
    if not case_dir.exists():
        return None
    mds = list(case_dir.glob("*.md"))
    return mds[0] if mds else None


def display_id_from_path(path: Path) -> str | None:
    m = SDP_ID_RE.match(path.stem)
    return m.group(1) if m else None


def changed_files(since_ref: str) -> list[Path]:
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", since_ref, "--", "cases/"],
            cwd=REPO_ROOT, text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"git diff failed: {e}", file=sys.stderr)
        return []
    return [REPO_ROOT / line for line in out.splitlines() if line.endswith(".md")]


def all_case_files() -> list[Path]:
    return sorted(CASES_DIR.glob("*/*.md"))


def reconcile_tags(long_id: str, header: dict, token: str, dry_run: bool = False) -> dict:
    """
    Header `Tags:` line is the source of truth for non-flow tags.
    flow:* tags are preserved (managed by sdp_set_flow).
    """
    raw = header.get("tags") or ""
    desired = set(t.strip() for t in raw.split(",") if t.strip() and t != "—")

    request = fetch_request(long_id, token)
    current = set(get_tags(request))
    current_flow = current & FLOW_TAGS
    target = desired | current_flow
    if target == current:
        return {"tags": "noop"}
    if dry_run:
        return {"tags_current": sorted(current), "tags_target": sorted(target), "dry_run": True}
    put_tags(long_id, sorted(target), token)
    return {"tags_set": sorted(target)}


def reconcile_status(long_id: str, header: dict, token: str, dry_run: bool = False) -> dict:
    """
    Transition SDP ticket status to match the flow: tag in the markdown.

    Mapping:
        flow:queue   → Open
        flow:active  → Open (no native In Progress)
        flow:waiting → Waiting for Review
        flow:done    → Resolved (never Closed — requester must accept first)

    Skips transition if current status already matches the expected state.
    Never auto-closes or auto-resolves (flow:done is skipped for safety).
    """
    tags_raw = header.get("tags") or ""
    flow_tag = None
    for t in tags_raw.split(","):
        t = t.strip()
        if t in FLOW_TAGS:
            flow_tag = t
            break
    if not flow_tag:
        return {"status": "noop", "reason": "no flow tag in header"}

    flow_state = flow_tag.replace("flow:", "")

    # Safety: never auto-resolve/close via CI/CD — only waiting and open transitions
    if flow_state == "done":
        return {"status": "noop", "reason": "flow:done skipped (manual close only)"}

    expected_status = FLOW_STATUS_MAP.get(flow_state)
    if not expected_status:
        return {"status": "noop", "reason": f"no mapping for {flow_state}"}

    # Get current SDP status
    request = fetch_request(long_id, token)
    current_status = _txt(request.get("status"))

    # Already in correct state?
    if current_status == expected_status:
        return {"status": "noop", "current": current_status}

    # If current is already a waiting subtype and expected is generic waiting, skip
    if flow_state == "waiting" and current_status in WAITING_STATUSES:
        return {"status": "noop", "current": current_status, "reason": "already in waiting subtype"}

    if dry_run:
        return {"status_transition": f"{current_status} → {expected_status}", "dry_run": True}

    transition_status(long_id, expected_status, token)
    return {"status_transitioned": f"{current_status} → {expected_status}"}

CONTEXT_CARD_MARKER = "📰 Context Card"


def reconcile_context_note(long_id: str, display_id: str, text: str,
                           token: str, dry_run: bool = False) -> dict:
    """Post the clerk card + web links as an internal note (idempotent).

    The original SDP description is never touched. If a note containing the
    context card marker already exists the call is a no-op.
    """
    clerk_card = extract_section(text, "📰 Clerk Card") or extract_section(text, "Clerk Card") or ""
    links_body = extract_section(text, "Web Links") or ""
    web_links = parse_links_section(links_body)

    if not clerk_card and not web_links:
        return {"context_note": "noop", "reason": "no clerk card or web links"}

    # Idempotency: skip if a context card note already exists
    existing = fetch_notes(long_id, token, row_count=50)
    for note in existing:
        desc = _txt(note.get("description", ""))
        if CONTEXT_CARD_MARKER in desc:
            return {"context_note": "noop", "reason": "already posted"}

    html = build_html_description(clerk_card, web_links, original_request="")

    if dry_run:
        return {"dry_run": True, "html_length": len(html),
                "links_count": len(web_links), "has_clerk_card": bool(clerk_card)}

    result = add_note(long_id, html, token, show_to_requester=False)
    status = result.get("response_status", {}).get("status", "unknown")
    return {"context_note": status, "html_length": len(html), "links_count": len(web_links)}


def process_file(path: Path, token: str, dry_run: bool = False) -> dict:
    text = path.read_text()
    header = parse_case_header(text)
    display_id = header.get("sdp_display_id") or display_id_from_path(path)
    if not display_id:
        return {"file": str(path), "skipped": "no display_id"}

    long_id = header.get("sdp_id") or resolve_long_id(display_id, token)
    summary: dict = {"file": str(path.relative_to(REPO_ROOT)), "display_id": display_id}

    # Context card note (HTML clerk card + clickable web links) — posted once, never overwrites description
    try:
        summary["context_note"] = reconcile_context_note(
            long_id, display_id, text, token, dry_run=dry_run)
    except Exception as e:
        summary["context_note_error"] = str(e)

    try:
        summary.update(reconcile_tags(long_id, header, token, dry_run=dry_run))
    except Exception as e:
        summary["tags_error"] = str(e)
    try:
        summary["tasks"] = reconcile_tasks(long_id, display_id, token, dry_run=dry_run)
    except Exception as e:
        summary["tasks_error"] = str(e)
    try:
        summary["linked_requests"] = reconcile_links(long_id, display_id, token, dry_run=dry_run)
    except Exception as e:
        summary["linked_requests_error"] = str(e)
    try:
        summary["approval"] = reconcile_approval(long_id, display_id, token, dry_run=dry_run)
    except Exception as e:
        summary["approval_error"] = str(e)
    try:
        summary["status"] = reconcile_status(long_id, header, token, dry_run=dry_run)
    except Exception as e:
        summary["status_error"] = str(e)
    return summary


def main():
    load_env_file()
    p = argparse.ArgumentParser(description="Reconcile SDP state from markdown")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--file")
    g.add_argument("--id")
    g.add_argument("--changed-since", metavar="REF")
    g.add_argument("--all", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.file:
        files = [Path(args.file)]
    elif args.id:
        f = find_file_for_id(args.id)
        if not f:
            fail(
                f"No case file for SDP-{args.id}",
                causes=["Stub was never created for this ID",
                        "Case directory uses a different display ID"],
                try_=[f"python3 scripts/sdp_create_stub.py --id {args.id}",
                      f"ls cases/ | grep {args.id}"],
            )
        files = [f]
    elif args.changed_since:
        files = changed_files(args.changed_since)
    else:
        files = all_case_files()

    if not files:
        print("No case files to process.")
        return

    token = get_sdp_token()
    import json
    for f in files:
        result = process_file(f, token, dry_run=args.dry_run)
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
