---
name: fabric-deploy
description: 'Manage Microsoft Fabric pipeline deployments, verify schedules, and restore schedule configurations after CI/CD deploys. Use when the user says "deploy fabric pipeline", "check pipeline schedule", "fix schedule after deploy", or wants to trigger/monitor Fabric pipeline runs.'
argument-hint: 'Specify the action: list pipelines, check schedule, trigger run, save/restore schedule'
---

# Fabric Deploy Skill

Manage Microsoft Fabric pipeline deployments, verify schedules, and restore schedule configurations after CI/CD deploys. Wraps `scripts/fabric_pipeline.py`.

## When to Use

- User says "deploy fabric pipeline", "check pipeline schedule", "fix schedule after deploy"
- After a deployment that may have dropped schedule triggers (known issue)
- Checking run status on a pipeline that should have fired
- Saving/restoring schedule configuration around a deployment

---

## Workspace IDs (<org_short>)

| Workspace | ID |
|-----------|-----|
| <workspace_prod> | `<RESOURCE_GUID>` |
| ws_loanetl | *(check .env or az)*  |

Set default: `FABRIC_WORKSPACE_ID` in `.env`

---

## Workflow

### List pipelines

```bash
cd /home/acestus/git/ace && export $(grep -v '^#' .env | xargs)

python3 scripts/fabric_pipeline.py --workspace-id {WS_ID} --list
```

### Before deploying — save the schedule

Always back up schedule config before a deployment that touches a pipeline:

```bash
python3 scripts/fabric_pipeline.py \
  --workspace-id {WS_ID} \
  --save-schedule {PIPELINE_ID} \
  --output /tmp/{pipeline-name}-schedule.json
```

### After deploying — verify and restore

```bash
# Check if schedule survived
python3 scripts/fabric_pipeline.py --workspace-id {WS_ID} --get-schedule {PIPELINE_ID}

# If missing, restore from backup
python3 scripts/fabric_pipeline.py \
  --workspace-id {WS_ID} \
  --set-schedule {PIPELINE_ID} \
  --schedule-file /tmp/{pipeline-name}-schedule.json
```

### Trigger a pipeline run manually

```bash
python3 scripts/fabric_pipeline.py --workspace-id {WS_ID} --trigger {PIPELINE_ID}
```

### Check recent runs

```bash
python3 scripts/fabric_pipeline.py --workspace-id {WS_ID} --list-runs {PIPELINE_ID}

# Specific run status
python3 scripts/fabric_pipeline.py \
  --workspace-id {WS_ID} \
  --run-status {PIPELINE_ID} \
  --run-id {RUN_ID}
```

### List all workspaces

```bash
python3 scripts/fabric_pipeline.py --list-workspaces
```

---

## Schedule Loss Pattern (<PROJECT>-366 fix)

The known issue: Fabric deployment API replaces the pipeline definition and drops schedule config.

**Safe deploy sequence:**
1. `--save-schedule` → back up to `/tmp/`
2. Run deployment (GitHub Actions or manual)
3. `--get-schedule` → confirm it dropped
4. `--set-schedule` with the saved file → restore
5. `--list-runs` → confirm next run is scheduled

---

## Notes

- Auth: `az account get-access-token --resource https://api.fabric.microsoft.com` — requires active `az login`
- Falls back to Power BI resource URL for older tenant configurations
- The `<workspace_prod>` workspace runs the nightly DMO pipeline at 17:30 UTC — verify this after any deployment
- Gateway connection `<GATEWAY_CONNECTION_ID>` must be active for DMO run to succeed (<PEER_NAME> owns this)

---

## Stop the Line

**Hard stops — halt the deployment if:**
- Schedule backup was NOT taken before deploy → "🛑 Stop the line: no schedule backup. Run --save-schedule first."
- Post-deploy schedule check shows dropped config AND no backup file exists → "🛑 Stop the line: schedule lost with no backup. Manual recovery required."
- Pipeline run fails within 30 minutes of deploy → "🛑 Stop the line: first run after deploy failed. Investigate before proceeding."

These conditions require immediate attention. Do not proceed to the next pipeline or workspace until resolved.

## Learning Feedback

After every deployment cycle (save → deploy → verify → restore):
1. If the schedule was dropped (known pattern), confirm restoration and log the occurrence in the issue file:
   ```
   ⚠ Schedule drop detected again on {pipeline_name}. Pattern count: {N} since initial fix.
     → If count > 3: escalate to Microsoft support as regression.
   ```
2. If a new failure mode is observed (not schedule-related), flag for pattern capture:
   ```
   💡 New deployment failure mode: {description}
      → Add to planner/patterns/fabric.md? (say "pattern" to capture)
   ```
