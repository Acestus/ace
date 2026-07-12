# Ace CRM — Azure Table Storage Design

Status: current. Replaces the earlier Azure SQL design
(`db/migrations/001_init_crm.sql`, removed) after switching to Table Storage
for cost reasons at 1-12 user scale (~$1-2/month vs. ~$20-45/month for Azure
SQL Serverless).

Table Storage is schemaless — there is no migration to run. Tables are
created on first use (`TableClient.CreateIfNotExistsAsync`, called from
`TableStorageCrmRepository`). This document is the source of truth for the
partition/row key strategy instead of a `.sql` file.

## What was traded away vs. Azure SQL

- No foreign keys, no `CHECK` constraints, no server-enforced uniqueness
  beyond `(PartitionKey, RowKey)`. All of that logic now lives in
  `Ace.Crm.Data/ContactValidation.cs` and `TableStorageCrmRepository`
  (e.g., duplicate company name check, "contact must exist before logging an
  interaction against it" check) — enforced in application code, not the
  store.
- No cross-partition transactions. Table Storage batch transactions only
  work within a single partition. There is a small window between
  "check contact exists" and "insert interaction" in
  `CreateInteractionAsync` that is not atomic. Acceptable at this scale
  (low write concurrency); revisit if that changes.
- No ad-hoc querying/joins. Every query pattern had to be designed into the
  partition key up front (see below). Anything not covered by a designed key
  becomes a slower cross-partition/table scan.

## What was gained

- Storage-tier pricing only — no compute to size, pause, or resume.
- Built-in optimistic concurrency via `ETag` and a free `Timestamp` per
  entity — no hand-rolled `ROWVERSION` column needed.
- Zero schema migrations to manage.

## Tables and key strategy

Key derivation lives in `Ace.Crm.Data/TableKeys.cs` as pure functions —
unit tested independently of the Azure SDK. Summary:

### `Companies`

| | |
|---|---|
| PartitionKey | constant `"company"` |
| RowKey | company id (generated) |

All companies share one partition. At the target scale (a handful to a few
hundred companies for a 1-12 person shop) this keeps "list all companies"
a single fast partition query instead of an expensive cross-partition scan.

### `Contacts`

| | |
|---|---|
| PartitionKey | `CompanyId`, or `"unassigned"` if the contact has no company |
| RowKey | contact id (generated) |

Optimizes the dominant query: "contacts for a given company"
(`ListContactsAsync(companyId)`) — a single partition query. "List all
contacts" (no company filter) falls back to a full-table scan; acceptable at
this scale, revisit with a secondary lookup table if contact volume grows
into the thousands.

`GetContactAsync(id)` (by id, company unknown) similarly requires a
cross-partition scan filtered by `RowKey == id`, since the partition key
depends on `CompanyId`. Same acceptable-at-this-scale tradeoff.

### `Interactions`

| | |
|---|---|
| PartitionKey | `ContactId` |
| RowKey | `{invertedTicks:D19}_{interactionId}` — see below |

Optimizes the dominant query: "interactions for a contact, most recent
first" (`ListInteractionsForContactAsync`) — a single partition query with
no client-side sort needed, because Table Storage returns rows in RowKey
ascending order and the RowKey is built from
`DateTime.MaxValue.Ticks - occurredAt.Ticks`, so the row with the latest
`OccurredAt` sorts first. The interaction id is appended to keep row keys
unique when two interactions share the same `OccurredAt` tick value.

## Consistency/validation invariants enforced in code, not storage

See `Ace.Crm.Data/ContactValidation.cs` for the rules themselves. Enforced
in `TableStorageCrmRepository`:

- Company names must be unique (case-insensitive) — checked via a query
  against the single `"company"` partition before insert.
- An interaction's `ContactId` must reference an existing contact — checked
  via `GetContactAsync` before insert.
- Interaction type must be one of the allowed set (`ContactValidation`).
- Follow-up date must be after the interaction date (`ContactValidation`).

## Local development

Point `AceCrmTableStorageConnectionString` at the Azurite emulator
(`UseDevelopmentStorage=true`, see `src/Ace.Crm.Api/local.settings.json`) or
a real storage account connection string. `Ace.Crm.Data.Tests` and
`Ace.Crm.Acceptance.Tests` do not need Table Storage or Azurite at all — they
run against `InMemoryCrmRepository`, which implements the same
`ICrmRepository` interface.
