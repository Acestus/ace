---
LINEAR: ACE-40
title: Daily Gospel Reader — AWS Marketplace SaaS (Private, Gospel v1)
team: Acestus
state: Backlog
flow: queue
urgency: 3
due: 
created: 2026-07-03
---

## Description

## User Story

## User Story

As the developer experimenting with AWS Marketplace's AI Agents and Tools
category, I want to build and privately list a "Daily Gospel Reader" SaaS
product (Lambda + API Gateway) so that I can learn the AWS Marketplace SaaS
listing/subscription mechanics end-to-end — mirroring the same daily-Gospel
idea already explored on iOS (ACE-33), Android (ACE-34), OpenClaw (ACE-36),
and the GPT Store (ACE-38), this time on AWS.

## Acceptance Criteria

- [ ] A new standalone GitHub repo `catholic-daily-gospel-aws` exists,
      containing an AWS Lambda function (not Azure — this ticket uses AWS
      infrastructure end-to-end).
- [ ] The Lambda scrapes/parses [USCCB.org](<http://USCCB.org>) and returns today's Gospel
      citation + full text as JSON.
- [ ] If the Lambda's USCCB call fails (network issue, page format change,
      parse failure, etc.), it returns a clear error response rather than
      malformed data or an unhandled exception.
- [ ] An API Gateway endpoint (e.g. `GET /gospel`) fronts the Lambda,
      secured with an API key per the standard AWS Marketplace SaaS
      subscription model.
- [ ] The product is registered as a SaaS listing in AWS Marketplace Seller
      Central, but kept **private/unlisted** — not published for public
      discovery or subscription.
- [ ] Verified end-to-end: subscribing to the private listing yourself,
      calling the API Gateway endpoint with the issued API key, and
      receiving today's real Gospel text sourced from [USCCB.org](<http://USCCB.org>) (or a clear
      error if something fails).

## Out of Scope (v1)

* Public publication/listing on AWS Marketplace — private/unlisted only.
* First reading, responsorial psalm, second reading — Gospel only, matching
  ACE-36/38's scope.
* Bedrock Agents or any AWS-native "agent" framework — this is a simple
  Lambda + API Gateway SaaS API, not a Bedrock Agent.
* Sharing/reusing the Azure backends built for ACE-33/34/36/38 — this uses
  AWS infrastructure exclusively.
* Billing/metering configuration beyond whatever AWS Marketplace requires
  as a minimum to create a private listing.

## Implementation Plan

## Implementation Plan

Pattern: new standalone repo + AWS-native backend (parallels ACE-36/38's
approach, but on AWS instead of Azure), paired with AWS Marketplace Seller
Central for the private SaaS listing itself (no repo artifact — configured
in AWS's console). Fully independent of ACE-33/34/36/38 — no shared backend,
code, or cloud provider.

1. **Create the repo**
   * New GitHub repo `catholic-daily-gospel-aws`, containing the Lambda
     function source and IaC (e.g. AWS SAM or CDK — whichever is simplest
     for a single Lambda + API Gateway pair).
2. **Backend: USCCB Gospel scraper (AWS Lambda)**
   * Lambda function fetches USCCB's daily readings page for today's date,
     parses out only the Gospel citation + full text.
   * Returns JSON `{ date, citation, text }` on success.
   * Returns a distinct error response (e.g. 502 with
     `{ error: "parse_failed" }`) if the page can't be parsed, rather than
     an unhandled exception.
3. **API Gateway front door**
   * Provision an API Gateway REST or HTTP API with a single `GET /gospel`
     route, integrated with the Lambda.
   * Enable an API key requirement (usage plan) on the route — this is the
     standard AWS Marketplace SaaS metering/entitlement pattern.
   * Deploy via IaC + GitHub Actions (OIDC-based AWS auth, no long-lived
     access keys stored in the repo).
4. **AWS Marketplace SaaS listing (private)**
   * Register as a seller in AWS Marketplace Seller Central (if not already
     done).
   * Create a SaaS product listing pointing at the API Gateway endpoint,
     following AWS's SaaS metering/entitlement integration requirements.
   * Keep the listing private/unlisted — do not submit for public catalog
     review or publication.
5. **Verification**
   * Subscribe to your own private listing.
   * Use the issued API key to call the `GET /gospel` endpoint.
   * Confirm it returns today's real Gospel citation + text sourced from
     [USCCB.org](<http://USCCB.org>).
   * Force a failure path (e.g., temporarily break the USCCB parse target)
     and confirm the API returns the clear error response instead of
     malformed data.

## What Stays Untouched

* The `ace` repo — this is a fully separate project/repo.
* Any backend or code built for ACE-33 (iOS), ACE-34 (Android), ACE-36
  (OpenClaw), or ACE-38 (GPT Store) — this uses AWS exclusively, no sharing.
* No public AWS Marketplace publication, no Bedrock Agent framework, no
  readings beyond the Gospel.

## Actions

### 2026-07-03

WORKLOG: Stub created from Linear ACE-40

## Follow-up

Status: Backlog
TODO:
- [ ] Review and scope work