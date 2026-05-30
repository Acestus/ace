#!/usr/bin/env python3
"""
azure_rg_inventory.py — Daily Azure Resource Group inventory diff and Confluence updater.

Queries all resource groups across all <ORG_NAME>-tenant subscriptions, diffs against the
last committed snapshot, and publishes a drift log to the Azure Subscription and Resource
Group Registry Confluence page (page ID <PAGE_ID>) if anything changed.

Usage:
    python3 scripts/azure_rg_inventory.py [--dry-run] [--force]

    --dry-run    Print diff only; do not update snapshot or publish to Confluence
    --force      Publish to Confluence even if no changes detected (useful for initial run)

Authentication:
    Uses the current `az` CLI session. In GitHub Actions, wire up OIDC via `azure/login`
    before running this script. No stored credentials required.

Environment:
    CONFLUENCE_EMAIL and WWEEKS_CONFLUENCE_API_TOKEN must be set (loaded from .env locally).
"""

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, require_tool, CONFLUENCE_COMMON_CAUSES

# ── Constants ──────────────────────────────────────────────────────────────────

<ORG_SHORT>_TENANT_ID = "<AZURE_TENANT_ID>"
CONFLUENCE_PAGE_ID = "<PAGE_ID>"

REPO_ROOT = Path(__file__).parent.parent
SNAPSHOT_PATH = REPO_ROOT / "assets" / "<PAGE_ID>" / "rg-snapshot.json"
CONFLUENCE_MD = REPO_ROOT / "confluence" / "<PAGE_ID>-Azure-Subscription-and-Resource-Group-Registry.md"
PUBLISH_SCRIPT = REPO_ROOT / "scripts" / "publish-markdown-to-confluence.py"

# RG name prefixes/exact names that are auto-provisioned by Azure services.
# Changes to these are not meaningful — skip them in the diff.
AUTO_PROVISIONED_PREFIXES = (
    "NetworkWatcherRG",
    "Built-In-Identity-RG",
    "DefaultResourceGroup-",
    "MC_",
    "MA_",
    "AzureBackupRG_",
    "ResourceMoverRG-",
    "ZonalMove-",
    "cloud-shell-storage-",
    "LogAnalyticsDefaultResources",
    "darktrace-network-flow-analysis-",
    "RCAutomation",
    "<ORG_NAME>-asc-export",
    "dfc-automatedfc-",
    "azureapp-auto-alerts-",
)


# ── Azure queries ──────────────────────────────────────────────────────────────

def get_subscriptions() -> list[dict]:
    """Return all enabled subscriptions in the <ORG_NAME> tenant."""
    result = subprocess.check_output(
        ["az", "account", "list", "--output", "json"],
        stderr=subprocess.DEVNULL,
    )
    all_subs = json.loads(result)
    return [
        s for s in all_subs
        if s["tenantId"] == <ORG_SHORT>_TENANT_ID and s["state"] == "Enabled"
    ]


def get_resource_groups(subscription_id: str, subscription_name: str) -> list[dict]:
    """Return all resource groups in a subscription as inventory records."""
    result = subprocess.check_output(
        ["az", "group", "list", "--subscription", subscription_id, "--output", "json"],
        stderr=subprocess.DEVNULL,
    )
    groups = json.loads(result)
    return [
        {
            "key": f"{subscription_id}/{rg['name']}",
            "subscription_id": subscription_id,
            "subscription_name": subscription_name,
            "name": rg["name"],
            "location": rg.get("location", ""),
        }
        for rg in groups
    ]


def is_auto_provisioned(rg_name: str) -> bool:
    """Return True if this RG is a known auto-provisioned artifact."""
    return any(rg_name.startswith(prefix) for prefix in AUTO_PROVISIONED_PREFIXES)


def fetch_estate() -> dict[str, dict]:
    """Fetch all non-auto-provisioned RGs across all <ORG_NAME> subscriptions.

    Returns a dict keyed by '{subscription_id}/{rg_name}' for fast lookup.
    """
    print("🔍 Fetching subscriptions...")
    subscriptions = get_subscriptions()
    print(f"   Found {len(subscriptions)} subscriptions in <ORG_NAME> tenant")

    estate: dict[str, dict] = {}
    for sub in subscriptions:
        groups = get_resource_groups(sub["id"], sub["name"])
        meaningful = [g for g in groups if not is_auto_provisioned(g["name"])]
        estate.update({g["key"]: g for g in meaningful})
        print(f"   {sub['name']}: {len(meaningful)} RGs (of {len(groups)} total)")

    print(f"✅ Estate fetched: {len(estate)} resource groups across {len(subscriptions)} subscriptions")
    return estate


# ── Snapshot I/O ───────────────────────────────────────────────────────────────

def load_snapshot() -> dict[str, dict]:
    """Load the last committed RG snapshot. Returns empty dict if none exists."""
    if not SNAPSHOT_PATH.exists():
        print("⚠️  No snapshot found — this will be the first run")
        return {}
    data = json.loads(SNAPSHOT_PATH.read_text())
    return {item["key"]: item for item in data}


def save_snapshot(estate: dict[str, dict]) -> None:
    """Write the current estate to the snapshot file."""
    SNAPSHOT_PATH.write_text(
        json.dumps(sorted(estate.values(), key=lambda r: r["key"]), indent=2)
    )
    print(f"💾 Snapshot saved: {SNAPSHOT_PATH}")


# ── Diff logic ─────────────────────────────────────────────────────────────────

def diff_snapshots(
    old: dict[str, dict],
    new: dict[str, dict],
) -> tuple[list[dict], list[dict]]:
    """Return (added, removed) lists of RG records."""
    added = [new[k] for k in new if k not in old]
    removed = [old[k] for k in old if k not in new]
    return added, removed


# ── Confluence update ──────────────────────────────────────────────────────────

def build_drift_entry(added: list[dict], removed: list[dict]) -> str:
    """Build a single dated drift log entry in markdown."""
    today = date.today().isoformat()
    lines = [f"### {today}\n"]

    if added:
        lines.append("**Added:**\n")
        for rg in sorted(added, key=lambda r: (r["subscription_name"], r["name"])):
            lines.append(
                f"- `{rg['subscription_name']}` / `{rg['name']}` [{rg['location']}] — ❓ Unclassified\n"
            )

    if removed:
        if added:
            lines.append("\n")
        lines.append("**Removed:**\n")
        for rg in sorted(removed, key=lambda r: (r["subscription_name"], r["name"])):
            lines.append(
                f"- `{rg['subscription_name']}` / `{rg['name']}` — no longer present in estate\n"
            )

    return "".join(lines)


DRIFT_LOG_HEADING = "## Drift Log"
DRIFT_LOG_INTRO = (
    "\n\nChanges detected automatically by `azure_rg_inventory.py`. "
    "When new RGs appear here, add them to the correct subscription section with a business context description.\n\n"
)


def inject_drift_entry(md_path: Path, added: list[dict], removed: list[dict]) -> None:
    """Insert a new drift log entry into the Confluence markdown file.

    Creates the '## Drift Log' section if it doesn't exist yet.
    New entries go at the top of the section (reverse chronological).
    """
    content = md_path.read_text()
    entry = build_drift_entry(added, removed)

    if DRIFT_LOG_HEADING in content:
        # Insert new entry just after the section heading + intro paragraph
        insert_after = content.index(DRIFT_LOG_HEADING) + len(DRIFT_LOG_HEADING)
        # Skip over the intro paragraph to find where entries begin
        after_heading = content[insert_after:]
        # Find the first '### ' date entry or end of intro
        import re
        match = re.search(r"\n### \d{4}-\d{2}-\d{2}", after_heading)
        if match:
            pos = insert_after + match.start() + 1  # +1 to keep the leading \n
            content = content[:pos] + entry + "\n" + content[pos:]
        else:
            content = content + "\n" + entry
    else:
        # Append new Drift Log section before Related Pages, or at end
        related_heading = "## Related Pages"
        if related_heading in content:
            pos = content.index(related_heading)
            content = content[:pos] + DRIFT_LOG_HEADING + DRIFT_LOG_INTRO + entry + "\n---\n\n" + content[pos:]
        else:
            content = content + "\n\n" + DRIFT_LOG_HEADING + DRIFT_LOG_INTRO + entry

    md_path.write_text(content)
    print(f"📝 Drift log updated in {md_path.name}")


def publish_to_confluence(dry_run: bool) -> None:
    """Run the publish script to push the updated markdown to Confluence."""
    if dry_run:
        print("🚫 [dry-run] Skipping Confluence publish")
        return

    print(f"🚀 Publishing page {CONFLUENCE_PAGE_ID} to Confluence...")
    result = subprocess.run(
        ["python3", str(PUBLISH_SCRIPT), CONFLUENCE_PAGE_ID, str(CONFLUENCE_MD)],
        capture_output=False,
    )
    if result.returncode != 0:
        fail(
            "Confluence publish step failed",
            causes=[
                "publish-markdown-to-confluence.py exited non-zero",
                "Missing CONFLUENCE_EMAIL or WWEEKS_CONFLUENCE_API_TOKEN in .env",
                "Confluence page ID is incorrect or you lack edit permission",
            ],
            try_=[
                f"Run manually: python3 {PUBLISH_SCRIPT} {CONFLUENCE_PAGE_ID} {CONFLUENCE_MD}",
                "Check that .env contains CONFLUENCE_EMAIL and WWEEKS_CONFLUENCE_API_TOKEN",
            ],
        )


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Print diff only; do not update files or publish")
    parser.add_argument("--force", action="store_true", help="Publish even if no changes detected")
    args = parser.parse_args()

    # 1. Fetch live estate
    estate = fetch_estate()

    # 2. Load snapshot and diff
    snapshot = load_snapshot()
    added, removed = diff_snapshots(snapshot, estate)

    print(f"\n📊 Diff result: {len(added)} added, {len(removed)} removed")

    if added:
        print("\n  ➕ Added:")
        for rg in sorted(added, key=lambda r: (r["subscription_name"], r["name"])):
            print(f"     {rg['subscription_name']} / {rg['name']} [{rg['location']}]")

    if removed:
        print("\n  ➖ Removed:")
        for rg in sorted(removed, key=lambda r: (r["subscription_name"], r["name"])):
            print(f"     {rg['subscription_name']} / {rg['name']}")

    # 3. Exit early if nothing changed (unless --force)
    if not added and not removed:
        print("\n✅ No changes detected — estate matches snapshot")
        if not args.force:
            return
        print("   --force specified; publishing anyway")

    # 4. Update snapshot
    if not args.dry_run:
        save_snapshot(estate)

    # 5. Inject drift log entry and publish
    if added or removed:
        inject_drift_entry(CONFLUENCE_MD, added, removed)
        publish_to_confluence(args.dry_run)
    elif args.force:
        publish_to_confluence(args.dry_run)

    print("\n✅ Done")


if __name__ == "__main__":
    main()
