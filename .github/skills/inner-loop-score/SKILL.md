---
name: inner-loop-score
description: "Score non-Gherkin inner-loop tests and generate markdown/json reports. Use when the user asks to assess test quality, reduce acceptance-test overload, or trend test design quality."
argument-hint: "Say what to score (repo path/test project) and whether to regenerate the markdown report."
---

# Inner-Loop Score Skill

## Role

Evaluate inner-loop test quality (not acceptance Gherkin scenarios) and produce repeatable score artifacts.

## Scope

- Include: `*Tests.cs` inner-loop test files.
- Exclude: acceptance feature files, Reqnroll generated files, and acceptance-focused test classes.

## Command Surface

```bash
dotnet test tests/Quality.Reqnroll.Score.Tests/Quality.Reqnroll.Score.Tests.csproj \
  --filter "TestCategory=inner-loop-score|Category=inner-loop-score"
```

## Operating Contract

1. Keep Gherkin acceptance coverage separate from this score.
2. Use this score for trend and refactoring priority, not pass/fail gating by itself.
3. Re-run after major test refactors and attach markdown results to planning or review updates.
4. Use this as trend telemetry and refactoring guidance, not a hard gate by itself.
