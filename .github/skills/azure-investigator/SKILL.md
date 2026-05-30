---
name: azure-investigator
description: 'Investigate Azure resources, managed identities, role assignments, and access patterns. Use when the user asks about Azure permissions, RBAC, resource inventory, identity investigation, or access debugging. Wraps az CLI with higher-level investigation commands.'
argument-hint: 'Specify what to investigate: an identity name, resource group, or access scope'
---

# Azure Investigator Skill

Use this when the question is really "what exists, who can touch it, and why is access broken?" Start with the high-level workflow in `scripts/az_investigate.py`. Drop to the lower-level scripts only when you need a precise query.

## When to Use

Use this skill when the user says things like:

- "Investigate this managed identity"
- "Who has access to this Key Vault?"
- "Give me everything in `rg-skpedm-prd-usw2-001`"
- "Compare dev and prd resource groups"
- "Why is this identity getting 403s?"
- "What changed between these two Azure environments?"

This is the standard order:
1. Confirm Azure context.
2. Run the smallest investigation command that answers the question.
3. If the high-level report surfaces something odd, drill in with `az_resource.py` or `entra_lookup.py`.
4. If this came from a ticket, push findings back into the issue file.

## Quick Start

These are the three commands you use most:

```bash
cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)

# Full managed identity investigation
python3 scripts/az_investigate.py --identity umi-skpedm-prd-usw2-ctl

# Who has access to a specific resource?
python3 scripts/az_investigate.py --access kv-skpedm-prd-usw2-001 --rg rg-skpedm-prd-usw2-001

# Full RG inventory for ticket work
python3 scripts/az_investigate.py --rg-inventory rg-skpedm-prd-usw2-001
```

## Investigation Workflows

### 1. Managed identity investigation

```bash
python3 scripts/az_investigate.py --identity umi-skpedm-prd-usw2-ctl
```

What it does:
1. Finds matching user-assigned managed identities.
2. Lists RBAC role assignments for the identity principal.
3. Calls Microsoft Graph with `az rest` to check app role assignments.
4. Scans Azure resources to find where that identity is attached.

Example output:

```text
=== Managed Identity: umi-skpedm-prd-usw2-ctl ===
Name           Resource Group             Client ID                              Principal ID
-------------  -------------------------  ------------------------------------  ------------------------------------
umi-skpedm...  rg-skpedm-prd-usw2-001     11111111-2222-3333-4444-555555555555  aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee

RBAC
PRINCIPAL TYPE     ROLE                         SCOPE
ServicePrincipal   Key Vault Secrets User       /subscriptions/.../vaults/kv-skpedm-prd-usw2-001
ServicePrincipal   Storage Blob Data Reader     /subscriptions/.../storageAccounts/stskpedmprd001

Graph API app roles
RESOURCE           APP ROLE
Microsoft Graph    User.Read.All
Microsoft Graph    Group.Read.All

Attached resources
NAME                          TYPE                                           RESOURCE GROUP
func-skpedm-prd-usw2-001      Microsoft.Web/sites                            rg-skpedm-prd-usw2-001
aca-skpedm-prd-usw2-api       Microsoft.App/containerApps                    rg-skpedm-prd-usw2-001
```

Use this first for 403s, token failures, and "does this identity actually have what it needs?"

### 2. Resource access investigation

```bash
python3 scripts/az_investigate.py --access kv-skpedm-prd-usw2-001 --rg rg-skpedm-prd-usw2-001
```

What it does:
1. Resolves the resource ID.
2. Lists role assignments on that resource scope.
3. Groups assignments by principal type so you can see users, groups, and service principals separately.
4. Marks whether access is direct or inherited.

Example output:

```text
=== Access report: kv-skpedm-prd-usw2-001 ===
Resource ID: /subscriptions/.../resourceGroups/rg-skpedm-prd-usw2-001/providers/Microsoft.KeyVault/vaults/kv-skpedm-prd-usw2-001

[Group]
PRINCIPAL                    ROLE                     ORIGIN
azpim-prd-edmlevel1          Key Vault Secrets User   inherited

[ServicePrincipal]
umi-skpedm-prd-usw2-ctl      Key Vault Secrets User   direct
```

Use this when someone asks "who can read this vault?" or "why can prod app X access this resource but dev can't?"

### 3. Resource group inventory

```bash
python3 scripts/az_investigate.py --rg-inventory rg-skpedm-prd-usw2-001
```

What it does:
1. Lists every resource in the RG.
2. Lists managed identities in the RG.
3. Pulls role assignments on the RG scope.
4. Prints tags and identity attachments so you can spot drift fast.

Example output:

```text
=== Resource group inventory: rg-skpedm-prd-usw2-001 ===
Resources: 12
Managed identities: 2
Role assignments on RG scope: 9

Resources
NAME                         TYPE                                  IDENTITY              TAGS
kv-skpedm-prd-usw2-001       Microsoft.KeyVault/vaults             —                     env=prd, owner=edm
umi-skpedm-prd-usw2-ctl      Microsoft.ManagedIdentity/...         principalId=aaaa...    env=prd
func-skpedm-prd-usw2-001     Microsoft.Web/sites                   UserAssigned           env=prd, app=dmo
```

Use this for ticket triage. It gives you the RG state without making you stitch together five separate `az` calls.

### 4. Compare two resource groups

```bash
python3 scripts/az_investigate.py --compare-rg rg-skpedm-dev-usw2-001 rg-skpedm-prd-usw2-001
```

What it does:
1. Loads both RG inventories.
2. Shows resources only in one side.
3. Compares matching resources for tag, SKU, kind, location, and identity differences.

Example output:

```text
=== Compare RGs ===
Only in rg-skpedm-dev-usw2-001
- kv-skpedm-dev-usw2-001  Microsoft.KeyVault/vaults

Only in rg-skpedm-prd-usw2-001
- aca-skpedm-prd-usw2-api Microsoft.App/containerApps

Configuration differences
NAME                    DIFFERENCE
stskpedm001             tags differ; identity differs
func-skpedm-api         kind differs; sku differs
```

Use this before you call something "prod drift." Check it first.

### 5. Subscription summary

```bash
python3 scripts/az_investigate.py --subscription-summary
```

What it does:
1. Lists resource groups.
2. Counts resources per RG.
3. Counts managed identities.
4. Counts Key Vaults.

This is the fast "what's in this subscription right now?" view.

## Low-Level Toolkit

When the high-level report is not enough, drop to these:

### `scripts/az_resource.py`
Use for direct, granular Azure queries:

```bash
python3 scripts/az_resource.py --whoami
python3 scripts/az_resource.py --show kv-skpedm-prd-usw2-001 --rg rg-skpedm-prd-usw2-001
python3 scripts/az_resource.py --roles /subscriptions/{sub}/resourceGroups/rg-skpedm-prd-usw2-001
python3 scripts/az_resource.py --list-umi --filter umi-skp
```

### `scripts/entra_lookup.py`
Use for Entra lookups that are not Azure resource scoped:

```bash
python3 scripts/entra_lookup.py --mi umi-skpedm-prd-usw2-ctl
python3 scripts/entra_lookup.py --group azpim-prd-edmlevel1
python3 scripts/entra_lookup.py --user-groups <YOUR_EMAIL>
```

Rule: `az_investigate.py` first, low-level tools second.

## Integration with ticket-investigator

When a ticket needs Azure digging:
1. Run `az_investigate.py` with the smallest command that fits the question.
2. Copy the concrete findings into the issue file.
3. Record the exact resource IDs, principal IDs, roles, and missing permissions.
4. If you find drift, say which side is missing what. Don't write "configs differ" and move on.

Good issue note:

```markdown
### 2026-05-23 14:10 — Azure investigation

**Resource:** `kv-skpedm-prd-usw2-001`
**Identity:** `umi-skpedm-prd-usw2-ctl` (`principalId=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee`)

**Confirmed:**
- Identity has `Key Vault Secrets User` on the vault scope
- Identity is attached to `func-skpedm-prd-usw2-001`
- No Graph app role assignments beyond default Microsoft Graph access

**Gap:**
- Dev identity does not have the same vault role assignment
```

## Notes

- `AZURE_SUBSCRIPTION_ID` in `.env` sets the default subscription.
- `az login` still matters. If the CLI context is wrong, your report is wrong.
- Graph app role queries use `az rest`. If that fails, fix your auth before assuming permissions are missing.
- For PIM checks, use `pim-runbook`. This skill is for resource investigation, not PIM eligibility state.
