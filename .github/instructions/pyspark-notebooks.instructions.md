# PySpark Notebook Authoring Instructions

Guidelines for writing Fabric PySpark notebooks in this repository, derived from the patterns in `ws_loanetl`.

---

## File Format

Every notebook is a single Python file named `notebook-content.py` inside a `{name}.Notebook/` directory. The format is plain Python with special comment blocks that Fabric parses.

```
nb_{prefix}_{domain}_{desc}.Notebook/
├── .platform
└── notebook-content.py
```

---

## Required Cell Structure

### 1. File header (always first line)
```python
# Fabric notebook source
```

### 2. Notebook-level METADATA block
```python
# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "<lakehouse-guid>",
# META       "default_lakehouse_name": "lh_{domain}_{layer}",
# META       "default_lakehouse_workspace_id": "<workspace-guid>",
# META       "known_lakehouses": [
# META         { "id": "<lakehouse-guid>" }
# META       ]
# META     }
# META   }
# META }
```

### 3. PARAMETERS CELL (pipeline-injectable values)
```python
# PARAMETERS CELL ********************

etl_process_date = ""   # YYYY-MM-DD; blank = resolved from ETL control table

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
```

Parameters cells use `# PARAMETERS CELL ********************` instead of `# CELL ********************`. Pipeline activities override these at runtime.

### 4. Code cells
```python
# CELL ********************

# your code here

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
```

Every cell — including parameters cells — must be followed by a METADATA block with `"language": "python"` and `"language_group": "synapse_pyspark"`.

---

## Cell 1: Docstring + Imports

The first code cell contains the notebook docstring and all imports. No logic here.

```python
# CELL ********************

"""
nb_{prefix}_{domain}_{desc} — <Short title>
============================================
<What this notebook does. What source it reads. What target it writes.
Which stored procedures or legacy jobs it replaces, if any.>

Medallion Layer: <BRONZE | SILVER | GOLD>
"""

from pyspark.sql import SparkSession, DataFrame, Window
from pyspark.sql.functions import (
    col, current_timestamp, lit, when, coalesce, date_sub,
    row_number, to_date, trim, upper, sha2, concat_ws
)
from pyspark.sql.types import DateType, DecimalType, StringType
from datetime import datetime, date, timedelta
```

Only import what is used. Do not import `SparkSession` if `spark` is already available in the Fabric runtime (it always is — only import it for local compatibility).

---

## Notebook Types and Patterns

### Ingestion (`nb_ing_`) — Source → Bronze

**Purpose:** Extract from external source, land as-is in Bronze Lakehouse with audit columns. Full-fidelity, no business logic.

**Write pattern:**
```python
def write_bronze(df, table_name: str, mode: str = "append"):
    (
        df.write
        .format("delta")
        .mode(mode)
        .option("mergeSchema", "true")   # absorb schema evolution
        .saveAsTable(table_name)
    )
    print(f"  ✓ {table_name}: {spark.table(table_name).count():,} rows ({mode})")
```

**Audit columns — always add before writing:**
```python
df = (
    df
    .withColumn("_brz_load_ts", current_timestamp())
    .withColumn("_brz_source_table", lit(f"{database}.{schema}.{table}"))
)
```

**JDBC read:**
```python
df = (
    spark.read
    .format("jdbc")
    .option("url", source_jdbc_url)
    .option("dbtable", f"(SELECT * FROM {database}.{schema}.{table}) AS t")
    .option("user", source_jdbc_user)
    .option("password", source_jdbc_password)
    .option("driver", "com.microsoft.sqlserver.jdbc.SQLServerDriver")
    .load()
)
```

**Rules:**
- Table names: `azsql_{source_table}_raw`
- No type casting, no filtering, no joins in Bronze
- `mergeSchema=true` by default (schema evolution strategy: `"absorb"`)
- Credentials come from parameters cell (`source_jdbc_password`), backed by Key Vault at runtime

---

### Transformation Bronze → Silver (`nb_tfm_{domain}_brz_slv`)

**Purpose:** Cleanse, type-cast, apply business logic. Produce clean, conformed tables.

**Write pattern — standard (idempotent with `replaceWhere` + Liquid Clustering):**
```python
# Liquid Clustering via SQL DDL (.clusterBy() requires Spark 4+)
if etl_process_date:
    # Incremental: table already clustered from initial creation
    df_clean.write.format("delta").mode("overwrite") \
        .option("replaceWhere", f"Record_Date = '{etl_process_date}'") \
        .saveAsTable("loanetl_{entity}_clean")
else:
    # Full overwrite: CREATE OR REPLACE preserves clustering
    df_clean.createOrReplaceTempView("_tmp")
    spark.sql("""
        CREATE OR REPLACE TABLE loanetl_{entity}_clean
        USING DELTA CLUSTER BY (Record_Date)
        AS SELECT * FROM _tmp
    """)
    spark.catalog.dropTempView("_tmp")
print(f"  ✓ loanetl_{entity}_clean: {spark.table('loanetl_{entity}_clean').count():,} rows")
```

**Audit column:**
```python
df = df.withColumn("_slv_processed_ts", current_timestamp())
```

**Table names:** `loanetl_{entity}_clean`

**SCD Type 2 pattern** (for history tables like `loanetl_history_bankruptcy_clean`):
```python
END_OF_TIME_DATE = "9999-12-31"
NULL_SENTINEL = "__NULL__"

# 1. Load current active segments from target
df_current = spark.table("loanetl_{entity}_clean").filter(
    col("Effective_Thru_Date") == lit(END_OF_TIME_DATE).cast(DateType())
)

# 2. Load today's staging records
df_staging = spark.table(f"{bronze_lakehouse}.azsql_{source}_raw").filter(
    col("Record_Date") == lit(etl_date).cast(DateType())
)

# 3. Detect new or changed records (coalesce nulls to sentinel for comparison)
change_condition = col("SRC.Key_Col").isNull()  # new record
for c in change_columns:
    change_condition = change_condition | (
        coalesce(col(f"TGT.{c}"), lit(NULL_SENTINEL)) !=
        coalesce(col(f"SRC.{c}"), lit(NULL_SENTINEL))
    )

df_changed = (
    df_staging.alias("TGT")
    .join(df_current.alias("SRC"), col("TGT.Key_Col") == col("SRC.Key_Col"), "left")
    .filter(change_condition)
)

# 4. New segments — open-ended (9999-12-31)
df_new_segments = (
    df_changed
    .withColumn("Effective_From_Date", lit(etl_date).cast(DateType()))
    .withColumn("Effective_Thru_Date", lit(END_OF_TIME_DATE).cast(DateType()))
    .withColumn("_slv_processed_ts", current_timestamp())
)

# 5. Close prior segments for changed records
df_closed = (
    df_current.alias("HB")
    .join(df_changed.filter(col("SRC.Key_Col").isNotNull())
          .select(col("TGT.Key_Col").alias("_changed")).distinct(),
          col("HB.Key_Col") == col("_changed"), "inner")
    .withColumn("Effective_Thru_Date", date_sub(lit(etl_date).cast(DateType()), 1))
    .drop("_changed")
    .withColumn("_slv_processed_ts", current_timestamp())
)

# 6. Carry forward unchanged segments
df_unchanged = (
    df_current.alias("HB")
    .join(df_changed.filter(col("SRC.Key_Col").isNotNull())
          .select(col("TGT.Key_Col").alias("_changed")).distinct(),
          col("HB.Key_Col") == col("_changed"), "left")
    .filter(col("_changed").isNull())
    .drop("_changed")
    .withColumn("_slv_processed_ts", current_timestamp())
)

# 7. Union and write
df_final = df_unchanged.unionByName(df_closed).unionByName(df_new_segments)

(
    df_final.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("loanetl_{entity}_clean")
)
```

**Rules:**
- Read Bronze using the `bronze_lakehouse` parameter: `spark.table(f"{bronze_lakehouse}.azsql_{table}_raw")`
- No JDBC reads in Silver — only Bronze Delta tables
- Wrap writes in `try/except` and re-raise so the pipeline fails visibly
- `replaceWhere` on the date partition makes re-runs safe

---

### Transformation Silver → Gold (`nb_tfm_{domain}_slv_gld`)

**Purpose:** Aggregate, join, curate for BI consumption. No source access.

**Write pattern:**
```python
_writer = (
    df_gold
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
)
if etl_process_date:
    _writer = _writer.option("replaceWhere", f"Record_Date = '{etl_process_date}'")
_writer.saveAsTable("fct_{entity}")
print(f"  ✓ fct_{entity}: {spark.table('fct_{entity}').count():,} rows")
```

**Audit column:**
```python
df = df.withColumn("_gld_published_ts", current_timestamp())
```

**Table naming:**
| Prefix | Use |
|--------|-----|
| `fct_` | Fact tables — event/transaction grain |
| `agg_` | Pre-aggregated summaries |
| `mart_` | Wide denormalized tables for specific BI use cases |

**Rules:**
- Read Silver using `silver_lakehouse` parameter: `spark.table(f"{silver_lakehouse}.loanetl_{entity}_clean")`
- Drop internal audit columns before writing: `.drop("_slv_processed_ts")`
- No business logic transformations — Silver is the last place for that

---

## Error Handling

Wrap every table write in `try/except`. Re-raise so the pipeline activity marks as failed.

```python
try:
    (
        df_final.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable("loanetl_{entity}_clean")
    )
    print(f"  ✓ loanetl_{{entity}}_clean: {spark.table('loanetl_{entity}_clean').count():,} rows")
except Exception as e:
    print(f"  ❌ loanetl_{{entity}}_clean write FAILED: {e}")
    raise
```

---

## Logging Standards

Use emoji prefixes consistently for log readability:

| Prefix | Meaning |
|--------|---------|
| `✓` | Step completed successfully |
| `❌` | Step failed |
| `⚠` | Warning / unexpected but non-fatal |
| `---` | Section header separator |
| `[SHIM]` | Local shim output (never in production code) |

```python
print("--- 1. Loading skip trace data ---")
print(f"  ✓ azsql_master_skip_trace_raw: {df.count():,} rows loaded")
print(f"  ⚠ Schema drift detected: +['New_Column']")
print(f"  ❌ Write failed: {e}")
```

---

## Parameters and Lakehouse References

Always reference lakehouses by parameter, never hardcoded:

```python
# PARAMETERS CELL ********************
bronze_lakehouse = "lh_loanetl_brz"   # overridden locally to "brz" for testing
silver_lakehouse = "lh_loanetl_slv"   # overridden locally to "slv" for testing
etl_process_date = ""
```

Read pattern:
```python
df = spark.table(f"{bronze_lakehouse}.azsql_{table}_raw")
df = spark.table(f"{silver_lakehouse}.loanetl_{entity}_clean")
```

---

## Sub-Notebook Calls

Use `notebookutils.notebook.run()` to invoke utility notebooks:

```python
notebookutils.notebook.run(
    "nb_util_loanetl_mockdata",
    timeout_seconds=300,
    arguments={"demo_date": etl_process_date, "num_customers": 50}
)
notebookutils.notebook.exit("DEMO_MODE")
```

The local `fabric_shim` mocks `notebookutils` so these calls work during local testing without modification.

---

## PII Handling

Never store PII (SSN, account numbers) in plaintext. Use SHA-512 hashing:

```python
from pyspark.sql.functions import sha2, concat_ws

df = df.withColumn(
    "SSN_Hash",
    sha2(concat_ws("|", col("SSN"), lit("loanetl_salt")), 512)
).drop("SSN")
```

Never log PII values — do not include PII columns in `print()` statements or sample row output.

---

## Local Testing

Run any notebook locally against Delta tables without deploying to Fabric:

```bash
python local/run_pipeline.py --notebook brz_slv --verbose
python local/run_pipeline.py --notebook slv_gld
python local/run_pipeline.py --debug-joins   # instrument joins with row counts
```

See the "Testing PySpark Locally" section in the root `README.md` for full details.

---

## Checklist for New Notebooks

- [ ] File starts with `# Fabric notebook source`
- [ ] Notebook-level METADATA block sets `kernel_info.name` to `"synapse_pyspark"`
- [ ] PARAMETERS CELL present with all pipeline-injectable values
- [ ] Every cell (including parameters) ends with a METADATA block
- [ ] First code cell has docstring stating purpose and medallion layer
- [ ] Lakehouse names referenced via parameters, not hardcoded
- [ ] Audit column added (`_brz_load_ts`, `_slv_processed_ts`, or `_gld_published_ts`)
- [ ] Writes wrapped in `try/except` with re-raise
- [ ] `replaceWhere` used for idempotent Silver/Gold date-partition writes
- [ ] No PII in logs or plaintext storage
- [ ] Notebook added to `NOTEBOOKS` dict in `local/run_pipeline.py` for local testing
- [ ] Notebook added to the Workspace Items table in `README.md`
