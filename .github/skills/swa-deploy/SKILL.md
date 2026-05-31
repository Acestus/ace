---
name: swa-deploy
description: 'Deploy, monitor, and debug Azure Static Web App (SWA) projects. Use when the user says "deploy the site", "check deploy status", "watch the Actions run", "why did the deploy fail", or "is fabric.acestus.com live". Wraps swa_deploy.py and swa_status.py.'
argument-hint: 'Specify repo or config path. Actions: deploy, status, watch-run RUN_ID, logs'
---

# SWA Deploy Skill

Manage the full lifecycle of an Azure Static Web App CI/CD deployment:
commit → push → watch GitHub Actions → verify Azure resource → check DNS.

Wraps `scripts/swa_deploy.py` and `scripts/swa_status.py`.

---

## Known Projects

| Site | Repo | Config | SWA Name | RG |
|------|------|--------|----------|----|
| fabric.acestus.com | `Acestus/fabricweb` | `~/github/ace/.azure/appsettings.json` | `swa-fabricweb-prd-cus-001` | `rg-fabricweb-prd` |

---

## Workflows

### Check current status (no deploy)

```bash
cd ~/github/ace
python3 scripts/swa_status.py \
  --config ~/github/ace/.azure/appsettings.json \
  --repo Acestus/fabricweb
```

Shows:
- Latest 5 GitHub Actions runs with pass/fail icons
- Azure SWA hostname
- DNS CNAME status (dig check)
- UMI existence

### Commit staged changes and deploy

```bash
cd ~/github/fabricweb
python3 ~/github/ace/scripts/swa_deploy.py \
  --repo Acestus/fabricweb \
  --message "feat: update services page" \
  --swa-name swa-fabricweb-prd-cus-001 \
  --rg rg-fabricweb-prd
```

This: stages all → commits → pushes → waits for Actions → streams output → shows SWA hostname on success.

### Watch an existing run (no commit)

```bash
python3 ~/github/ace/scripts/swa_deploy.py \
  --repo Acestus/fabricweb \
  --watch-run RUN_ID
```

### Deploy failed — get failure logs

```bash
gh run view --repo Acestus/fabricweb --log-failed $(gh run list --repo Acestus/fabricweb --limit 1 --json databaseId -q '.[0].databaseId')
```

Or use `--status` to auto-show logs for the latest failure:

```bash
python3 ~/github/ace/scripts/swa_status.py \
  --config ~/github/ace/.azure/appsettings.json \
  --repo Acestus/fabricweb
```

---

## Common Failure Patterns

| Error | Cause | Fix |
|-------|-------|-----|
| `LocationNotAvailableForResourceType` | SWA not in that region | Valid regions: `centralus`, `eastus2`, `westus2`, `westeurope`, `eastasia` |
| `outputs-should-not-contain-secrets` | Bicep output uses `listSecrets()` | Remove `deploymentToken` output; use `az staticwebapp secrets list` in workflow instead |
| `InvalidResourceGroupLocation` | RG already exists in different location | Delete and recreate RG, or use existing location |
| `workflow does not have workflow_dispatch` | Tried `gh workflow run` but no trigger | Push to `main` triggers it automatically |
| OIDC `403` on Azure Login | UMI Contributor role not assigned on RG | `az role assignment create --assignee {clientId} --role Contributor --scope {rg-scope}` |
| `No CNAME yet` in DNS check | hover.com CNAME not added | Add `fabric CNAME {swa-hostname}.azurestaticapps.net` at hover.com |

---

## DNS Setup (first deploy)

After the first successful deploy:

1. Get hostname from Actions output or:
   ```bash
   az staticwebapp show --name swa-fabricweb-prd-cus-001 --resource-group rg-fabricweb-prd \
     --query defaultHostname -o tsv
   ```

2. Add CNAME at hover.com:
   - Host: `fabric`
   - Value: `{hostname}.azurestaticapps.net`
   - TTL: 300

3. Add custom domain in Azure (Portal or CLI):
   ```bash
   az staticwebapp hostname set \
     --name swa-fabricweb-prd-cus-001 \
     --resource-group rg-fabricweb-prd \
     --hostname fabric.acestus.com
   ```

4. Update `appsettings.json` `cnameTarget` field.

---

## OIDC Identity Reference

| Item | Value |
|------|-------|
| UMI | `umi-fabricweb-prd-usw2-dat` |
| Identity RG | `rg-fabricweb-prd-id` |
| Client ID | `e19c50fa-6f17-4160-9a87-a7ae835e19a4` |
| Tenant | `f81d921a-9cda-470d-a8bd-f12b7a65091c` |
| Subscription | `df64929f-810d-4176-8097-35cd05cae10d` (acestus) |
| Federated subject | `repo:Acestus/fabricweb:environment:prd` |

GitHub env vars set on `prd` environment:
- `AZURE_CLIENT_ID` = `e19c50fa-6f17-4160-9a87-a7ae835e19a4`
- `AZURE_TENANT_ID` = `f81d921a-9cda-470d-a8bd-f12b7a65091c`
- `AZURE_SUBSCRIPTION_ID` = `df64929f-810d-4176-8097-35cd05cae10d`

---

## Files

| File | Purpose |
|------|---------|
| `~/github/ace/scripts/swa_deploy.py` | Commit + push + watch Actions + report hostname |
| `~/github/ace/scripts/swa_status.py` | Status check: Azure + Actions + DNS |
| `~/github/ace/.azure/appsettings.json` | Config: tenant, sub, RGs, UMI, SWA name |
| `~/github/fabricweb/stacks-bicep/fabricweb/` | Workload Bicep stack (SWA) |
| `~/github/fabricweb/stacks-bicep/fabricweb-id/` | Identity Bicep stack (UMI + federated cred) |
| `~/github/fabricweb/.github/workflows/deploy.yaml` | CI/CD: Hugo build → Bicep deploy → SWA deploy |
