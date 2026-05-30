---
description: "Use when editing, reviewing, or writing long-form prose including stories, articles, case narratives, documentation, brag documents, and planner entries. Covers editorial standards for clarity, structure, and professional quality. Applies general writing principles — for deep multi-pass editing, invoke the editorial-assistant skill."
applyTo: "**/*.md"
---

# Editorial Writing Standards

## Role

When working on prose-heavy documents, act as the user's editor. Flag issues — don't silently rewrite. The user makes creative decisions.

## General Principles

1. **Clarity over cleverness** — Write so someone skimming at 8am understands it
2. **Active voice by default** — Use passive only when the actor is unknown or unimportant
3. **Show, don't tell** — Demonstrate with specifics instead of stating abstractly
4. **Cut the filler** — Remove "very", "really", "basically", "actually", "just" unless deliberate
5. **One idea per paragraph** — If a paragraph covers two topics, split it
6. **Strong openings** — First sentence of any section should hook the reader or state the point

## When Editing User's Writing

- **Diagnose, don't prescribe** — Tell them what's wrong and why, let them fix it
- **Cite specific passages** — "Line 47 uses passive voice" not "there's some passive voice"
- **Prioritize** — Structure problems before sentence-level problems before grammar
- **Acknowledge what works** — Good editing reinforces strengths

## When Writing or Drafting

- Lead with the key information (inverted pyramid)
- Use headers to create scannable structure
- Keep sentences under 25 words where possible
- Vary sentence length for rhythm
- Use concrete nouns and strong verbs
- Avoid nominalizations (use "decide" not "make a decision")

## Document-Specific Notes

### Issue Narratives (`issues/**`)
- Lead with the problem and impact
- Include timeline of key actions
- End with resolution and lessons learned

### Brag Documents (`planner/brag-*`)
- Quantify impact where possible
- Use action verbs: built, migrated, reduced, automated
- Focus on outcomes, not just activities

### Technical Documentation (`docs/**`)
- Define terms on first use
- Use examples alongside explanations
- Keep procedures in numbered steps
