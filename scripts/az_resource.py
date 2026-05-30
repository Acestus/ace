#!/usr/bin/env python3
"""
az_resource.py — Azure resource lookup and role assignment helper.

Usage:
    python3 scripts/az_resource.py --show RESOURCE_NAME_OR_ID [--rg RESOURCE_GROUP]
    python3 scripts/az_resource.py --roles SCOPE [--user EMAIL]
    python3 scripts/az_resource.py --list-umi [--rg RESOURCE_GROUP] [--filter PATTERN]
    python3 scripts/az_resource.py --find PATTERN [--rg RESOURCE_GROUP] [--type RESOURCE_TYPE]
    python3 scripts/az_resource.py --tags RESOURCE_ID_OR_NAME [--rg RESOURCE_GROUP]
    python3 scripts/az_resource.py --whoami

Flags:
    --show NAME_OR_ID      Show a resource by name or full resource ID.
    --roles SCOPE          List role assignments for a scope.
    --user EMAIL           Filter role assignments to a specific user.
    --list-umi             List user-assigned managed identities.
    --filter PATTERN       Filter managed identities by name pattern.
    --find PATTERN         Find resources by name pattern.
    --type RESOURCE_TYPE   Filter resources by Azure resource type.
    --tags NAME_OR_ID      Show resource tags.
    --rg RESOURCE_GROUP    Resource group filter.
    --whoami               Show current Azure account context.

Environment:
    AZURE_SUBSCRIPTION_ID  — target subscription (optional; uses current az context if not set)
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, AZURE_COMMON_CAUSES


def load_env_file():
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())



def with_subscription(command):
    subscription = os.environ.get("AZURE_SUBSCRIPTION_ID", "").strip()
    if subscription:
        return command + ["--subscription", subscription]
    return command



def run_az_json(command):
    full_command = with_subscription(command + ["-o", "json"])
    try:
        result = subprocess.run(full_command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise RuntimeError("az CLI is not installed")
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(detail or "az command failed")
    try:
        return json.loads(result.stdout or "null")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse az output: {exc}")



def extract_resource_group(resource):
    if resource.get("resourceGroup"):
        return resource["resourceGroup"]
    resource_id = resource.get("id", "")
    parts = resource_id.split("/")
    if "resourceGroups" in parts:
        index = parts.index("resourceGroups")
        if index + 1 < len(parts):
            return parts[index + 1]
    return "—"



def truncate(text, limit):
    text = str(text or "—")
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"



def print_table(headers, rows):
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))



def get_resource(name_or_id, resource_group):
    if name_or_id.startswith("/subscriptions/"):
        return run_az_json(["az", "resource", "show", "--ids", name_or_id])
    command = ["az", "resource", "list", "--name", name_or_id, "--query", "[0]"]
    if resource_group:
        command.extend(["--resource-group", resource_group])
    resource = run_az_json(command)
    if not resource:
        raise RuntimeError(f"Resource not found: {name_or_id}")
    return resource



def show_resource(name_or_id, resource_group):
    resource = get_resource(name_or_id, resource_group)
    state = ((resource.get("properties") or {}).get("provisioningState") or "—")
    tags = resource.get("tags") or {}
    print(f"Name              : {resource.get('name', '—')}")
    print(f"Type              : {resource.get('type', '—')}")
    print(f"Location          : {resource.get('location', '—')}")
    print(f"Resource group    : {extract_resource_group(resource)}")
    print(f"ID                : {resource.get('id', '—')}")
    print(f"Provisioning state: {state}")
    print("Tags              :")
    if tags:
        for key in sorted(tags):
            print(f"  {key}: {tags[key]}")
    else:
        print("  —")
    print("✓ Resource loaded")
    return 0



def list_roles(scope, user_filter):
    assignments = run_az_json([
        "az", "role", "assignment", "list", "--scope", scope, "--include-inherited",
        "--query", "[].{principal:principalName,role:roleDefinitionName,type:principalType}",
    ])
    rows = []
    for item in assignments:
        principal = str(item.get("principal") or "—")
        if user_filter and principal.lower() != user_filter.lower():
            continue
        rows.append([
            truncate(principal, 40),
            truncate(item.get("type") or "—", 20),
            truncate(item.get("role") or "—", 40),
        ])
    if not rows:
        print("⚠ No matching role assignments found")
        return 0
    print_table(["PRINCIPAL", "TYPE", "ROLE"], rows)
    print(f"✓ Listed {len(rows)} role assignment(s)")
    return 0



def list_umi(resource_group, name_filter):
    command = ["az", "identity", "list"]
    if resource_group:
        command.extend(["--resource-group", resource_group])
    identities = run_az_json(command)
    rows = []
    pattern = (name_filter or "").lower()
    for identity in identities:
        name = identity.get("name", "")
        if pattern and pattern not in name.lower():
            continue
        rows.append([
            truncate(name or "—", 36),
            truncate(extract_resource_group(identity), 28),
            truncate(identity.get("clientId") or "—", 36),
            truncate(identity.get("principalId") or "—", 36),
        ])
    if not rows:
        print("⚠ No managed identities found")
        return 0
    print_table(["NAME", "RESOURCE GROUP", "CLIENT ID", "PRINCIPAL ID"], rows)
    print(f"✓ Listed {len(rows)} managed identit(ies)")
    return 0



def find_resources(pattern, resource_group, resource_type):
    command = ["az", "resource", "list"]
    if resource_group:
        command.extend(["--resource-group", resource_group])
    if resource_type:
        command.extend(["--resource-type", resource_type])
    resources = run_az_json(command)
    rows = []
    search = pattern.lower()
    for resource in resources:
        name = str(resource.get("name") or "")
        if search not in name.lower():
            continue
        rows.append([
            truncate(name or "—", 36),
            truncate(resource.get("type") or "—", 45),
            truncate(extract_resource_group(resource), 28),
            truncate(resource.get("location") or "—", 20),
        ])
    if not rows:
        print("⚠ No matching resources found")
        return 0
    print_table(["NAME", "TYPE", "RESOURCE GROUP", "LOCATION"], rows)
    print(f"✓ Found {len(rows)} matching resource(s)")
    return 0



def show_tags(name_or_id, resource_group):
    resource = get_resource(name_or_id, resource_group)
    tags = resource.get("tags") or {}
    if not tags:
        print("⚠ Resource has no tags")
        return 0
    print(f"Tags for {resource.get('name', name_or_id)}:")
    for key in sorted(tags):
        print(f"  {key}: {tags[key]}")
    print("✓ Tags loaded")
    return 0



def show_whoami():
    account = run_az_json(["az", "account", "show"])
    user = account.get("user") or {}
    print(f"Account name      : {account.get('name', '—')}")
    print(f"Subscription name : {account.get('name', '—')}")
    print(f"Tenant ID         : {account.get('tenantId', '—')}")
    print(f"User              : {user.get('name', '—')}")
    print("✓ Azure context loaded")
    return 0



def build_parser():
    parser = argparse.ArgumentParser(description="Azure resource lookup and role assignment helper")
    parser.add_argument("--rg", help="Azure resource group")
    parser.add_argument("--user", help="User principal name/email filter")
    parser.add_argument("--filter", help="Name filter for --list-umi")
    parser.add_argument("--type", help="Azure resource type filter for --find")
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument("--show", metavar="RESOURCE_NAME_OR_ID", help="Show a resource")
    action_group.add_argument("--roles", metavar="SCOPE", help="List role assignments")
    action_group.add_argument("--list-umi", action="store_true", help="List managed identities")
    action_group.add_argument("--find", metavar="PATTERN", help="Find resources by name pattern")
    action_group.add_argument("--tags", metavar="RESOURCE_ID_OR_NAME", help="Show resource tags")
    action_group.add_argument("--whoami", action="store_true", help="Show current Azure identity")
    return parser



def main():
    load_env_file()
    parser = build_parser()
    args = parser.parse_args()
    if len(sys.argv) == 1:
        parser.print_help()
        return 1
    try:
        if args.show:
            return show_resource(args.show, args.rg)
        if args.roles:
            return list_roles(args.roles, args.user)
        if args.list_umi:
            return list_umi(args.rg, args.filter)
        if args.find:
            return find_resources(args.find, args.rg, args.type)
        if args.tags:
            return show_tags(args.tags, args.rg)
        if args.whoami:
            return show_whoami()
        parser.print_help()
        return 1
    except Exception as exc:
        fail(str(exc), causes=AZURE_COMMON_CAUSES)


if __name__ == "__main__":
    sys.exit(main())
