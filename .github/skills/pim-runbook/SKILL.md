---
name: pim-runbook
description: 'Manage Azure PIM role assignments — check eligibility, confirm activations, update runbook documentation. Use when the user says "check PIM", "does X have the role", "set up PIM access", or is working PIM-related tickets.'
argument-hint: 'Specify what to check: user eligibility, group membership, activation status, or runbook update'
---

# PIM Runbook Skill

Manage Azure Privileged Identity Management (PIM) role assignments — check eligibility, confirm activations, update runbook documentation. Wraps `scripts/az_pim.py` and `scripts/entra_lookup.py`.

## When to Use

- User says "check PIM for X", "does Y have the PIM role", "set up PIM access"
- Working tickets about PIM assignment configuration (<PROJECT>-342, <PROJECT>-357, <TICKET-ID> pattern)
- Confirming a user's PIM eligible/active state before closing a ticket
- Writing or updating a PIM runbook section in Confluence

---

## Workflow

### Check current state

```bash
cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)

# Your own eligible and active assignments
python3 scripts/az_pim.py --list-eligible
python3 scripts/az_pim.py --list-active

# Another user's assignments
python3 scripts/az_pim.py --assignments --user <YOUR_EMAIL>

# Check if a user has a specific role eligible
python3 scripts/az_pim.py --check --user rarora@<ORG_DOMAIN> --role "Contributor"
```

### Check PIM group membership

```bash
# All PIM-related groups a user belongs to
python3 scripts/az_pim.py --groups --user <YOUR_EMAIL>

# Confirm a specific group's members
python3 scripts/entra_lookup.py --group "azpim-prd-edmlevel1"
```

### Scope patterns (for --list-eligible --scope)

| Scope | Pattern |
|-------|---------|
| Full subscription | `/subscriptions/{sub-id}` |
| Resource group | `/subscriptions/{sub-id}/resourceGroups/{rg-name}` |
| Specific resource | `/subscriptions/{sub-id}/resourceGroups/{rg}/providers/{type}/{name}` |

### Typical PIM setup workflow (from <PROJECT>-342/357 pattern)

1. Verify the Entra group exists:
   ```bash
   python3 scripts/entra_lookup.py --group "azpim-prd-edmlevel1"
   ```
2. Confirm user is a member:
   ```bash
   python3 scripts/az_pim.py --groups --user TARGET@<ORG_DOMAIN>
   ```
3. Check eligible assignments:
   ```bash
   python3 scripts/az_pim.py --list-eligible --scope /subscriptions/{sub}
   ```
4. If user is missing: escalate to Azure Portal — PIM eligible assignments require Owner/UAA on the scope

---

## Runbook Update Pattern

After resolving a PIM ticket, update the runbook:
```bash
python3 scripts/confluence_update_page.py \
  --page-id {RUNBOOK_PAGE_ID} \
  --replace-section "Access Setup" \
  "Updated {DATE}: {RESOURCE} — {USER} added to {GROUP} with {ROLE} eligible via PIM."
```

---

## Notes

- PIM API requires an active az login session with subscription access
- `AZURE_SUBSCRIPTION_ID` in `.env` sets default subscription; override with `--scope`
- Eligible ≠ Active — a user with an eligible assignment still needs to activate in Azure Portal or via `az rest`
- PIM activation window is typically 8h (per <org_short> config on azpim-prd-* groups)
- Eligible assignment creation requires `Privileged Role Administrator` or `Owner` at that scope
