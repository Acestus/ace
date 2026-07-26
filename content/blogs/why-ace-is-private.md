---
title: Why Ace Is Private
date: 2026-07-19
description: A short explanation of the design choice behind the private knowledge site.
draft: false
---

Ace is private because the best notes are the ones that can stay blunt.

The site is meant to hold implementation plans, rough ideas, and the kind of technical context that is easier to use when it does not have to be polished for an audience. That means the writing can be direct, the diagrams can stay local, and the pages can include exact resource names without turning into marketing copy.

The boundary is simple:

- Markdown is the source of truth.
- Hugo turns the Markdown into the site.
- Generated assets are built before publish time.
- Anything secret stays out of the page body.
