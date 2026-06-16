# Copilot Instructions

## Shell Commands

- Never combine `cd` with other commands using `&&` or `;`
- Always issue `cd` as its own separate bash call before running commands in that directory
- Use `shellId` (async mode) to maintain directory state across calls when needed
- **Pre-flight self-check:** Before issuing any bash command containing `cd`, mentally verify it does not also contain `&&` or `;`. If it does, split into two separate bash calls.
- Violations can be caught by the repo's shell command linting guidance.
