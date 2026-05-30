#!/usr/bin/env python3
"""
az_investigate.py — Higher-level Azure investigation workflows.

Usage:
    python3 scripts/az_investigate.py --identity NAME
    python3 scripts/az_investigate.py --access RESOURCE_NAME --rg RESOURCE_GROUP
    python3 scripts/az_investigate.py --rg-inventory RESOURCE_GROUP
    python3 scripts/az_investigate.py --compare-rg RG1 RG2
    python3 scripts/az_investigate.py --subscription-summary

Environment:
    AZURE_SUBSCRIPTION_ID  — target subscription (optional; uses current az context if not set)
"""

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, AZURE_COMMON_CAUSES

from az_resource import (
    extract_resource_group,
    get_resource,
    load_env_file,
    print_table,
    run_az_json,
    truncate,
    with_subscription,
)


SECTION_WIDTH = 72


def section(title):
    print(f"\n{'=' * SECTION_WIDTH}")
    print(title)
    print(f"{'=' * SECTION_WIDTH}")


def run_az_json_local(command, include_subscription=True):
    full_command = with_subscription(command + ["-o", "json"]) if include_subscription else command + ["-o", "json"]
    try:
        result = subprocess.run(full_command, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError("az CLI is not installed") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(detail or "az command failed")
    try:
        return json.loads(result.stdout or "null")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse az output: {exc}") from exc


def get_subscription_info():
    return run_az_json(["az", "account", "show"])


def get_subscription_id():
    return str(get_subscription_info().get("id") or "")


def format_tags(tags):
    if not tags:
        return "—"
    pairs = [f"{key}={tags[key]}" for key in sorted(tags)]
    return truncate(", ".join(pairs), 48)


def identity_summary(resource):
    identity = resource.get("identity") or {}
    if not identity:
        return "—"
    identity_type = identity.get("type") or "—"
    user_assigned = identity.get("userAssignedIdentities") or {}
    if user_assigned:
        names = [rid.split("/")[-1] for rid in sorted(user_assigned)]
        return truncate(f"{identity_type}: {', '.join(names)}", 48)
    principal_id = identity.get("principalId")
    if principal_id:
        return truncate(f"{identity_type}: {principal_id}", 48)
    return truncate(identity_type, 48)


def normalize_resource_name(name):
    normalized = str(name or "")
    for token in ("-dev-", "-tst-", "-stg-", "-prd-"):
        normalized = normalized.replace(token, "-{env}-")
    return normalized


def resource_key(resource):
    return (
        str(resource.get("type") or "").lower(),
        normalize_resource_name(resource.get("name") or "").lower(),
    )


def comparable_resource_shape(resource):
    sku = resource.get("sku") or {}
    return {
        "location": resource.get("location") or "",
        "kind": resource.get("kind") or "",
        "sku": f"{sku.get('name', '')}:{sku.get('tier', '')}",
        "identity": identity_summary(resource),
        "tags": json.dumps(resource.get("tags") or {}, sort_keys=True),
    }


def role_origin(assignment, scope):
    assignment_scope = str(assignment.get("scope") or "")
    return "direct" if assignment_scope.lower() == scope.lower() else "inherited"


def print_grouped_assignments(assignments, scope):
    grouped = defaultdict(list)
    for assignment in assignments:
        principal_type = str(assignment.get("principalType") or "Unknown")
        grouped[principal_type].append(assignment)

    if not grouped:
        print("⚠ No role assignments found")
        return

    for principal_type in sorted(grouped):
        print(f"\n[{principal_type}]")
        rows = []
        for item in sorted(grouped[principal_type], key=lambda value: str(value.get("principalName") or "")):
            rows.append([
                truncate(item.get("principalName") or "—", 38),
                truncate(item.get("roleDefinitionName") or "—", 34),
                role_origin(item, scope),
            ])
        print_table(["PRINCIPAL", "ROLE", "ORIGIN"], rows)


def print_identity_matches(identities):
    rows = []
    for identity in identities:
        rows.append([
            truncate(identity.get("name") or "—", 28),
            truncate(extract_resource_group(identity), 28),
            truncate(identity.get("clientId") or "—", 36),
            truncate(identity.get("principalId") or "—", 36),
        ])
    print_table(["NAME", "RESOURCE GROUP", "CLIENT ID", "PRINCIPAL ID"], rows)


def resolve_app_role_names(assignments):
    resolved = []
    resource_cache = {}
    for assignment in assignments:
        resource_id = assignment.get("resourceId")
        app_role_id = assignment.get("appRoleId")
        role_name = assignment.get("appRoleId") or "—"
        if resource_id and resource_id not in resource_cache:
            try:
                resource = run_az_json_local([
                    "az", "rest", "--method", "get",
                    "--uri", f"https://graph.microsoft.com/v1.0/servicePrincipals/{resource_id}?$select=displayName,appRoles",
                ], include_subscription=False)
                app_roles = resource.get("appRoles") or []
                resource_cache[resource_id] = {
                    "name": resource.get("displayName") or assignment.get("resourceDisplayName") or "—",
                    "roles": {item.get("id"): item for item in app_roles},
                }
            except RuntimeError:
                resource_cache[resource_id] = {
                    "name": assignment.get("resourceDisplayName") or "—",
                    "roles": {},
                }
        if resource_id and resource_id in resource_cache and app_role_id in resource_cache[resource_id]["roles"]:
            app_role = resource_cache[resource_id]["roles"][app_role_id]
            role_name = app_role.get("value") or app_role.get("displayName") or str(app_role_id)
        resolved.append({
            "resource": assignment.get("resourceDisplayName") or resource_cache.get(resource_id, {}).get("name") or "—",
            "role": role_name,
        })
    return resolved


def get_graph_app_role_assignments(service_principal_id):
    response = run_az_json_local([
        "az", "rest", "--method", "get",
        "--uri", (
            "https://graph.microsoft.com/v1.0/"
            f"servicePrincipals/{service_principal_id}/appRoleAssignments"
            "?$select=resourceDisplayName,resourceId,appRoleId"
        ),
    ], include_subscription=False)
    return response.get("value") or []


def find_identity_references(identity):
    identity_id = str(identity.get("id") or "").lower()
    principal_id = str(identity.get("principalId") or "").lower()
    resources = run_az_json(["az", "resource", "list"])
    references = []
    for resource in resources:
        attached_identity = resource.get("identity") or {}
        if not attached_identity:
            continue
        reasons = []
        user_assigned = attached_identity.get("userAssignedIdentities") or {}
        if any(str(key).lower() == identity_id for key in user_assigned):
            reasons.append("userAssigned")
        if principal_id and str(attached_identity.get("principalId") or "").lower() == principal_id:
            reasons.append("principalId")
        if reasons:
            references.append([
                truncate(resource.get("name") or "—", 34),
                truncate(resource.get("type") or "—", 42),
                truncate(extract_resource_group(resource), 28),
                ",".join(reasons),
            ])
    return references


def investigate_identity(name_pattern):
    safe_pattern = name_pattern.replace("'", "\\'")
    identities = run_az_json([
        "az", "identity", "list",
        "--query", f"[?contains(name, '{safe_pattern}')]",
    ])
    if not identities:
        print(f"⚠ No managed identities matched '{name_pattern}'")
        return 0

    section(f"Managed identity search: {name_pattern}")
    print_identity_matches(identities)
    print(f"✓ Found {len(identities)} matching managed identit(ies)")

    for identity in identities:
        section(f"Managed Identity: {identity.get('name', '—')}")
        print(f"Resource group : {extract_resource_group(identity)}")
        print(f"Client ID      : {identity.get('clientId', '—')}")
        print(f"Principal ID   : {identity.get('principalId', '—')}")
        print(f"Resource ID    : {identity.get('id', '—')}")

        assignments = run_az_json([
            "az", "role", "assignment", "list",
            "--assignee", identity.get("principalId") or "",
            "--include-inherited",
        ])
        print("\nRBAC")
        if assignments:
            rows = []
            for assignment in sorted(assignments, key=lambda value: (str(value.get("roleDefinitionName") or ""), str(value.get("scope") or ""))):
                rows.append([
                    truncate(assignment.get("roleDefinitionName") or "—", 34),
                    truncate(assignment.get("scope") or "—", 72),
                ])
            print_table(["ROLE", "SCOPE"], rows)
        else:
            print("⚠ No RBAC role assignments found")

        print("\nGraph API app roles")
        graph_lookup_failed = False
        try:
            graph_assignments = get_graph_app_role_assignments(identity.get("principalId") or "")
        except RuntimeError as exc:
            graph_assignments = []
            graph_lookup_failed = True
            print(f"⚠ Graph lookup failed: {exc}")
        if graph_assignments:
            rows = []
            for item in resolve_app_role_names(graph_assignments):
                rows.append([
                    truncate(item["resource"], 30),
                    truncate(item["role"], 40),
                ])
            print_table(["RESOURCE", "APP ROLE"], rows)
        elif not graph_lookup_failed:
            print("⚠ No Graph app role assignments found")

        print("\nAttached resources")
        references = find_identity_references(identity)
        if references:
            print_table(["NAME", "TYPE", "RESOURCE GROUP", "MATCH"], references)
        else:
            print("⚠ No attached resources found")
    return 0


def investigate_access(resource_name, resource_group):
    resource = get_resource(resource_name, resource_group)
    scope = resource.get("id") or ""
    assignments = run_az_json([
        "az", "role", "assignment", "list",
        "--scope", scope,
        "--include-inherited",
    ])

    section(f"Access report: {resource.get('name', resource_name)}")
    print(f"Resource type : {resource.get('type', '—')}")
    print(f"Resource ID   : {scope}")
    print_grouped_assignments(assignments, scope)
    print(f"\n✓ Listed {len(assignments)} role assignment(s)")
    return 0


def inventory_resource_group(resource_group):
    subscription_id = get_subscription_id()
    scope = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
    resources = run_az_json(["az", "resource", "list", "--resource-group", resource_group])
    identities = run_az_json(["az", "identity", "list", "--resource-group", resource_group])
    assignments = run_az_json([
        "az", "role", "assignment", "list",
        "--scope", scope,
        "--include-inherited",
    ])

    section(f"Resource group inventory: {resource_group}")
    print(f"Resources              : {len(resources)}")
    print(f"Managed identities     : {len(identities)}")
    print(f"Role assignments on RG : {len(assignments)}")

    print("\nResources")
    if resources:
        rows = []
        for resource in sorted(resources, key=lambda value: (str(value.get("type") or ""), str(value.get("name") or ""))):
            rows.append([
                truncate(resource.get("name") or "—", 30),
                truncate(resource.get("type") or "—", 42),
                truncate(resource.get("location") or "—", 14),
                truncate(identity_summary(resource), 48),
                format_tags(resource.get("tags") or {}),
            ])
        print_table(["NAME", "TYPE", "LOCATION", "IDENTITY", "TAGS"], rows)
    else:
        print("⚠ No resources found")

    print("\nManaged identities")
    if identities:
        print_identity_matches(identities)
    else:
        print("⚠ No managed identities found")

    print("\nRole assignments")
    print_grouped_assignments(assignments, scope)
    return 0


def compare_resource_groups(left_group, right_group):
    left_resources = run_az_json(["az", "resource", "list", "--resource-group", left_group])
    right_resources = run_az_json(["az", "resource", "list", "--resource-group", right_group])
    left_map = {resource_key(resource): resource for resource in left_resources}
    right_map = {resource_key(resource): resource for resource in right_resources}

    only_left = [left_map[key] for key in sorted(left_map.keys() - right_map.keys())]
    only_right = [right_map[key] for key in sorted(right_map.keys() - left_map.keys())]
    shared_keys = sorted(left_map.keys() & right_map.keys())

    section(f"Compare RGs: {left_group} vs {right_group}")

    print(f"Only in {left_group}")
    if only_left:
        rows = [[truncate(resource.get("name") or "—", 30), truncate(resource.get("type") or "—", 42)] for resource in only_left]
        print_table(["NAME", "TYPE"], rows)
    else:
        print("✓ None")

    print(f"\nOnly in {right_group}")
    if only_right:
        rows = [[truncate(resource.get("name") or "—", 30), truncate(resource.get("type") or "—", 42)] for resource in only_right]
        print_table(["NAME", "TYPE"], rows)
    else:
        print("✓ None")

    print("\nConfiguration differences")
    diff_rows = []
    for key in shared_keys:
        left_shape = comparable_resource_shape(left_map[key])
        right_shape = comparable_resource_shape(right_map[key])
        differences = []
        for field in sorted(left_shape):
            if left_shape[field] != right_shape[field]:
                differences.append(f"{field} differs")
        if differences:
            diff_rows.append([
                truncate(left_map[key].get("name") or "—", 30),
                truncate(left_map[key].get("type") or "—", 42),
                truncate("; ".join(differences), 48),
            ])
    if diff_rows:
        print_table(["NAME", "TYPE", "DIFFERENCE"], diff_rows)
    else:
        print("✓ Matching resources have the same compared shape")
    return 0


def subscription_summary():
    account = get_subscription_info()
    resource_groups = run_az_json(["az", "group", "list"])
    resources = run_az_json(["az", "resource", "list"])
    identities = run_az_json(["az", "identity", "list"])
    key_vaults = [resource for resource in resources if resource.get("type") == "Microsoft.KeyVault/vaults"]

    resources_by_group = defaultdict(int)
    identities_by_group = defaultdict(int)
    for resource in resources:
        resources_by_group[extract_resource_group(resource)] += 1
    for identity in identities:
        identities_by_group[extract_resource_group(identity)] += 1

    section("Subscription summary")
    print(f"Subscription name : {account.get('name', '—')}")
    print(f"Subscription ID   : {account.get('id', '—')}")
    print(f"Tenant ID         : {account.get('tenantId', '—')}")
    print(f"Resource groups   : {len(resource_groups)}")
    print(f"Managed identities: {len(identities)}")
    print(f"Key Vaults        : {len(key_vaults)}")

    rows = []
    for group in sorted(resource_groups, key=lambda value: str(value.get("name") or "")):
        name = str(group.get("name") or "—")
        rows.append([
            truncate(name, 32),
            str(resources_by_group.get(name, 0)),
            str(identities_by_group.get(name, 0)),
            truncate(group.get("location") or "—", 14),
        ])
    print("\nResource groups")
    print_table(["RESOURCE GROUP", "RESOURCES", "UMIS", "LOCATION"], rows)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Higher-level Azure investigation workflows")
    parser.add_argument("--rg", help="Azure resource group for --access")
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument("--identity", metavar="NAME", help="Investigate a managed identity")
    action_group.add_argument("--access", metavar="RESOURCE_NAME", help="Show who has access to a resource")
    action_group.add_argument("--rg-inventory", metavar="RESOURCE_GROUP", help="Inventory a resource group")
    action_group.add_argument("--compare-rg", nargs=2, metavar=("RG1", "RG2"), help="Compare two resource groups")
    action_group.add_argument("--subscription-summary", action="store_true", help="Summarize the current subscription")
    return parser


def main():
    load_env_file()
    parser = build_parser()
    args = parser.parse_args()
    if len(sys.argv) == 1:
        parser.print_help()
        return 1
    try:
        if args.identity:
            return investigate_identity(args.identity)
        if args.access:
            if not args.rg:
                return fail("--access requires --rg")
            return investigate_access(args.access, args.rg)
        if args.rg_inventory:
            return inventory_resource_group(args.rg_inventory)
        if args.compare_rg:
            return compare_resource_groups(args.compare_rg[0], args.compare_rg[1])
        if args.subscription_summary:
            return subscription_summary()
        parser.print_help()
        return 1
    except Exception as exc:
        return fail(str(exc))


if __name__ == "__main__":
    sys.exit(main())
