"""
scripts/lib/errors.py — Actionable error helpers.

Every script in scripts/ should use these helpers instead of ad-hoc
print/sys.exit. The goal: every failure tells the next agent
*what failed*, *why*, and *what to try next*.

Usage
-----

    from lib.errors import (
        fail, require_env, require_tool,
        http_fail, JIRA_COMMON_CAUSES,
    )

    require_env(
        "CONFLUENCE_EMAIL", "WWEEKS_CONFLUENCE_API_TOKEN",
        hint="Load .env: export $(grep -v '^#' .env | xargs)",
    )

    try:
        resp = urlopen(req)
    except urllib.error.HTTPError as e:
        http_fail(e, api_name="Jira", key=args.key,
                  common_causes=JIRA_COMMON_CAUSES)

Or for non-HTTP failures:

    fail("Issue file not found",
         causes=[f"Stub never created for {key}",
                 "Key typo in --key argument"],
         try_=[f"python3 scripts/jira_create_stub.py --key {key}",
               "ls issues/ | grep -i <partial-key>"],
         docs="docs/issue-file-format.md")

Import note
-----------
To import from a script in scripts/, prepend scripts/ to sys.path
*before* importing (boilerplate at the top of each script):

    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    from lib.errors import fail, require_env, http_fail
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import urllib.error
from typing import Iterable, Mapping, Optional


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def _print_block(
    summary: str,
    *,
    causes: Optional[Iterable[str]] = None,
    try_: Optional[Iterable[str]] = None,
    docs: Optional[str] = None,
    icon: str = "❌",
    stream=sys.stderr,
) -> None:
    """Render the standard actionable-error block."""
    print(f"{icon} {summary}", file=stream)
    if causes:
        print("   Likely causes:", file=stream)
        for c in causes:
            print(f"     • {c}", file=stream)
    if try_:
        print("   Try:", file=stream)
        for t in try_:
            print(f"     • {t}", file=stream)
    if docs:
        print(f"   Docs: {docs}", file=stream)


def fail(
    summary: str,
    *,
    causes: Optional[Iterable[str]] = None,
    try_: Optional[Iterable[str]] = None,
    docs: Optional[str] = None,
    exit_code: int = 1,
) -> None:
    """Print an actionable failure block and exit.

    Always provide at least `try_` — if you can't name a next step,
    the error is not actionable enough yet.
    """
    _print_block(summary, causes=causes, try_=try_, docs=docs)
    sys.exit(exit_code)


def warn(
    summary: str,
    *,
    causes: Optional[Iterable[str]] = None,
    try_: Optional[Iterable[str]] = None,
    docs: Optional[str] = None,
) -> None:
    """Print an actionable warning block; do not exit."""
    _print_block(summary, causes=causes, try_=try_, docs=docs, icon="⚠️ ")


# ---------------------------------------------------------------------------
# Preflight validators
# ---------------------------------------------------------------------------


def require_env(
    *keys: str,
    hint: Optional[str] = None,
    env_file: str = ".env",
) -> None:
    """Fail fast if any of these env vars are missing or empty."""
    missing = [k for k in keys if not os.environ.get(k)]
    if not missing:
        return

    causes = [
        f"{env_file} not loaded into current shell",
        f"Missing from {env_file}: {', '.join(missing)}",
        "Running outside the projects/ repo root",
    ]
    try_ = [
        f"cd /home/wweeks/git/projects && export $(grep -v '^#' {env_file} | xargs)",
        f"grep -E '^({'|'.join(missing)})=' {env_file}",
    ]
    if hint:
        try_.insert(0, hint)
    fail(
        f"Required environment variable(s) not set: {', '.join(missing)}",
        causes=causes,
        try_=try_,
    )


def require_tool(
    name: str,
    *,
    install: Optional[str] = None,
    docs: Optional[str] = None,
) -> None:
    """Fail fast if a CLI tool is not on PATH."""
    if shutil.which(name):
        return
    try_ = []
    if install:
        try_.append(install)
    try_.append(f"which {name}")
    try_.append("echo $PATH")
    fail(
        f"Required CLI tool not found on PATH: {name}",
        causes=[
            f"{name} is not installed",
            "Wrong shell — running in a stripped environment (cron, CI)",
            "PATH does not include the install location",
        ],
        try_=try_,
        docs=docs,
    )


# ---------------------------------------------------------------------------
# HTTP failure translator
# ---------------------------------------------------------------------------


def http_fail(
    err: urllib.error.HTTPError,
    *,
    api_name: str,
    key: Optional[str] = None,
    operation: Optional[str] = None,
    common_causes: Optional[Mapping[int, dict]] = None,
    extra_try: Optional[Iterable[str]] = None,
) -> None:
    """Translate a urllib HTTPError into an actionable failure block.

    `common_causes` maps status codes to a dict with:
        {"causes": [...], "try": [...], "docs": "..."}
    See JIRA_COMMON_CAUSES below for the canonical shape.
    """
    code = err.code
    try:
        body = err.read().decode(errors="replace")
    except Exception:
        body = ""
    body_snippet = body[:300].strip()
    # Try to extract a useful message from JSON bodies
    body_msg = ""
    if body_snippet.startswith("{"):
        try:
            j = json.loads(body)
            for fld in ("errorMessages", "errors", "message", "error", "detail"):
                if fld in j and j[fld]:
                    body_msg = json.dumps(j[fld])[:200]
                    break
        except Exception:
            pass

    op = operation or "request"
    target = f" for {key}" if key else ""
    summary = f"{api_name} API rejected {op}{target} ({code} {err.reason})"
    if body_msg:
        summary += f" — {body_msg}"

    info = (common_causes or {}).get(code, {})
    causes = info.get("causes")
    try_ = list(info.get("try", []))
    if extra_try:
        try_.extend(extra_try)
    docs = info.get("docs")

    # Always show the raw body snippet as the last "try" so debug context survives
    if body_snippet and not body_msg:
        try_.append(f"Raw body: {body_snippet}")

    fail(summary, causes=causes, try_=try_ or None, docs=docs)


# ---------------------------------------------------------------------------
# Common-cause dictionaries (per API)
# ---------------------------------------------------------------------------


JIRA_COMMON_CAUSES: dict = {
    400: {
        "causes": [
            "Invalid field name or value in payload",
            "Required field missing for this issue type",
            "Transition ID does not exist in this workflow",
        ],
        "try": [
            "python3 scripts/jira_fetch_ticket.py --key <KEY> --raw  # inspect schema",
            "Check transition IDs: curl -u $CONFLUENCE_EMAIL:$WWEEKS_CONFLUENCE_API_TOKEN https://<YOUR_ATLASSIAN>.atlassian.net/rest/api/3/issue/<KEY>/transitions",
        ],
    },
    401: {
        "causes": [
            "WWEEKS_CONFLUENCE_API_TOKEN is expired or revoked",
            "CONFLUENCE_EMAIL does not match the token owner",
        ],
        "try": [
            "Regenerate token: https://id.atlassian.com/manage-profile/security/api-tokens",
            "grep CONFLUENCE_ .env",
        ],
    },
    403: {
        "causes": [
            "Account lacks permission on this project/issue",
            "Browse Projects permission missing",
            "Workflow guard prevents this transition for your role",
        ],
        "try": [
            "Check project permissions in Jira UI → Project settings → Permissions",
            "Ask a Jira admin to add the account to the right role",
        ],
    },
    404: {
        "causes": [
            "Issue key is wrong (typo, deleted, moved project)",
            "Account does not have Browse permission so issue appears missing",
            "Custom field ID does not exist in this Jira instance",
        ],
        "try": [
            "python3 scripts/jira_search.py --jql 'key = <KEY>'",
            "Verify in browser: https://<YOUR_ATLASSIAN>.atlassian.net/browse/<KEY>",
        ],
    },
    429: {
        "causes": ["Rate limited by Jira Cloud"],
        "try": [
            "Wait 60s and retry",
            "Batch operations — Jira Cloud limit is ~10 req/s per user",
        ],
    },
    500: {
        "causes": [
            "Atlassian-side incident",
            "Malformed ADF in a comment body",
        ],
        "try": [
            "Check status: https://status.atlassian.com/",
            "Retry with simplified payload",
        ],
    },
}


SDP_COMMON_CAUSES: dict = {
    400: {
        "causes": [
            "Invalid input_data JSON shape",
            "Field name does not match SDP schema (camelCase vs snake_case)",
            "Status name does not exist in the SDP instance",
        ],
        "try": [
            "python3 scripts/sdp_fetch_ticket.py --id <ID> --raw  # inspect schema",
            "Inspect transitions: python3 scripts/sdp_changelog.py --id <ID>",
        ],
    },
    401: {
        "causes": [
            "SDP_AUTH_TOKEN expired or revoked",
            "SDP_PORTAL_NAME wrong (should be '<org_short>' not full URL)",
        ],
        "try": [
            "Regenerate API key in SDP → Personalize → API Key",
            "grep SDP_ .env",
        ],
    },
    403: {
        "causes": [
            "API key technician role missing required permissions",
            "Request is in a status that blocks the operation",
        ],
        "try": [
            "Check technician role in SDP admin",
            "python3 scripts/sdp_fetch_ticket.py --id <ID>  # check current status",
        ],
    },
    404: {
        "causes": [
            "Request ID does not exist (deleted, or short vs long ID confusion)",
            "Wrong portal: SDP_PORTAL_NAME mismatched to SDP_AUTH_TOKEN",
        ],
        "try": [
            "Verify in browser: https://<YOUR_SDP>.sdpondemand.manageengine.com/app/itdesk/ui/requests/<ID>",
            "Check long ID in cases/<ID>/*.md header (**Long ID:**)",
        ],
    },
    429: {
        "causes": ["Rate limited by SDP On-Demand"],
        "try": ["Wait 60s and retry; SDP throttles bursts"],
    },
}


CONFLUENCE_COMMON_CAUSES: dict = {
    400: {
        "causes": [
            "Storage-format XHTML is malformed (unclosed tag, bad entity)",
            "Page version conflict — page was edited since last fetch",
        ],
        "try": [
            "python3 scripts/confluence_get_page.py --id <ID>  # refetch current version",
            "Validate XHTML body offline before posting",
        ],
    },
    401: {
        "causes": [
            "WWEEKS_CONFLUENCE_API_TOKEN expired or revoked",
            "CONFLUENCE_EMAIL does not match the token owner",
        ],
        "try": [
            "Regenerate token: https://id.atlassian.com/manage-profile/security/api-tokens",
            "grep CONFLUENCE_ .env",
        ],
    },
    403: {
        "causes": [
            "Account lacks space permission to edit this page",
            "Page is restricted to a different group",
        ],
        "try": [
            "Check page restrictions in Confluence UI → ⋯ → Restrictions",
            "Verify space membership",
        ],
    },
    404: {
        "causes": [
            "Page ID is wrong",
            "Page was deleted or moved to another space",
            "Account does not have view permission so page appears missing",
        ],
        "try": [
            "Search by title: curl -u ... 'https://<YOUR_ATLASSIAN>.atlassian.net/wiki/rest/api/content?title=<TITLE>'",
            "Check page in browser: https://<YOUR_ATLASSIAN>.atlassian.net/wiki/pages/viewpage.action?pageId=<ID>",
        ],
    },
    409: {
        "causes": ["Version conflict — someone else edited the page"],
        "try": [
            "Refetch page (gets new version number), then retry update",
        ],
    },
}


GRAPH_COMMON_CAUSES: dict = {
    400: {
        "causes": [
            "Malformed filter/select query string",
            "Property name does not exist on resource",
        ],
        "try": [
            "Test query in Graph Explorer: https://developer.microsoft.com/graph/graph-explorer",
        ],
    },
    401: {
        "causes": [
            "Access token expired (1h lifetime)",
            "Token acquired for wrong audience",
        ],
        "try": [
            "az account get-access-token --resource https://graph.microsoft.com",
            "Verify tenant: az account show --query tenantId",
        ],
    },
    403: {
        "causes": [
            "App registration missing required Graph permission",
            "Admin consent not granted",
            "Conditional Access blocking the principal",
        ],
        "try": [
            "Check permissions in Entra → App registrations → API permissions",
            "Verify CA policies don't block service principals from this IP",
        ],
    },
    404: {
        "causes": [
            "User/group/object does not exist or was deleted",
            "Wrong tenant context",
        ],
        "try": [
            "az ad user show --id <UPN>",
            "az account show --query tenantId",
        ],
    },
}


AZURE_COMMON_CAUSES: dict = {
    # Used for az CLI exit codes and ARM REST failures
    "AuthorizationFailed": {
        "causes": [
            "Principal lacks RBAC role on target scope",
            "PIM-eligible role not yet activated",
            "Wrong subscription context",
        ],
        "try": [
            "az account show  # check current subscription",
            "az role assignment list --assignee <upn-or-objectId> --scope <scope>",
            "Activate PIM: https://portal.azure.com → PIM → My roles",
        ],
    },
    "ResourceNotFound": {
        "causes": [
            "Resource was deleted or moved",
            "Wrong subscription/resource-group context",
            "Resource name typo",
        ],
        "try": [
            "az graph query -q \"Resources | where name =~ '<name>'\"",
            "az account list-locations  # confirm region",
        ],
    },
    "SubscriptionNotFound": {
        "causes": [
            "Subscription ID typo",
            "Account does not have access to subscription",
            "Logged into wrong tenant",
        ],
        "try": [
            "az account list -o table",
            "az login --tenant <AZURE_TENANT_ID>",
        ],
    },
    "InvalidAuthenticationToken": {
        "causes": [
            "Token expired",
            "Not logged in",
        ],
        "try": [
            "az login",
            "az account get-access-token  # verify token works",
        ],
    },
}


FABRIC_COMMON_CAUSES: dict = {
    401: {
        "causes": [
            "Managed identity lost the Fabric workspace role",
            "Access token cached past expiry",
        ],
        "try": [
            "Verify workspace role assignment in Fabric admin portal",
            "Restart Function App to clear token cache",
        ],
    },
    403: {
        "causes": [
            "Identity has Viewer role but operation requires Contributor+",
            "Capacity is paused",
        ],
        "try": [
            "Check workspace roles in Fabric → Workspace settings → Manage access",
            "Check capacity state in Fabric admin portal",
        ],
    },
    404: {
        "causes": [
            "Workspace/item ID does not exist",
            "Item was deleted",
            "Wrong workspace ID",
        ],
        "try": [
            "List workspaces: GET https://api.fabric.microsoft.com/v1/workspaces",
        ],
    },
    429: {
        "causes": ["Fabric API throttling (capacity load too high)"],
        "try": [
            "Wait and retry with backoff",
            "Check capacity metrics in Fabric admin portal",
        ],
    },
}
