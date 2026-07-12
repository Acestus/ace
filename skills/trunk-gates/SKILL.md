---
name: trunk-gates
description: "Run trunk-based preflight/postflight/promote quality gates for the ace repo using C# gate scripts and .NET workflows."
argument-hint: "Say which gate to run: preflight, postflight, or promote <dev|stg|prd>."
---

# Trunk Gates Skill

## Role

This skill is a thin collar over trunk gate commands used by GitHub Actions and local validation.

## Command Surface

- `dotnet run --project scripts/Ace.Quality.Gates/Ace.Quality.Gates.csproj -- preflight`
- `dotnet run --project scripts/Ace.Quality.Gates/Ace.Quality.Gates.csproj -- postflight`
- `dotnet run --project scripts/Ace.Quality.Gates/Ace.Quality.Gates.csproj -- promote --environment dev`
- `dotnet run --project scripts/Ace.Quality.Gates/Ace.Quality.Gates.csproj -- promote --environment stg`
- `dotnet run --project scripts/Ace.Quality.Gates/Ace.Quality.Gates.csproj -- promote --environment prd`

## Operating Contract

1. Keep quality gate orchestration in C# scripts.
2. Keep workflow logic thin and delegate execution to `Ace.Quality.Gates`.
3. Use preflight for PR validation and postflight/promote for broader gate coverage.
4. Keep this skill short and maintainable (<200 lines).
