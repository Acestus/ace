#!/usr/bin/env python3
"""
entra_lookup.py — Look up users, groups, and managed identities in Microsoft Entra ID (Azure AD).

Uses the Microsoft Graph API with client credentials (app registration).

Usage:
    # Look up a user by email or UPN
    python3 scripts/entra_lookup.py --user <YOUR_EMAIL>
    python3 scripts/entra_lookup.py --user rarora@<ORG_DOMAIN>

    # List members of a group
    python3 scripts/entra_lookup.py --group "azpim-prd-edmlevel1"

    # Look up a managed identity by display name
    python3 scripts/entra_lookup.py --mi "umi-skpedm-prd-usw2-ctl"

    # List all managed identities (filtered by name pattern)
    python3 scripts/entra_lookup.py --mi-list "umi-skp"

    # Get a user's group memberships
    python3 scripts/entra_lookup.py --user-groups <YOUR_EMAIL>

Environment (reads from .env if not already set):
    GRAPH_TENANT_ID     — Azure tenant ID
    GRAPH_CLIENT_ID     — App registration client ID
    GRAPH_CLIENT_SECRET — App registration client secret

Falls back to Azure CLI token if GRAPH_CLIENT_SECRET is not set:
    az account get-access-token --resource https://graph.microsoft.com
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, http_fail, GRAPH_COMMON_CAUSES

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def load_env_file():
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() not in os.environ:
            os.environ[k.strip()] = v.strip()


def get_token_client_credentials() -> str:
    tenant = os.environ.get("GRAPH_TENANT_ID", "")
    client_id = os.environ.get("GRAPH_CLIENT_ID", "")
    client_secret = os.environ.get("GRAPH_CLIENT_SECRET", "")
    if not all([tenant, client_id, client_secret]):
        return ""
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
    }).encode()
    req = urllib.request.Request(
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read()).get("access_token", "")
    except Exception:
        return ""


def get_token_az_cli() -> str:
    try:
        result = subprocess.run(
            ["az", "account", "get-access-token", "--resource", "https://graph.microsoft.com",
             "--query", "accessToken", "-o", "tsv"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_token() -> str:
    token = get_token_client_credentials()
    if token:
        return token
    token = get_token_az_cli()
    if token:
        print("  (using az CLI token)", file=sys.stderr)
        return token
    fail(
        "No Microsoft Graph token available",
        causes=["GRAPH_CLIENT_SECRET not set and az login session has expired",
                "GRAPH_TENANT_ID or GRAPH_CLIENT_ID are missing"],
        try_=["az login",
              "export GRAPH_TENANT_ID=... GRAPH_CLIENT_ID=... GRAPH_CLIENT_SECRET=...",
              "grep GRAPH_ .env"],
    )


def graph_get(path: str, token: str) -> dict:
    req = urllib.request.Request(
        f"{GRAPH_BASE}{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        http_fail(e, api_name="Microsoft Graph", operation=f"GET {path}",
                  common_causes=GRAPH_COMMON_CAUSES)


def print_user(u: dict):
    print(f"  Display Name : {u.get('displayName', '—')}")
    print(f"  UPN          : {u.get('userPrincipalName', '—')}")
    print(f"  Email        : {u.get('mail', '—')}")
    print(f"  Object ID    : {u.get('id', '—')}")
    print(f"  Account type : {u.get('userType', '—')}")
    print(f"  Enabled      : {u.get('accountEnabled', '—')}")


def main():
    load_env_file()

    parser = argparse.ArgumentParser(description="Look up Entra ID objects")
    parser.add_argument("--user", metavar="EMAIL", help="Look up a user by UPN/email")
    parser.add_argument("--user-groups", metavar="EMAIL", help="List a user's group memberships")
    parser.add_argument("--group", metavar="NAME", help="List members of a group by display name")
    parser.add_argument("--mi", metavar="NAME", help="Look up a managed identity by display name")
    parser.add_argument("--mi-list", metavar="PREFIX", help="List managed identities matching a name prefix")
    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        sys.exit(1)

    token = get_token()

    if args.user:
        upn = urllib.parse.quote(args.user)
        data = graph_get(f"/users/{upn}?$select=displayName,userPrincipalName,mail,id,userType,accountEnabled", token)
        print(f"\n{'─'*60}")
        print(f"  User: {args.user}")
        print(f"{'─'*60}")
        print_user(data)
        print()

    if args.user_groups:
        upn = urllib.parse.quote(args.user_groups)
        data = graph_get(f"/users/{upn}/memberOf?$select=displayName,id,groupTypes", token)
        groups = data.get("value", [])
        print(f"\n{'─'*60}")
        print(f"  Group memberships for {args.user_groups} ({len(groups)})")
        print(f"{'─'*60}")
        for g in sorted(groups, key=lambda x: x.get("displayName", "")):
            print(f"  {g.get('displayName', '—'):<50} {g.get('id', '')}")
        print()

    if args.group:
        name = urllib.parse.quote(f"displayName eq '{args.group}'")
        data = graph_get(f"/groups?$filter={name}&$select=id,displayName,description", token)
        groups = data.get("value", [])
        if not groups:
            print(f"  Group '{args.group}' not found.")
            return
        group_id = groups[0]["id"]
        print(f"\n{'─'*60}")
        print(f"  Group: {groups[0]['displayName']}")
        print(f"  ID   : {group_id}")
        desc = groups[0].get("description", "")
        if desc:
            print(f"  Desc : {desc}")
        print(f"{'─'*60}")
        members = graph_get(f"/groups/{group_id}/members?$select=displayName,userPrincipalName,id", token)
        for m in members.get("value", []):
            print(f"  {m.get('displayName', '—'):<40} {m.get('userPrincipalName', m.get('id', ''))}")
        if not members.get("value"):
            print("  (no members)")
        print()

    if args.mi:
        name = urllib.parse.quote(f"displayName eq '{args.mi}' and servicePrincipalType eq 'ManagedIdentity'")
        data = graph_get(f"/servicePrincipals?$filter={name}&$select=displayName,id,appId,servicePrincipalType", token)
        items = data.get("value", [])
        print(f"\n{'─'*60}")
        print(f"  Managed Identity: {args.mi}")
        print(f"{'─'*60}")
        if not items:
            print("  Not found in Entra ID.")
        for sp in items:
            print(f"  Display Name : {sp.get('displayName', '—')}")
            print(f"  Object ID    : {sp.get('id', '—')}  (principal ID)")
            print(f"  App/Client ID: {sp.get('appId', '—')}")
        print()

    if args.mi_list:
        prefix = args.mi_list.replace("'", "")
        name_filter = urllib.parse.quote(
            f"startswith(displayName,'{prefix}') and servicePrincipalType eq 'ManagedIdentity'"
        )
        data = graph_get(
            f"/servicePrincipals?$filter={name_filter}&$select=displayName,id,appId&$top=50", token
        )
        items = data.get("value", [])
        print(f"\n{'─'*60}")
        print(f"  Managed identities matching '{prefix}' ({len(items)})")
        print(f"{'─'*60}")
        for sp in sorted(items, key=lambda x: x.get("displayName", "")):
            print(f"  {sp.get('displayName', '—'):<50}")
            print(f"    Object ID : {sp.get('id', '—')}")
            print(f"    Client ID : {sp.get('appId', '—')}")
        print()


if __name__ == "__main__":
    main()
