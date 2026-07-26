# Technical Documentation Writer Spec

This guide tells agents how to write Ace technical pages.

## Goal

Produce pages that are useful to a human on the first read and reusable by an agent later.

## Required Inputs

- Exact resource names
- The current architecture boundary
- The intended audience
- The current command set
- Any dependencies or hard blockers

## Page Shape

1. Title
2. Short lede
3. Summary or scope
4. Commands or exact steps
5. Diagram, table, or callout when it clarifies the process
6. Follow-up actions

## Voice Rules

- Use active voice.
- Name the concrete Azure, GitHub, Hugo, or .NET resource.
- Avoid vague filler like “some”, “thing”, or “various”.
- Prefer one sentence that states the action and the reason.

## Naming Rules

- Write the full resource name on first mention.
- Use the environment or subscription name if it matters.
- Keep file names short and lowercase with hyphens.
- Match the page title to the actual subject.

## Diagram Guidance

- Use PlantUML when the page needs a workflow, boundary, or component map.
- Use a table for comparisons, settings, or inventories.
- Use commands for anything a human must run exactly.
- Use a callout or note for caveats, blockers, and follow-up work.

## Writing Checklist

- [ ] Page starts with a direct summary.
- [ ] Every named resource is exact.
- [ ] Commands are copy-pasteable.
- [ ] Diagrams explain something the text cannot.
- [ ] Follow-up work is explicit.
- [ ] No secret, token, or private transcript body appears in the page.

## Example

See [Ace technical baseline](/technical/ace-technical-baseline/).
