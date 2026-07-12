# Ace CRM Platform — Architecture Notes

Status: scaffolded, not yet deployed to Azure.

## Decisions

- **Database:** Azure Table Storage (not Azure SQL). Originally scaffolded
  against Azure SQL Serverless (~$20-45/mo realistic estimate at this scale);
  switched to Table Storage for cost (~$1-2/mo — pure pay-per-transaction,
  no compute to pause/resume) once actual usage scale (1-12 people, casual
  CRUD) made SQL's relational features (FKs, joins, ad-hoc queries) not worth
  their cost premium. See `db/table-storage-design.md` for the partition/row
  key strategy and what was traded away (no FKs, no cross-partition
  transactions, no ad-hoc queries — all query patterns had to be designed
  into keys up front). `ICrmRepository` isolates this choice; swapping back
  to a relational store later means writing one new implementation, not
  touching the API layer, tests, or front end.
- **API:** Azure Functions, isolated worker model (`src/Ace.Crm.Api`), HTTP
  triggers only for now (companies, contacts, interactions).
- **Front end:** Azure Static Web App serving a vanilla, modular JS front end
  (`web/wwwroot`) — no framework, no build step. `js/apiClient.js` is the only
  module that knows about `/api/*`; page scripts (`crm.js`, `main.js`) just
  consume it.
- **CRM:** Built in-house rather than adopting a third-party open-source CRM.
  The .NET open-source CRM ecosystem has no actively-maintained option that
  targets Azure Functions + SWA, and the actual CRM surface needed here
  (companies, contacts, interactions, follow-ups) is small enough that
  building it directly on `src/Ace.Crm.Data` is less work than integrating and
  reskinning an existing product.
- **Local SQLite stays local-first.** `Ace.Tools.Cli`'s `~/.acestus/workflow.db`
  and `~/.ace/rounds.db` remain per-machine, single-user state (already STRICT
  tables). They are not the multi-user CRM store — SQLite doesn't handle
  concurrent multi-machine writers safely. The plan is local SQLite → backup
  snapshot to Azure Blob Storage (disaster recovery), while shared CRM data
  lives in Azure SQL behind the Functions API.

## Conventions inherited from `Ace.Tools.Cli` (the reference precedent)

This CRM was architected by treating `src/Ace.Tools.Cli` as the existing
reference implementation in this repo, not as a green-field design. Concrete
conventions carried over:

- **Model style split:** persisted/database-mapped entities (`Company`,
  `Contact`, `Interaction` in `Ace.Crm.Data/Models.cs`) are **mutable classes**
  with `{ get; set; }`, matching `Ace.Tools.Cli/Models.cs` (`Ticket`,
  `WorkLog`, `CrmContact`, etc.) — this is what Dapper's default mapper binds
  to naturally. Transient/computed types (request DTOs, validation results,
  command results) are `record`s, matching `Ace.Tools.Cli`'s own split (see
  `WorkflowOperations.cs`'s `StartMyDayResult`/`DispatchResult` vs. its
  `Models.cs` classes). Do not use records for anything Dapper maps directly
  from a table row in this repo.
- **Project naming:** `Ace.<Domain>.<Layer>` (`Ace.Crm.Data`, `Ace.Crm.Api`),
  matching `Ace.Tools.Cli`'s `Ace.<Purpose>` pattern.
- **Flat file-per-concern layout**, no nested folders under `src/<Project>/`,
  matching `Ace.Tools.Cli`'s layout.
- **csproj shape:** `net10.0`, `ImplicitUsings enable`, `Nullable enable`,
  Dapper for data access — copied verbatim from `Ace.Tools.Cli.csproj`.
- **`.slnx` solution format** (not legacy `.sln`) — extended the existing
  `Ace.Tools.slnx` rather than creating a second solution file.
- **STRICT SQLite / typed-SQL discipline** carries the same spirit as the
  local `schema.sql` STRICT-table conversion: real constraints, no loose
  typing, explicit mapping notes when a store-specific type doesn't exist
  1:1 (there it was `TIMESTAMP`→`TEXT`/`BOOLEAN`→`INTEGER` for SQLite STRICT;
  here it's `DATETIME2`/`CHAR(36)`/`CHECK` constraints for Azure SQL).

When extending this CRM (or building the next Azure-backed service in this
repo), check `Ace.Tools.Cli` first for an existing pattern before inventing
a new one.

## Project layout

```
src/Ace.Crm.Data/     Models, validation (pure functions), ICrmRepository,
                      TableStorageCrmRepository (Azure Table Storage),
                      TableKeys (pure partition/row key derivation),
                      InMemoryCrmRepository (used by Functions local dev +
                      acceptance tests)
src/Ace.Crm.Api/      Azure Functions isolated worker, HTTP triggers only
web/wwwroot/          Vanilla JS/modular SWA front end
db/table-storage-design.md   Partition/row key design (tables are schemaless;
                              no migrations to run)
tests/Ace.Crm.Data.Tests/         Inner-loop unit tests (Dave Farley index)
tests/Ace.Crm.Acceptance.Tests/   Reqnroll acceptance tests (Gherkin)
```

## Test quality scoring

Both new test projects were scored with the repo's existing
`Quality.Reqnroll.Score.Tests` engine (Dave Farley test-quality index:
U/M/R/A/N/G/F/T properties):

- `tests/Ace.Crm.Data.Tests` (24 validation/repository tests + 9 `TableKeys`
  partition-key tests) → **8.66/10 (Excellent)**
- `tests/Ace.Crm.Acceptance.Tests/Features/ContactManagement.feature` → **9.05/10 (Exemplary)**

Conventions that drove the score up (worth reusing on future test files):

- Test method names follow `Given_<context>_When_<action>_Then_<outcome>`.
- No `DateTime.UtcNow`/`Guid.NewGuid()` inside assertions — inject
  `TimeProvider` and an id factory instead, fix them in tests.
- No sleeps, no file/network I/O, no reflection-based mocking in unit tests.
- Gherkin scenarios avoid implementation vocabulary (no "database", "SQL",
  "table") and use `Rule:` grouping to cluster related scenarios.

Re-run scoring after changes:

```bash
dotnet test tests/Quality.Reqnroll.Score.Tests/Quality.Reqnroll.Score.Tests.csproj \
  --filter "Category=inner-loop-score|Category=outer-loop-gherkin-score"
```

## Not yet done (deliberately deferred)

- **Azure provisioning.** No resource group, storage account, Function App,
  or SWA has been created yet. This needs an explicit go-ahead on naming
  (`rg-ace-crm-dev` following the existing `rg-<project>-<env>` convention
  seen in the subscription) and region before running `az` commands that cost
  money.
- **Local Table Storage testing via Azurite.** Neither Azurite nor Docker was
  available in this environment, so `TableStorageCrmRepository` has been
  built and reviewed carefully but not exercised against a real (or emulated)
  table service yet — only its pure key-derivation logic (`TableKeys`) has
  test coverage. Run an Azurite-backed integration pass before first
  deployment.
- **SQLite → Blob Storage backup cron job.** Straightforward once the storage
  account exists; not yet wired.
- **Auth.** `staticwebapp.config.json` currently requires `authenticated` for
  `/api/*` using SWA's built-in auth default provider; Azure AD app
  registration/tenant restriction not yet configured.
- **CI wiring.** New projects are not yet included in `trunk-gates` or GitHub
  Actions workflows.
