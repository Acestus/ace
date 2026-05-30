# Copilot Instructions

## Shell Commands

- Never combine `cd` with other commands using `&&` or `;`
- Always issue `cd` as its own separate bash call before running commands in that directory
- Use `shellId` (async mode) to maintain directory state across calls when needed
