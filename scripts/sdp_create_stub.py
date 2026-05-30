#!/usr/bin/env python3
"""
sdp_create_stub.py — Create a local cases/{ID}/{ID} - {Summary}.md stub for a
known SDP request. Pulls subject/requester/description from SDP and writes the
canonical case template.

Mirror of jira_create_stub.py.

Usage:
    python3 scripts/sdp_create_stub.py --id 33903
    python3 scripts/sdp_create_stub.py --id 33903 --owner sdp --lane sdp_approval
    python3 scripts/sdp_create_stub.py --id 33903 --jira <PROJECT>-368
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, SDP_COMMON_CAUSES

from sdp_lib import (
    REPO_ROOT, load_env_file, get_sdp_token, resolve_long_id, fetch_request,
    get_tags, _txt, classify_lane,
)


SAFE_CHARS_RE = None  # filled lazily
def _safe_filename(s: str) -> str:
    import re
    return re.sub(r"[^\w\s().-]", "", s).strip()[:90]


CASE_TEMPLATE = """# {display_id} - {subject}

**SDP Request:** [#{display_id} — {subject}]({url})
**Long ID:** {long_id}
{jira_line}**OWNER:** {owner}
**Tags:** {tags}
**Urgency:** {urgency}
**Importance:** {importance}
**Agentic:** {agentic}
**Approvers:** {approvers}
**Status:** {status}
**Created:** {created}
**Requester:** {requester_full}
**Technician:** {technician}

---

## 📰 Clerk Card

> **Lede.** {requester} requested: {subject}. Assigned to {technician}.
>
> **Status.** {status} — awaiting investigation.
>
> **Next.** Investigate and update this clerk card with findings.
>
> **Links:**
> - [SDP #{display_id} — request details]({url})

---

## Description

------------------------------------------------

{description}

## Investigation

------------------------------------------------


## Actions

------------------------------------------------

### {now}

- WORKLOG 0m: Created case file stub from SDP.

## Tasks

------------------------------------------------


## Web Links

------------------------------------------------


## Linked Requests

------------------------------------------------


## Approval

------------------------------------------------


## Follow-up

------------------------------------------------
Status:
TODO:
"""


def main():
    load_env_file()
    p = argparse.ArgumentParser(description="Create local SDP case markdown stub")
    p.add_argument("--id", required=True)
    p.add_argument("--owner", choices=["sdp", "jira"], default="sdp")
    p.add_argument("--jira", help="Linked Jira key (e.g. <PROJECT>-368) — sets OWNER if absent")
    p.add_argument("--urgency", default="3", help="1-5")
    p.add_argument("--importance", default="3", help="1-5")
    p.add_argument("--agentic", default="4", help="1-5 (SDP default: 4 = mostly manual)")
    p.add_argument("--approvers", default="", help="Comma-separated approver emails")
    p.add_argument("--force", action="store_true", help="Overwrite if file exists")
    args = p.parse_args()

    token = get_sdp_token()
    long_id = resolve_long_id(args.id, token)
    request = fetch_request(long_id, token)
    if not request:
        fail(
            f"SDP request {args.id} not found",
            causes=["Request was deleted or ID is wrong", "display_id vs long ID confusion"],
            try_=[f"python3 scripts/sdp_fetch_ticket.py --id {args.id}",
                  f"Verify: https://<YOUR_SDP>.sdpondemand.manageengine.com/app/itdesk/ui/requests/{args.id}"],
        )

    display_id = _txt(request.get("display_id"))
    subject = _txt(request.get("subject")).strip()
    description = _txt(request.get("description")).strip()
    requester = _txt((request.get("requester") or {}).get("name"))
    req_email = _txt((request.get("requester") or {}).get("email_id"))
    created = _txt((request.get("created_time") or {}).get("display_value"))
    status = _txt(request.get("status"))
    tech = _txt((request.get("technician") or {}).get("name"))
    group = _txt(request.get("group"))
    urgency_api = _txt(request.get("urgency"))
    tags = get_tags(request)

    case_dir = REPO_ROOT / "cases" / display_id
    case_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{display_id} - {_safe_filename(subject) or 'untitled'}.md"
    path = case_dir / fname

    if path.exists() and not args.force:
        print(f"⚠ Already exists: {path.relative_to(REPO_ROOT)}")
        sys.exit(0)

    jira_line = f"**JIRA:** {args.jira}\n" if args.jira else ""
    requester_full = f"{requester} <{req_email}>" if req_email else requester
    technician = f"{tech} ({group})" if group else tech
    url = f"https://<YOUR_SDP>.sdpondemand.manageengine.com/app/itdesk/ui/requests/{long_id}/details"

    # Determine flow tag from status
    flow_map = {
        'Open': 'flow:queue', 'In Progress': 'flow:active',
        'Waiting for Review': 'flow:waiting', 'On Hold': 'flow:waiting',
        'Resolved': 'flow:done', 'Closed': 'flow:done', 'Canceled': 'flow:done',
    }
    flow = flow_map.get(status, 'flow:queue')

    content = CASE_TEMPLATE.format(
        display_id=display_id,
        subject=subject,
        long_id=long_id,
        jira_line=jira_line,
        owner=args.owner,
        tags=flow,
        urgency=urgency_api or args.urgency,
        importance=args.importance,
        agentic=args.agentic,
        approvers=args.approvers or "—",
        status=status,
        requester=requester,
        requester_full=requester_full,
        technician=technician,
        created=created,
        url=url,
        description=description or "(no description)",
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    path.write_text(content)
    print(f"✓ Created {path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
