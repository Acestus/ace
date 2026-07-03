---
LINEAR: ACE-32
title: Michigan Trip — Vacation Info Site (Acestus.com, Static Web App)
team: Acestus
state: Backlog
flow: queue
urgency: 5
importance: 4
due:
created: 2026-07-02
---

## Description

Build a static vacation-information page for a Michigan trip, modeled on the
disney2025.bluegreen.love/presentation.html reference site.

### Ask / Specs

- **Purpose:** Informational vacation page (itinerary, highlights, photos) for a
  Michigan trip — similar structure/content style to
  https://www.disney2025.bluegreen.love/presentation.html.
- **Domain:** Acestus.com (root domain). DNS is managed via Hover. Open to either
  Hover-side CNAME/ALIAS routing to the SWA default hostname, or Azure-managed
  custom domain validation (Azure issues the TXT/CNAME challenge).
- **Hosting:** Azure Static Web App, **Free SKU** only.
- **Reference architecture:** Mirror the `acewatch` repo pattern
  (github.com/Acestus/acewatch):
  - Vite + TypeScript static frontend (no backend/API needed — this site is
    purely informational, no dynamic data).
  - Bicep IaC in `infra/`, targeting a single `Microsoft.Web/staticSites`
    resource, SKU=Free, dev/stg/prd param files.
  - GitHub Actions deploy workflow using OIDC `azure/login` +
    `Azure/static-web-apps-deploy@v1`, no long-lived secrets.
- **Content:** Static content only — no CMS, no forms, no server-side logic.
- **Out of scope:** Azure Functions API, Storage account, Table Storage,
  Application Insights (not needed without a backend).

### Acceptance Criteria

- [ ] Site renders vacation info content at the SWA default hostname.
- [ ] Acestus.com resolves to the SWA (custom domain validated, HTTPS working).
- [ ] Bicep deploys cleanly to Free SKU SWA with no errors.
- [ ] GitHub Actions workflow deploys on push/dispatch via OIDC.
- [ ] No hardcoded secrets; deployment token pulled via az CLI at deploy time.

## Actions

### 2026-07-02

WORKLOG: Stub created from Linear ACE-32. Reviewed acewatch repo architecture
(Vite+TS frontend, Bicep IaC, OIDC GitHub Actions deploy) as the reference
pattern, minus the Functions API/Storage backend since this site has no
dynamic data.

## Follow-up

Status: Backlog
TODO:
- [x] Create Linear issue
- [ ] Draft implementation plan
- [ ] Scaffold Vite + TypeScript site
- [ ] Write Bicep IaC (SWA Free SKU)
- [ ] Write GitHub Actions OIDC deploy workflow
- [ ] Configure custom domain (Acestus.com via Hover)
