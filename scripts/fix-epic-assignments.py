#!/usr/bin/env python3
"""
fix-epic-assignments.py — Apply epic assignment corrections from the audit table.

Reads DECISIONS from the embedded dict below (populated after <APPROVER_NAME> reviews
the Confluence page at https://<YOUR_ATLASSIAN>.atlassian.net/wiki/spaces/<SPACE>/pages/<PAGE_ID>).

Usage:
    python3 scripts/fix-epic-assignments.py --dry-run   # Preview changes
    python3 scripts/fix-epic-assignments.py --apply     # Apply via Jira API
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import require_env

BASE_URL = "https://<YOUR_ATLASSIAN>.atlassian.net"

# Confirmed epic assignments from the audit review.
# Key = Jira issue to update, Value = Epic key to assign (or "SKIP" to leave unchanged, "CLOSE" to close)
# Populated from orphan suggestions; update after <APPROVER_NAME> reviews the Confluence page.
DECISIONS = {
    # --- Orphans (no epic) ---
    "<PROJECT>-25":  "<PROJECT>-16",   # Fabric - Retention → Fabric CI-CD
    "<PROJECT>-64":  "<PROJECT>-84",   # Linux OS Patching → Landing Zone
    "<PROJECT>-78":  "<PROJECT>-84",   # Veeam-01 Secure boot → Landing Zone
    "<PROJECT>-97":  "<PROJECT>-208",  # Servers - App/Browser control → Defender for Cloud
    "<PROJECT>-100": "<PROJECT>-60",   # Red Canary IdP SAML → Alert Source
    "<PROJECT>-153": "<PROJECT>-84",   # vm-prd-dsvm → Landing Zone
    "<PROJECT>-213": "<PROJECT>-207",  # JAMF PS → Intune
    "<PROJECT>-226": "<PROJECT>-207",  # Azure/M365 group licensing → Intune
    "<PROJECT>-227": "<PROJECT>-84",   # DCGC Reverse DNS → Landing Zone
    "<PROJECT>-233": "<PROJECT>-84",   # DCGC Virtual DC → Landing Zone
    "<PROJECT>-236": "<PROJECT>-208",  # Defender for Endpoint Detection → Defender for Cloud
    "<PROJECT>-239": "<PROJECT>-84",   # AZ-IPAM Training → Landing Zone
    "<PROJECT>-240": "<PROJECT>-60",   # Dark Trace DNS → Alert Source
    "<PROJECT>-248": "<PROJECT>-208",  # Defender EDR Policies → Defender for Cloud
    "<PROJECT>-254": "<PROJECT>-12",   # Defi Cleanup → SQL02 Migration
    "<PROJECT>-255": "<PROJECT>-12",   # Defi Blob Storage → SQL02 Migration
    "<PROJECT>-272": "<PROJECT>-164",  # SSO Loan Manager → Entra ID Suite
    "<PROJECT>-273": "<PROJECT>-84",   # SSL Gateways → Landing Zone
    "<PROJECT>-298": "<PROJECT>-207",  # M365 Admin Center → Intune
    "<PROJECT>-300": "<PROJECT>-84",   # SFTP Server Almalinux → Landing Zone
    "<PROJECT>-350": "<PROJECT>-145",  # JIRA Service Manager → JIRA Integrations
    "<PROJECT>-372": "<PROJECT>-164",  # Entra SAML Testing → Entra ID Suite
    "<PROJECT>-400": "<PROJECT>-16",   # Dev Codespaces → Fabric CI-CD
    "<PROJECT>-403": "<PROJECT>-182",  # Tenable OT Exposure → Pen Testing
    "<PROJECT>-404": "<PROJECT>-205",  # ISE BCP/HA → ISE Epic
    "<PROJECT>-405": "<PROJECT>-208",  # Defender AV/Admin → Defender for Cloud
    "<PROJECT>-407": "<PROJECT>-60",   # Checkmk → Alert Source
    "<PROJECT>-408": "<PROJECT>-207",  # Autopilot Dynamic Groups → Intune
    "<PROJECT>-409": "SKIP",       # TEST - Approver — close manually
    "<PROJECT>-459": "<PROJECT>-16",   # CI/CD Dave Farley → Fabric CI-CD

    # --- Potential mismatches (update after <APPROVER_NAME> confirms) ---
    # Uncomment and set to confirmed epic key after review:
    # "<PROJECT>-42":  "<PROJECT>-16",   # Fabric Event Logging — currently EDM-3536 (cross-project!)
    # "<PROJECT>-63":  "<PROJECT>-145",  # JIRA New Workspace — currently <PROJECT>-146
    # "<PROJECT>-88":  "<PROJECT>-84",   # SQL02 DNS zone — currently <PROJECT>-86
    # "<PROJECT>-103": "<PROJECT>-16",   # Fabric Sandbox Monitoring — currently <PROJECT>-12
    # "<PROJECT>-225": "<PROJECT>-182",  # Tenable ASM — currently <PROJECT>-154
    # "<PROJECT>-234": "<PROJECT>-207",  # Cresta via Intune — currently <PROJECT>-158
    # "<PROJECT>-235": "<PROJECT>-144",  # CI-CD Web 2.0 AKS — currently <PROJECT>-16
    # "<PROJECT>-237": "<PROJECT>-148",  # SASE VPN replacement — currently <PROJECT>-164
    # "<PROJECT>-241": "<PROJECT>-84",   # Jenkins Almalinux → Landing Zone
    # "<PROJECT>-242": "<PROJECT>-182",  # Tenable Web Scanning — currently <PROJECT>-169
    # "<PROJECT>-244": "<PROJECT>-182",  # CNAPP Tenable — currently <PROJECT>-16
    # "<PROJECT>-250": "<PROJECT>-207",  # JML Group licensing — currently <PROJECT>-178
    # "<PROJECT>-252": "<PROJECT>-208",  # Defender AV — currently <PROJECT>-182
    # "<PROJECT>-257": "<PROJECT>-182",  # Tenable CNAPP CIEM — currently <PROJECT>-188
}


def curl(method, path, body=None):
    require_env(
        "CONFLUENCE_EMAIL", "WWEEKS_CONFLUENCE_API_TOKEN",
        hint="Add them to .env at the repo root",
        env_file=str(Path(__file__).parent.parent / ".env"),
    )
    auth = os.environ["CONFLUENCE_EMAIL"] + ":" + os.environ["WWEEKS_CONFLUENCE_API_TOKEN"]
    cmd = ["curl", "-s", "-u", auth, "-H", "Content-Type: application/json",
           "-X", method, f"{BASE_URL}{path}"]
    if body:
        cmd += ["-d", json.dumps(body)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout


def get_issue(key):
    raw = curl("GET", f"/rest/api/3/issue/{key}?fields=summary,parent,status")
    return json.loads(raw)


def set_parent(key, epic_key, dry_run=True):
    if dry_run:
        print(f"  [DRY-RUN] SET {key} parent → {epic_key}")
        return True
    body = {"fields": {"parent": {"key": epic_key}}}
    raw = curl("PUT", f"/rest/api/3/issue/{key}", body)
    if raw.strip() in ("", "null"):
        print(f"  ✅ {key} → {epic_key}")
        return True
    else:
        data = json.loads(raw)
        if "errors" in data or "errorMessages" in data:
            print(f"  ❌ {key}: {data}")
            return False
        print(f"  ✅ {key} → {epic_key}")
        return True


def main():
    parser = argparse.ArgumentParser(description="Apply epic assignment corrections to Jira.")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Preview changes without applying (default)")
    parser.add_argument("--apply", action="store_true",
                        help="Apply changes to Jira")
    args = parser.parse_args()

    dry_run = not args.apply

    if dry_run:
        print("🔍 DRY RUN — no changes will be made. Pass --apply to execute.\n")
    else:
        print("🚀 APPLYING epic assignments to Jira...\n")

    success, skipped, failed = 0, 0, 0

    for issue_key, epic_key in DECISIONS.items():
        if epic_key == "SKIP":
            print(f"  ⏭  {issue_key} — SKIP")
            skipped += 1
            continue

        if not dry_run:
            issue = get_issue(issue_key)
            current_parent = (issue.get("fields", {}).get("parent") or {}).get("key")
            if current_parent == epic_key:
                print(f"  ✓  {issue_key} — already set to {epic_key}")
                skipped += 1
                continue

        ok = set_parent(issue_key, epic_key, dry_run=dry_run)
        if ok:
            success += 1
        else:
            failed += 1

    print(f"\n{'Preview' if dry_run else 'Done'}: {success} changes, {skipped} skipped, {failed} failed")
    if dry_run:
        print("Run with --apply to execute.")


if __name__ == "__main__":
    main()
