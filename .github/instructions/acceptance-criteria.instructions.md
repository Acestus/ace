# Acceptance Criteria for iac-infra Changes

## Purpose

This document defines the acceptance criteria that all changes to this repository must satisfy before merging. Use these checklists during PR review and before marking work as complete.

---

## 1. Bicep Stack Criteria

### Structure & Naming

- [ ] Stack folder is named using the project short code (e.g., `skpmon`, `skpad`, `skpedm`) — not the resource group name
- [ ] `main.bicep` exists at the stack root and references AVM modules from the Bicep public registry (`br/public:avm/...`)
- [ ] No local module copies in `modules-bicep/` — all resources use Azure Verified Modules (AVM)
- [ ] Environment parameter files follow the pattern `{env}/main.{env}.bicepparam` (e.g., `dev/main.dev.bicepparam`)
- [ ] Parameter files use `using '../main.bicep'` to reference the shared template

### Resource Naming (CAF)

- [ ] All Azure resources follow CAF naming: `{type}-{project}-{env}-{region}-{instance}` (e.g., `amg-skpmon-dev-usw2-01`)
- [ ] Region code is `usw2` (West US 2) unless deploying to a different region
- [ ] Environment codes are `dev`, `stg`, or `prd`

### Identity & Security

- [ ] Per-workload identity is a **single data-plane UMI**: `umi-{project}-{env}-{region}-dat`
- [ ] The data-plane UMI lives in the **identity subscription**, in a resource group named `rg-{project}-{env}-id` (e.g. `rg-skpwatch-dev-id`) — not in the workload's resource group
- [ ] **Do not create a per-workload control-plane UMI.** Control-plane operations use the shared platform control-plane UMI provided by the identity subscription
- [ ] Workload Bicep references the data-plane UMI via `existing` (cross-subscription/cross-RG); the UMI is provisioned out-of-band in the identity subscription
- [ ] No hardcoded secrets, connection strings, or API keys in Bicep files or parameter files
- [ ] Sensitive values are passed via Key Vault references or deployment parameters
- [ ] RBAC role assignments follow least-privilege — only the roles actually needed

### Deployment

- [ ] Stack is deployable via `./scripts/deploy-bicep.ps1 -Env {env} -Stack {stack} -Action deploy`
- [ ] `deploy-bicep.ps1` can parse the `.bicepparam` file to extract resource group and subscription
- [ ] **All stacks use `targetScope = 'resourceGroup'`** — `az stack sub create` is never used
- [ ] Resource group is pre-created by `deploy-bicep.ps1` via `az group create` if it does not exist
- [ ] For identity stacks whose RG name has a suffix (e.g. `rg-{project}-{env}-id`), add a `// deploy-rg: {name}` directive to the bicepparam file to override the default derived name
- [ ] Stack deploys cleanly with no errors on `az stack group create`
- [ ] Deployment is idempotent — running deploy twice produces no changes

---

## 2. Terraform Stack Criteria

### Structure & Naming

- [ ] Stack folder exists under `stacks-terraform/{stack-name}/`
- [ ] Contains `providers.tf`, `main.tf`, `variables.tf`, `outputs.tf`
- [ ] Environment-specific variable files follow `{env}/terraform.{env}.tfvars`
- [ ] `.gitignore` in the stack root ignores `.terraform/`, `*.tfstate`, `.env`

### State & Backend

- [ ] Remote backend is configured in `providers.tf` using azurerm (storage account `sttfstatedevusw2001`)
- [ ] State container name matches the stack name
- [ ] State files are never committed to the repository

### Auth & Secrets

- [ ] Provider authentication uses OIDC (workload identity) in CI/CD, not stored credentials
- [ ] Local authentication secrets are loaded from `.env` files (git-ignored)
- [ ] Sensitive variables are marked with `sensitive = true`
- [ ] No secrets appear in Terraform plan output or state file names

### Deployment

- [ ] Stack is deployable via `./scripts/deploy-terraform.ps1 -Env {env} -Stack {stack} -Action apply`
- [ ] `terraform plan` shows expected changes only — no unrelated drift
- [ ] `terraform apply` completes without errors
- [ ] Deployment is idempotent — re-apply shows `No changes`

---

## 3. Script Criteria

- [ ] PowerShell scripts use PascalCase filenames (e.g., `Deploy-Bicep.ps1`, `Check-BicepStack.ps1`)
- [ ] Scripts include `param()` blocks with typed, validated parameters
- [ ] Error handling uses `try/catch` with meaningful error messages
- [ ] Scripts use emoji-prefixed status output (`🚀`, `✅`, `❌`, `⚠️`) for readability
- [ ] Scripts do not contain hardcoded subscription IDs, resource names, or secrets
- [ ] Scripts that load secrets use `.env` file pattern with `KEY=VALUE` parsing

---

## 4. GitHub Actions Workflow Criteria

### File Conventions

- [ ] Workflow files use `.yaml` extension (not `.yml`) for new files
- [ ] Workflow filename describes the action: `deploy-{tool}-{env}.yaml` or `func-{action}-{lang}.yaml`

### Authentication

- [ ] OIDC authentication via `azure/login` with `client-id`, `tenant-id`, `subscription-id`
- [ ] No long-lived secrets for Azure authentication
- [ ] `permissions: id-token: write` is set for OIDC workflows
- [ ] Workflow permissions follow least-privilege (only `contents: read` unless writing is needed)

### Environment Protection

- [ ] Production deployments require approval via GitHub environment protection rules
- [ ] Dev deployments can be automatic on push to `dev` branch
- [ ] Changed stacks are auto-detected where possible (path-based triggers or diff detection)

---

## 5. Dashboard / Observability Criteria

### Grafana Dashboards

- [ ] Dashboard JSON files are stored in `stacks-bicep/{stack}/dashboards/`
- [ ] Dashboard JSON uses the `{ "dashboard": { ... } }` wrapper format
- [ ] `uid` field follows the pattern `{stack}-{dashboard-name}` (e.g., `skpmon-vnet-traffic-overview`)
- [ ] Azure Monitor datasource uses `uid: "azure-monitor-oob"` (built-in)
- [ ] Metric names match exactly what is available from `az monitor metrics list-definitions`
- [ ] All panels show data (no `No data` panels) — verified after deployment
- [ ] Subscription IDs and resource group names use template placeholders (`__CONN_SUBSCRIPTION__`, `__CONN_RESOURCE_GROUP__`) or are parameterised in tfvars

### Azure Workbooks

- [ ] Workbook JSON files are stored in `stacks-bicep/{stack}/workbooks/`
- [ ] KQL queries are syntactically valid and tested against the target Log Analytics workspace

---

## 6. General Criteria (All Changes)

### Code Quality

- [ ] No hardcoded secrets, passwords, API keys, or connection strings anywhere
- [ ] No commented-out code blocks left behind
- [ ] Changes are scoped — only files relevant to the change are modified
- [ ] Existing patterns and conventions in the repo are followed (don't invent new ones)

### Documentation

- [ ] `CHANGELOG.md` is updated with the change under `[Unreleased]` or today's date section
- [ ] `README.md` is updated if the change adds/removes stacks, scripts, or workflows
- [ ] Complex Bicep parameters or Terraform variables include `@description()` or `description =`

### Git Hygiene

- [ ] Commits use conventional commit messages: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`
- [ ] No generated files committed (`.terraform/`, `node_modules/`, `*.tfstate`, `.env`)
- [ ] Large binary files or JSON exports are git-ignored
- [ ] Branch is up to date with `main` before merge

### Testing

- [ ] Bicep stacks: `az bicep build` succeeds with no errors
- [ ] Terraform stacks: `terraform validate` passes
- [ ] Deployment was tested in `dev` environment before targeting `prd`
- [ ] Idempotency verified — second deployment shows no changes
