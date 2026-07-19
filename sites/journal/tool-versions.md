# Tool Versions

This repository keeps the scaffold simple and pins the local toolchain in docs so later CI and deployment tickets can refer to a single place.

## Current baseline

| Tool | Version | Notes |
|---|---|---|
| .NET SDK | `10.0.301` | Used by the repository CLI, the CRM API, and the tests |
| Hugo | `v0.164.0+extended` | Builds the Journal site scaffold into `public` |
| Bun | `1.3.14` | Package manager for the `web/` workspace |

## Update rule

When any of these versions change, update this file and keep the repo README in sync with the new baseline.
