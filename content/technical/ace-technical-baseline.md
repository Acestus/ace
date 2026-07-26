---
title: Ace Technical Baseline
date: 2026-07-19
description: The first polished technical page in Ace.
draft: false
---

Ace treats Markdown as the source of truth and generated assets as build outputs.

The page layout is intentionally direct:

1. State the goal.
2. Show the exact commands.
3. Add the diagram that clarifies the boundary.
4. End with the follow-up work.

## Build path

```bash
./scripts/build-site.sh
```

That script renders PlantUML, bundles the browser script, and then builds Hugo.

## Site flow

{{< diagram src="/diagrams/ace-architecture.svg" alt="Ace architecture from Markdown to Hugo to deployable static assets" caption="Ace renders diagrams before Hugo copies the static assets into the publish directory." >}}

## Notes

- Markdown files stay small and explicit.
- Generated SVGs live under `static/diagrams/` as build outputs.
- The browser bundle only activates when a page needs progressive enhancement.

## Follow-up

- Complete the remaining backend and Azure tickets once the owner supplies the missing environment details.
