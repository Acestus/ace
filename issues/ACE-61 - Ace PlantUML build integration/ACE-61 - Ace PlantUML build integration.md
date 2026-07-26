---
LINEAR: ACE-61
title: Ace — PlantUML build integration
team: Acestus
state: Backlog
flow: queue
urgency: 3
due: 
created: 2026-07-19
---

## Description

Render PlantUML source into deployable SVG diagrams.

Deliverables: pinned PlantUML setup, CI rendering step, local render command, Hugo diagram shortcode, example architecture diagram, and generated-file policy documentation.

Acceptance: changed `.puml` files update rendered SVG during build, syntax errors fail the pipeline, Markdown can embed diagrams with alt text and captions, and no Java process runs in the deployed website.

## Actions

### 2026-07-19

WORKLOG: Added PlantUML render automation, shortcode support, a sample diagram source, and a repeatable build path.

## Follow-up

Status: Done
TODO:
- [x] Sync the local stub to Linear and close the issue.
