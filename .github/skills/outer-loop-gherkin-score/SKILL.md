---
name: outer-loop-gherkin-score
description: "Score outer-loop Gherkin acceptance scenarios and generate markdown/json reports."
argument-hint: "Provide repo root and whether to refresh the score artifacts."
---

# Outer-Loop Gherkin Score Skill

## Role

Evaluate Gherkin acceptance files as outer-loop behavior contracts and produce report artifacts.

## Scope

- Include: `**/*.feature`
- Exclude: generated files under `.git`, binary artifacts.

## Command Surface

```bash
dotnet test tests/Quality.Reqnroll.Score.Tests/Quality.Reqnroll.Score.Tests.csproj \
  --filter "TestCategory=outer-loop-gherkin-score|Category=outer-loop-gherkin-score"
```

## Operating Contract

1. Keep this score focused on executable Gherkin quality.
2. Pair this with inner-loop scoring for full test design visibility.
3. Use trend and coaching signals, not hard merge gating.
4. Use trend and coaching signals, not hard merge gating.
