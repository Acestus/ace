#!/usr/bin/env python3
"""
az_pim.py — Azure PIM eligible and active role assignment helper.

Usage:
    python3 scripts/az_pim.py --list-eligible [--scope SUBSCRIPTION_OR_RG]
    python3 scripts/az_pim.py --list-active [--scope SUBSCRIPTION_OR_RG]
    python3 scripts/az_pim.py --check --user OBJECT_ID_OR_UPN --role "Role Name" [--scope SCOPE]
    python3 scripts/az_pim.py --assignments --user OBJECT_ID_OR_UPN
    python3 scripts/az_pim.py --groups --user OBJECT_ID_OR_UPN

Environment:
    AZURE_SUBSCRIPTION_ID  — target subscription (uses current az context if not set)
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, warn, require_tool, AZURE_COMMON_CAUSES

ELIGIBLE_API = (
    "providers/Microsoft.Authorization/roleEligibilityScheduleInstances"
    "?api-version=2020-10-01&$filter=asTarget()"
)
ACTIVE_API = (
    "providers/Microsoft.Authorization/roleAssignmentScheduleInstances"
    "?api-version=2020-10-01&$filter=asTarget()"
)


def load_env_file():
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value



def success(message: str):
    print(f"✓ {message}")


def get_subscription():
    result = subprocess.run(
        ["az", "account", "show", "--query", "id", "-o", "tsv"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def run_az_command(command: list[str]):
    try:
        return subprocess.run(command, capture_output=True, text=True)
    except FileNotFoundError:
        require_tool("az", hint="https://docs.microsoft.com/en-us/cli/azure/install-azure-cli")


def handle_az_error(result, fallback: str):
    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    combined = f"{stderr}\n{stdout}".lower()
    if "az login" in combined:
        fail("Not logged in to Azure CLI",
             causes=["Session expired or no active az login"],
             try_=["az login", "az account show"])
    if "subscription" in combined and ("not found" in combined or "could not be found" in combined):
        fail("Azure subscription not found",
             causes=AZURE_COMMON_CAUSES.get(404, {}).get("causes", [
                 "AZURE_SUBSCRIPTION_ID is wrong or not set"]),
             try_=["az account list --output table",
                   "grep AZURE_SUBSCRIPTION_ID .env"])
    fail(
        f"{fallback}: {stderr or stdout or 'unknown error'}",
        causes=AZURE_COMMON_CAUSES.get(result.returncode, {}).get("causes", []),
        try_=AZURE_COMMON_CAUSES.get(result.returncode, {}).get("try", []),
    )


def resolve_scope(scope_value: str | None):
    if scope_value:
        if scope_value.startswith("/"):
            return scope_value.rstrip("/")
        if re.fullmatch(r"[0-9a-fA-F-]{36}", scope_value):
            return f"/subscriptions/{scope_value}"
        sub = os.environ.get("AZURE_SUBSCRIPTION_ID", "") or get_subscription()
        if not sub:
            fail("Cannot resolve subscription ID",
                 causes=["AZURE_SUBSCRIPTION_ID not set and az account show failed"],
                 try_=["az account set --subscription <ID>",
                       "grep AZURE_SUBSCRIPTION_ID .env"])
        return f"/subscriptions/{sub}/resourceGroups/{scope_value}"
    sub = os.environ.get("AZURE_SUBSCRIPTION_ID", "") or get_subscription()
    if not sub:
        fail("Cannot resolve subscription ID",
             causes=["AZURE_SUBSCRIPTION_ID not set and az account show failed"],
             try_=["az account set --subscription <ID>",
                   "grep AZURE_SUBSCRIPTION_ID .env"])
    return f"/subscriptions/{sub}"


def az_rest_get(url: str):
    result = run_az_command(["az", "rest", "--method", "GET", "--url", url])
    if result.returncode != 0:
        handle_az_error(result, f"az rest GET failed for {url}")
    try:
        return json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        fail("Invalid JSON response from Azure CLI",
             causes=["Azure CLI returned non-JSON output (try running the command manually)"],
             try_=[f"az rest --method GET --url '{url}'"])


def resolve_user(user_value: str):
    if "@" not in user_value:
        return user_value
    result = run_az_command(["az", "ad", "user", "show", "--id", user_value, "--query", "id", "-o", "tsv"])
    if result.returncode != 0 or not result.stdout.strip():
        handle_az_error(result, f"Could not resolve user {user_value}")
    return result.stdout.strip()


def get_items(scope: str, eligible: bool):
    endpoint = ELIGIBLE_API if eligible else ACTIVE_API
    url = f"https://management.azure.com/{scope.lstrip('/')}/{endpoint}"
    data = az_rest_get(url)
    return data.get("value", [])


def expanded(row: dict):
    properties = row.get("properties", {})
    return properties.get("expandedProperties", {}), properties


def get_role_name(row: dict):
    expanded_properties, _ = expanded(row)
    role = expanded_properties.get("roleDefinition", {})
    return role.get("displayName", "—")


def get_principal_name(row: dict):
    expanded_properties, _ = expanded(row)
    principal = expanded_properties.get("principal", {})
    return principal.get("displayName", "—")


def get_principal_type(row: dict):
    expanded_properties, _ = expanded(row)
    principal = expanded_properties.get("principal", {})
    return principal.get("type", "—")


def get_status(row: dict):
    return row.get("properties", {}).get("status", "—")


def get_expiry(row: dict):
    return row.get("properties", {}).get("endDateTime", "—") or "—"


def get_principal_id(row: dict):
    properties = row.get("properties", {})
    principal_id = properties.get("principalId", "")
    if principal_id:
        return principal_id.lower()
    expanded_properties, _ = expanded(row)
    principal = expanded_properties.get("principal", {})
    return str(principal.get("id", "")).lower()


def get_assignment_scope(row: dict):
    properties = row.get("properties", {})
    return properties.get("scope", row.get("id", "—"))


def print_table(headers: list[str], rows: list[list[str]]):
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    header_line = " | ".join(headers[index].ljust(widths[index]) for index in range(len(headers)))
    divider = "-+-".join("-" * widths[index] for index in range(len(headers)))
    print(header_line)
    print(divider)
    for row in rows:
        print(" | ".join(row[index].ljust(widths[index]) for index in range(len(headers))))


def print_role_rows(items: list[dict]):
    rows = []
    for item in items:
        rows.append([
            get_role_name(item),
            get_principal_name(item),
            get_principal_type(item),
            get_status(item),
            get_expiry(item),
        ])
    if not rows:
        warn("No assignments found")
        return
    print_table(["ROLE", "PRINCIPAL", "PRINCIPAL TYPE", "STATUS", "EXPIRY"], rows)


def filter_user_role(items: list[dict], principal_id: str, role_name: str):
    target_role = role_name.lower()
    matches = []
    for item in items:
        if get_principal_id(item) != principal_id.lower():
            continue
        if target_role not in get_role_name(item).lower():
            continue
        matches.append(item)
    return matches


def print_assignment_section(title: str, items: list[dict]):
    print(title)
    if not items:
        warn("No matching assignments")
        print()
        return
    rows = []
    for item in items:
        rows.append([
            get_role_name(item),
            get_assignment_scope(item),
            get_status(item),
            get_expiry(item),
        ])
    print_table(["ROLE", "SCOPE", "STATUS", "EXPIRY"], rows)
    print()


def list_eligible(scope: str):
    print_role_rows(get_items(scope, eligible=True))
    return 0


def list_active(scope: str):
    print_role_rows(get_items(scope, eligible=False))
    return 0


def check_role(scope: str, user_value: str, role_name: str):
    principal_id = resolve_user(user_value)
    eligible_matches = filter_user_role(get_items(scope, eligible=True), principal_id, role_name)
    active_matches = filter_user_role(get_items(scope, eligible=False), principal_id, role_name)
    eligible_expiry = ", ".join(get_expiry(item) for item in eligible_matches) or "—"
    active_expiry = ", ".join(get_expiry(item) for item in active_matches) or "—"
    print(f"USER: {user_value}")
    print(f"ROLE: {role_name}")
    print(f"SCOPE: {scope}")
    print(f"ELIGIBLE: {'yes' if eligible_matches else 'no'}")
    if eligible_matches:
        print(f"ELIGIBLE EXPIRY: {eligible_expiry}")
    print(f"ACTIVE: {'yes' if active_matches else 'no'}")
    if active_matches:
        print(f"ACTIVE EXPIRY: {active_expiry}")
    return 0


def list_assignments(user_value: str):
    scope = resolve_scope(None)
    principal_id = resolve_user(user_value)
    eligible_items = [item for item in get_items(scope, eligible=True) if get_principal_id(item) == principal_id.lower()]
    active_items = [item for item in get_items(scope, eligible=False) if get_principal_id(item) == principal_id.lower()]
    print_assignment_section("ELIGIBLE", eligible_items)
    print_assignment_section("ACTIVE", active_items)
    return 0


def fallback_group_names(user_value: str):
    result = run_az_command(["az", "ad", "user", "get-member-groups", "--id", user_value, "--security-enabled-only", "false", "-o", "json"])
    if result.returncode != 0:
        handle_az_error(result, f"Could not get groups for {user_value}")
    try:
        group_ids = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return []
    names = []
    for group_id in group_ids:
        show_result = run_az_command(["az", "ad", "group", "show", "--group", str(group_id), "--query", "displayName", "-o", "tsv"])
        if show_result.returncode == 0 and show_result.stdout.strip():
            names.append(show_result.stdout.strip())
    return names


def list_groups(user_value: str):
    result = run_az_command([
        "az", "ad", "user", "get-member-groups",
        "--id", user_value,
        "--security-enabled-only", "false",
        "--query", "[].displayName",
        "-o", "tsv",
    ])
    if result.returncode != 0:
        handle_az_error(result, f"Could not get groups for {user_value}")
    group_names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not group_names:
        group_names = fallback_group_names(user_value)
    pim_groups = [name for name in group_names if re.search(r"(pim|azpim)", name, re.IGNORECASE)]
    if not pim_groups:
        warn("No PIM-related groups found")
        return 0
    print("GROUP NAME")
    print("----------")
    for name in sorted(set(pim_groups), key=str.lower):
        print(name)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Azure PIM helper using az rest")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--list-eligible", action="store_true", help="List eligible role assignments")
    actions.add_argument("--list-active", action="store_true", help="List active role assignments")
    actions.add_argument("--check", action="store_true", help="Check whether a user has a matching role")
    actions.add_argument("--assignments", action="store_true", help="List eligible and active assignments for a user")
    actions.add_argument("--groups", action="store_true", help="List PIM-related groups for a user")
    parser.add_argument("--scope", help="Full scope, subscription ID, or resource group name")
    parser.add_argument("--user", help="Object ID or UPN")
    parser.add_argument("--role", help="Role display name filter")
    return parser


def main():
    load_env_file()
    parser = build_parser()
    args = parser.parse_args()

    if args.list_eligible:
        return list_eligible(resolve_scope(args.scope))
    if args.list_active:
        return list_active(resolve_scope(args.scope))
    if args.check:
        if not args.user or not args.role:
            fail("--check requires --user and --role")
        return check_role(resolve_scope(args.scope), args.user, args.role)
    if args.assignments:
        if not args.user:
            fail("--assignments requires --user")
        return list_assignments(args.user)
    if args.groups:
        if not args.user:
            fail("--groups requires --user")
        return list_groups(args.user)
    fail("No action selected")


if __name__ == "__main__":
    sys.exit(main())
