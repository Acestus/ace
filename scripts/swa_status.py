#!/usr/bin/env python3
"""
swa_status.py — Quick status check for an Azure Static Web App + GitHub Actions.

Usage:
    python3 scripts/swa_status.py --config ace/.azure/appsettings.json
    python3 scripts/swa_status.py --swa swa-fabricweb-prd-cus-001 --rg rg-fabricweb-prd --repo Acestus/fabricweb
    python3 scripts/swa_status.py --config ace/.azure/appsettings.json --open

Flags:
    --config FILE          Path to appsettings.json (auto-reads swa, rg, repo, domain)
    --swa NAME             SWA resource name
    --rg NAME              Resource group name
    --repo OWNER/REPO      GitHub repo
    --domain DOMAIN        Custom domain (optional)
    --open                 Open the site in browser after check

Examples:
    # Full status from config file
    python3 scripts/swa_status.py --config ~/github/ace/.azure/appsettings.json --repo Acestus/fabricweb

    # Quick inline
    python3 scripts/swa_status.py \
        --swa swa-fabricweb-prd-cus-001 \
        --rg rg-fabricweb-prd \
        --repo Acestus/fabricweb \
        --domain fabric.acestus.com
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], check=False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def print_section(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print('─' * 60)


def load_config(config_path: str) -> dict:
    path = Path(config_path).expanduser()
    if not path.exists():
        print(f"  ❌ Config not found: {config_path}")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def check_github_actions(repo: str):
    print_section(f"GitHub Actions — {repo}")
    result = run(["gh", "run", "list", "--repo", repo, "--limit", "5",
                  "--json", "databaseId,status,conclusion,displayTitle,createdAt"])
    if result.returncode != 0:
        print(f"  ❌ gh CLI error: {result.stderr.strip()}")
        return

    runs = json.loads(result.stdout)
    if not runs:
        print("  ℹ  No runs found")
        return

    for r in runs:
        status = r.get("conclusion") or r.get("status") or "?"
        icon = {"success": "✅", "failure": "❌", "cancelled": "⛔", "in_progress": "⏳"}.get(status, "·")
        title = r.get("displayTitle", "")[:55]
        print(f"  {icon} {r['databaseId']}  {status:<12}  {title}")

    # Show log-failed output for the latest failed run
    latest = runs[0]
    if latest.get("conclusion") == "failure":
        print(f"\n  Latest failure logs (run {latest['databaseId']}):")
        subprocess.run(
            ["gh", "run", "view", str(latest["databaseId"]), "--repo", repo, "--log-failed"],
            check=False,
        )


def check_azure_swa(swa_name: str, resource_group: str, domain: str | None = None):
    print_section(f"Azure SWA — {swa_name}")
    result = run([
        "az", "staticwebapp", "show",
        "--name", swa_name,
        "--resource-group", resource_group,
        "--query", "{hostname:defaultHostname,sku:sku.name,branch:branch}",
        "--output", "json",
    ])
    if result.returncode != 0:
        print(f"  ❌ Azure CLI error (not logged in or resource doesn't exist yet)")
        print(f"     {result.stderr.strip()[:200]}")
        return None

    data = json.loads(result.stdout)
    hostname = data.get("hostname", "")
    print(f"  🌐 Hostname  : {hostname}")
    print(f"  📦 SKU       : {data.get('sku', 'unknown')}")
    print(f"  🔗 SWA URL   : https://{hostname}")
    if domain:
        print(f"  🌍 Domain    : https://{domain}")
        # Check if CNAME is set (basic DNS check)
        dns = run(["dig", "+short", "CNAME", domain])
        cname_val = dns.stdout.strip()
        if cname_val:
            status = "✅ CNAME set" if hostname in cname_val else f"⚠  CNAME → {cname_val} (expected {hostname})"
        else:
            status = "⏳ No CNAME yet — add at hover.com"
        print(f"  📡 DNS       : {status}")

    return hostname


def check_umi(umi_name: str, identity_rg: str):
    print_section(f"UMI — {umi_name}")
    result = run([
        "az", "identity", "show",
        "--name", umi_name,
        "--resource-group", identity_rg,
        "--query", "{clientId:clientId,principalId:principalId}",
        "--output", "json",
    ])
    if result.returncode != 0:
        print(f"  ❌ UMI not found or not logged in")
        return

    data = json.loads(result.stdout)
    print(f"  🔑 Client ID    : {data.get('clientId')}")
    print(f"  👤 Principal ID : {data.get('principalId')}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", help="Path to appsettings.json")
    parser.add_argument("--swa", help="SWA resource name")
    parser.add_argument("--rg", help="Workload resource group")
    parser.add_argument("--repo", help="GitHub owner/repo")
    parser.add_argument("--domain", help="Custom domain")
    parser.add_argument("--umi", help="UMI name")
    parser.add_argument("--id-rg", help="Identity resource group")
    parser.add_argument("--open", action="store_true", help="Open site in browser")
    args = parser.parse_args()

    swa_name = args.swa
    rg = args.rg
    repo = args.repo
    domain = args.domain
    umi_name = args.umi
    id_rg = args.id_rg

    if args.config:
        cfg = load_config(args.config)
        azure = cfg.get("azure", {})
        site = cfg.get("site", {})
        github = cfg.get("github", {})
        swa_name = swa_name or site.get("swaName")
        rg = rg or azure.get("workloadResourceGroup")
        repo = repo or github.get("repo")
        domain = domain or site.get("domain")
        umi_name = umi_name or azure.get("umiName")
        id_rg = id_rg or azure.get("identityResourceGroup")

    if not any([swa_name, repo]):
        parser.print_help()
        sys.exit(1)

    print(f"\n{'═' * 60}")
    print(f"  SWA Status Check")
    print(f"  {domain or swa_name}")
    print(f"{'═' * 60}")

    hostname = None
    if swa_name and rg:
        hostname = check_azure_swa(swa_name, rg, domain)

    if umi_name and id_rg:
        check_umi(umi_name, id_rg)

    if repo:
        check_github_actions(repo)

    if args.open and hostname:
        url = f"https://{domain or hostname}"
        print(f"\n  🚀 Opening {url}")
        subprocess.run(["xdg-open", url], check=False)


if __name__ == "__main__":
    main()
