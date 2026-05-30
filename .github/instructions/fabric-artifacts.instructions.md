# Fabric Artifact Creation Instructions

Instructions for creating new Microsoft Fabric artifacts in this repository, using `ws_loanetl` as reference architecture.

---

## Artifact Naming Conventions

All artifacts follow a structured naming scheme:

```
{prefix}_{domain}_{workspace}_{descriptor}
```

| Prefix | Type | Example |
|--------|------|---------|
| `lh_` | Lakehouse | `lh_loanetl_brz` |
| `nb_` | Notebook | `nb_ing_loanetl_brz` |
| `pl_` | Data Pipeline | `pl_orch_loanetl` |
| `env_` | Environment | `env_loanetl_spark` |
| `wh_` | Warehouse | `wh_sales_gld` |

Notebook sub-prefixes:

| Sub-prefix | Purpose | Example |
|------------|---------|---------|
| `nb_ing_` | Ingestion (source → Bronze) | `nb_ing_loanetl_brz` |
| `nb_tfm_` | Transformation (Bronze→Silver, Silver→Gold) | `nb_tfm_loanetl_brz_slv` |
| `nb_mnt_` | Maintenance / housekeeping | `nb_mnt_loanetl_maintenance` |
| `nb_util_` | Utility / ad-hoc / tests | `nb_util_loanetl_mockdata` |

---

## Directory Structure

Each artifact is a folder with its type as the extension:

```
ws_{workspace}/
├── lh_{domain}_{layer}.Lakehouse/
│   ├── .platform                   ← required: type + displayName + logicalId
│   ├── lakehouse.metadata.json     ← {"defaultSchema":"dbo"}
│   ├── alm.settings.json           ← ALM object type enablement
│   └── shortcuts.metadata.json     ← shortcut definitions (can be empty [])
│
├── nb_{prefix}_{domain}_{desc}.Notebook/
│   ├── .platform                   ← required: type + displayName + logicalId
│   └── notebook-content.py         ← PySpark notebook source
│
├── pl_{prefix}_{domain}.DataPipeline/
│   ├── .platform                   ← required: type + displayName + logicalId
│   └── pipeline-content.json       ← pipeline activity definitions
│
└── env_{domain}_spark.Environment/
    ├── .platform                   ← required: type + displayName + logicalId
    └── Setting.yml                 ← Spark runtime version + properties
```

---

## `.platform` File

Every artifact **must** have a `.platform` file. Use a new UUID for `logicalId`.

```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
  "metadata": {
    "type": "<ArtifactType>",
    "displayName": "<artifact_name>"
  },
  "config": {
    "version": "2.0",
    "logicalId": "<new-uuid-here>"
  }
}
```

Valid `type` values: `Lakehouse`, `Notebook`, `DataPipeline`, `Environment`, `Warehouse`

---

## Lakehouse

### Required Files

**`.platform`**
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
  "metadata": {
    "type": "Lakehouse",
    "displayName": "lh_{domain}_{layer}"
  },
  "config": {
    "version": "2.0",
    "logicalId": "<uuid>"
  }
}
```

**`lakehouse.metadata.json`**
```json
{"defaultSchema":"dbo"}
```

**`alm.settings.json`** — enable shortcuts and disable DataAccessRoles (standard):
```json
{
  "version": "1.0.1",
  "objectTypes": [
    {
      "name": "Shortcuts",
      "state": "Enabled",
      "subObjectTypes": [
        { "name": "Shortcuts.OneLake", "state": "Enabled" },
        { "name": "Shortcuts.AdlsGen2", "state": "Enabled" }
      ]
    },
    { "name": "DataAccessRoles", "state": "Disabled" }
  ]
}
```

**`shortcuts.metadata.json`** — empty unless defining shortcuts:
```json
[]
```

### Layer Guidelines

| Layer | Lakehouse | Tables | Write Pattern |
|-------|-----------|--------|---------------|
| Bronze | `lh_{domain}_brz` | `azsql_{source_table}_raw` | Overwrite / full load |
| Silver | `lh_{domain}_slv` | `{domain}_{entity}_clean` | `replaceWhere` on date partition |
| Gold | `lh_{domain}_gld` | `fct_`, `agg_`, `mart_` prefix | Overwrite or merge |

---

## Notebook

### `notebook-content.py` Structure

Follow the Fabric notebook format exactly:

```python
# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "<lakehouse-id>",
# META       "default_lakehouse_name": "lh_{domain}_{layer}",
# META       "default_lakehouse_workspace_id": "<workspace-id>",
# META       "known_lakehouses": [
# META         { "id": "<lakehouse-id>" }
# META       ]
# META     }
# META   }
# META }

# PARAMETERS CELL ********************

# Runtime parameters — overridden by pipeline at execution
etl_process_date = ""   # YYYY-MM-DD; blank = resolve from ETL control table

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

"""
nb_{prefix}_{domain}_{desc} — <Short description>
==================================================
<What this notebook does, what source it reads, what target it writes.>

Medallion Layer: <BRONZE | SILVER | GOLD>
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, lit
```

### Notebook Type Patterns

#### Ingestion (`nb_ing_`) — Source → Bronze
- Read from external source via JDBC or API
- Write Delta tables with `_brz_load_ts` and `_brz_source_table` audit columns
- Full overwrite per run (Bronze = raw, full-fidelity)
- Accept `source_jdbc_url`, `source_jdbc_user`, `source_jdbc_password` as parameters

#### Transformation Bronze→Silver (`nb_tfm__{domain}_brz_slv`)
- Read from Bronze lakehouse
- Apply cleansing, type casting, business logic
- Write using `replaceWhere` for idempotent re-runs
- Add `_slv_load_ts` audit column

#### Transformation Silver→Gold (`nb_tfm_{domain}_slv_gld`)
- Read from Silver lakehouse
- Aggregate, join, and curate for BI consumption
- Write `fct_`, `agg_`, or `mart_` prefixed tables
- Full overwrite is acceptable at Gold

#### Maintenance (`nb_mnt_`)
- OPTIMIZE, VACUUM, Z-ORDER operations
- No business logic
- Safe to run on any schedule

---

## Data Pipeline

### `pipeline-content.json` Structure

Pipelines orchestrate notebooks sequentially. Activities use `DependsOn` to enforce order:

```json
{
  "name": "pl_orch_{domain}",
  "properties": {
    "activities": [
      {
        "name": "Bronze Ingestion",
        "type": "TridentNotebook",
        "dependsOn": [],
        "typeProperties": {
          "notebookId": "<nb_ing notebook logicalId>",
          "parameters": {
            "etl_process_date": { "value": "", "type": "string" }
          }
        }
      },
      {
        "name": "Bronze to Silver",
        "type": "TridentNotebook",
        "dependsOn": [{ "activity": "Bronze Ingestion", "dependencyConditions": ["Succeeded"] }],
        "typeProperties": {
          "notebookId": "<nb_tfm_brz_slv logicalId>"
        }
      },
      {
        "name": "Silver to Gold",
        "type": "TridentNotebook",
        "dependsOn": [{ "activity": "Bronze to Silver", "dependencyConditions": ["Succeeded"] }],
        "typeProperties": {
          "notebookId": "<nb_tfm_slv_gld logicalId>"
        }
      }
    ]
  }
}
```

---

## Environment

Use `env_{domain}_spark.Environment` to pin the Spark runtime and configure properties. Attach to all notebooks in the workspace.

### `Setting.yml`
```yaml
sparkRuntimeVersion: "1.3"   # Spark 3.5 / Delta 3.2 — recommended

sparkProperties:
  spark.databricks.delta.optimizeWrite.enabled: "true"
  spark.databricks.delta.autoCompact.enabled: "true"
  spark.databricks.delta.properties.defaults.enableDeletionVectors: "true"
  spark.sql.parquet.vorder.enabled: "true"
  spark.sql.shuffle.partitions: "16"
  spark.sql.adaptive.enabled: "true"
  spark.sql.adaptive.coalescePartitions.enabled: "true"
```

---

## Deployment Parameters

Each workspace has per-environment parameter files in `.deployment/`:

```
ws_{workspace}/.deployment/
├── parameters.dev.json
├── parameters.tst.json
├── parameters.stg.json
└── parameters.prd.json
```

Schema: `https://developer.microsoft.com/json-schemas/fabric/gitIntegration/deploymentRules/2.0.0/schema.json`

```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/deploymentRules/2.0.0/schema.json",
  "version": "2.0",
  "description": "<env> environment parameters — <domain>",
  "environment": "<Development|Test|Staging|Production>",
  "rules": [],
  "parameters": {
    "subscription_id": "<azure-subscription-id>",
    "resource_group": "rg-skpedm-{env}-usw2-001",
    "sql_server_primary": "Prod-azsql-03"
  },
  "notebookParameters": {
    "source_server": "Prod-azsql-03",
    "target_lakehouse": "lh_{domain}_brz"
  }
}
```

---

## Checklist for New Artifacts

- [ ] Folder name matches `.platform` `displayName` exactly (e.g. `nb_ing_loanetl_brz.Notebook/`)
- [ ] `.platform` has a unique `logicalId` (generate a new UUID)
- [ ] Lakehouse has all four required files (`.platform`, `lakehouse.metadata.json`, `alm.settings.json`, `shortcuts.metadata.json`)
- [ ] Notebook `kernel_info.name` is `"synapse_pyspark"`
- [ ] Notebook has a `# PARAMETERS CELL` block for runtime overrides
- [ ] Pipeline activities use `DependsOn` to enforce Bronze → Silver → Gold order
- [ ] Deployment parameter files exist for all four environments
- [ ] New artifact is added to the workspace `Readme.md` items table
- [ ] New artifact is added to the root `README.md` Workspace Items table
