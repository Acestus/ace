# Contributing

This is a personal workflow toolkit shared as a reference. You're welcome to:

- **Fork it** and adapt it to your stack
- **Open issues** with bugs, suggestions, or questions
- **Send PRs** for fixes, new skills, or better docs

## Adding a Skill

1. Create `.github/skills/<name>/SKILL.md` with frontmatter:
   ```yaml
   ---
   name: skill-name
   description: 'When to use this skill...'
   argument-hint: 'What the user should provide'
   ---
   ```
2. Document the workflow phases (Capture → Validate → Act → Confirm).
3. Reference the scripts it composes with (`## Composes` section).

## Adding an Instruction

1. Create `.github/instructions/<name>.instructions.md`
2. Add the `applyTo` glob in frontmatter:
   ```yaml
   ---
   applyTo: "issues/**/*.md"
   ---
   ```
3. Keep rules focused on one file pattern.

## Adding a Script

- Python 3.10+ stdlib preferred (no extra deps unless needed)
- Use `argparse` for CLI args
- Read secrets from env vars, not files
- Print human-readable output with emoji status (`✓` / `❌` / `⚠`)
- Exit 0 on success, non-zero on failure

## Sanitization

Never commit:
- Real names, emails, or domain names
- Real Azure tenant/subscription IDs, resource group names
- Real Jira keys or Confluence page IDs (use placeholders)
- API tokens, connection strings, or webhook URLs

Run a sanity check before pushing:
```bash
grep -rn "<your-company-name>\|<your-domain>" .
```
