# Ace CRM Platform — Architecture Notes

Status: Azure resources exist (`rg-crm-dev`); now runs **locally** by
default for day-to-day use (see "Local-first run mode" below). SWA
deployment is separate/optional and not the primary way this gets used.

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

- **Azure provisioning.** Done: `rg-crm-dev` exists with a Function App
  (`func-crm-dev-scus-001`), Table Storage account for CRM data
  (`stcrmdevscus001`) and one for Functions runtime bookkeeping
  (`stcrmdevfuncscus001`). SWA has not been created/verified since the
  decision (2026-07-14) was to run locally day-to-day instead.
- **Local Table Storage testing via Azurite.** Done (2026-07-14) — see
  "Local-first run mode" below. `TableStorageCrmRepository` is now
  exercised against the real `stcrmdevscus001` account (not just Azurite;
  Azurite only backs the Functions runtime's own bookkeeping storage).
- **SQLite → Blob Storage backup cron job.** Straightforward once the storage
  account exists; not yet wired.
- **Auth.** `staticwebapp.config.json` currently requires `authenticated` for
  `/api/*` using SWA's built-in auth default provider; Azure AD app
  registration/tenant restriction not yet configured. Not relevant to local
  run mode (no SWA involved there), only if/when the SWA deployment is used.
- **CI wiring.** New projects are not yet included in `trunk-gates` or GitHub
  Actions workflows. `.github/workflows/deploy-crm.yaml` still targets
  `dotnet-version: '8.0.x'` and should be bumped to `10.0.x` to match
  `Ace.Crm.Api.csproj` (now `net10.0`) if/when SWA+Function App deployment is
  revisited.

## Local-first run mode (2026-07-14)

Decided to run the CRM **locally** day-to-day rather than deployed: no
public Function App, no public SWA, browser hits `localhost` only. Data
still lives in the real Azure Table Storage account (`stcrmdevscus001`,
`rg-crm-dev`) so it's durable and not re-seeded/lost between machines, but
that storage account has `allowBlobPublicAccess: false` and is not
internet-facing for unauthenticated access — the local Functions host
authenticates as your own AAD identity (`DefaultAzureCredential`, i.e.
whatever `az login` session is active) via the existing `Storage Table Data
Contributor` role assignment. No account keys are stored on disk.

What changed to make this work:

- `Ace.Crm.Api.csproj` bumped from `net8.0` → `net10.0` (only .NET 10 SDK
  was installed locally; also matches the rest of the workspace's
  convention and `Ace.Crm.Data`'s existing `net8.0;net10.0` multi-target).
- `local.settings.json` now sets `AceCrmTableStorageAccountName` (managed
  identity / AAD path in `Program.cs`) instead of a Table Storage
  connection string, and adds `Host.CORS` scoped to
  `http://localhost:8080` (where the static frontend is served from) so the
  Functions host only accepts browser requests from the local dev server.
  `AzureWebJobsStorage` stays `UseDevelopmentStorage=true` (Azurite) since
  that's just the Functions runtime's own bookkeeping storage, unrelated to
  CRM data.
- `web/wwwroot/js/apiClient.js`'s `API_BASE` now defaults to
  `http://localhost:7071/api` instead of the (never-deployed) production
  Function App URL, overridable via `window.ACE_CRM_API_BASE` if a page
  needs to point elsewhere.
- Added `scripts/crm-local.sh` — starts Azurite + `func start` (real Table
  Storage via your `az login`) + a plain `python3 -m http.server` for
  `web/wwwroot`, all with one command. `./scripts/crm-local.sh stop` tears
  everything down.

### Running it

```bash
az login   # if not already
./scripts/crm-local.sh
# UI:  http://localhost:8080/crm.html
# API: http://localhost:7071/api
./scripts/crm-local.sh stop
```

Requires: `az` CLI logged in with `Storage Table Data Contributor` on
`stcrmdevscus001` (already granted to the primary AAD user), `azurite`
(`npm i -g azurite`), Azure Functions Core Tools (`func`), .NET 10 SDK.

### Verified working end-to-end (2026-07-14)

- `func start` boots cleanly on net10.0 with all 8 HTTP-triggered functions
  registered.
- `GET /api/companies` returns real rows from `stcrmdevscus001` via AAD auth
  (no keys involved).
- `POST /api/companies` writes successfully; verified via
  `az storage entity query`/`delete` against the same table.
- CORS correctly scoped: preflight + actual requests from
  `Origin: http://localhost:8080` succeed; other origins would be rejected
  by the Functions host's CORS config.
- Static frontend (`crm.html` + `js/apiClient.js`) served locally on :8080
  talks to the local API on :7071 with no code changes needed beyond the
  `API_BASE` default above.

### Future work

- [ ] Consider a `Makefile` or `justfile` wrapper if `scripts/crm-local.sh`
      gets more options (seed data reset, tail logs, etc.) rather than
      growing flags on the bash script indefinitely.
- [ ] `crm.js`/`crm.html` only expose company create + company/contact list
      right now — no contact creation UI, no interaction UI, even though the
      API supports both. Worth building out the rest of the vanilla-JS UI
      to match the API surface.
- [ ] Decide whether the SWA + public Function App deployment path
      (`infra/crm/main.bicep`, `.github/workflows/deploy-crm.yaml`) stays as
      a documented-but-unused option, or gets removed/archived now that
      local-first is the primary mode. Currently left in place but not
      re-verified against the `net10.0` bump — if it's ever used again,
      confirm the Bicep's `functionAppConfig.runtime.version` and the
      workflow's `dotnet-version` both say `10.0`, not `8.0`.
- [ ] No auth at all on the local Functions host beyond CORS + it only
      listening on localhost. Fine for single-user local use; revisit if
      this ever needs to be reachable by more than one person on a LAN.
