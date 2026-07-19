# Ace Repository Architecture

This repository is organized as a .NET-first workflow toolkit with thin-collar skills, local state, and trunk-based CI gates.

## Top-Level Layout

| Path | Purpose |
| --- | --- |
| `content/` | Hugo content sections for the Ace knowledge site |
| `layouts/` | Hugo templates for the site shell |
| `archetypes/` | Hugo starter files for `hugo new` |
| `assets/plantuml/` | PlantUML sources and generated-file staging |
| `web/` | Bun workspace for TypeScript/front-end assets |
| `src/Ace.Tools.Cli/` | Primary .NET CLI for rounds, Linear, GitHub, and workflow operations |
| `tests/Quality.Reqnroll.Score.Tests/` | Reqnroll/xUnit scoring tests for inner-loop and outer-loop quality signals |
| `scripts/Ace.Quality.Gates/` | C# orchestration for preflight/postflight/promote/deploy gate commands |
| `.github/workflows/` | Trunk workflows (`preflight`, `postflight`, `promote`) using `.yaml` |
| `.github/skills/` | Thin-collar Copilot skills routing to CLI/C# command surfaces |
| `.github/instructions/` | Repository coding and workflow conventions |
| `docs/testing/` | Generated quality score reports (`inner-loop-score`, `outer-loop-gherkin-score`) |
| `issues/` | Markdown issue stubs and worklog records |

## Testing Architecture

### Inner loop

- Scope: non-Gherkin unit/integration tests (`*Tests.cs`) excluding acceptance artifacts.
- Command:
  `dotnet test tests/Quality.Reqnroll.Score.Tests/Quality.Reqnroll.Score.Tests.csproj --filter "TestCategory=inner-loop-score|Category=inner-loop-score"`
- Output artifacts:
  - `docs/testing/inner-loop-score.md`
  - `docs/testing/inner-loop-score.json`

### Outer loop

- Scope: executable `*.feature` files (Reqnroll behavior contracts).
- Command:
  `dotnet test tests/Quality.Reqnroll.Score.Tests/Quality.Reqnroll.Score.Tests.csproj --filter "TestCategory=outer-loop-gherkin-score|Category=outer-loop-gherkin-score"`
- Output artifacts:
  - `docs/testing/outer-loop-gherkin-score.md`
  - `docs/testing/outer-loop-gherkin-score.json`

## Trunk-Based Pipeline Design

Branch-to-environment mapping:

| Branch | Environment |
| --- | --- |
| `dev` | `dev` |
| `release/*` | `stg` |
| `main` | `prd` |

Workflows:

1. `preflight.yaml` (pull_request)
   - Runs C# preflight gate (fast checks + inner-loop scoring)
2. `postflight.yaml` (push)
   - Resolves environment from branch
   - Runs C# postflight gate (inner + outer loop scoring + build)
   - Publishes .NET app artifact per environment
3. `promote.yaml` (workflow_dispatch)
   - Runs promote gate for selected environment
   - Publishes .NET app artifact for promotion review

## Tool Baseline

The current scaffold assumes:

- `.NET SDK 10.0.301`
- `Hugo v0.164.0+extended`
- `Bun 1.3.14`

## C# Gate Script Contract

`scripts/Ace.Quality.Gates/Program.cs` provides:

- `preflight`
- `postflight`
- `promote --environment <dev|stg|prd>`
- `deploy-net-app --environment <dev|stg|prd>`

This keeps workflow logic thin and centralizes quality/deploy orchestration in .NET code.
