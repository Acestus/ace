---
LINEAR: ACE-24
title: ISN Interview Prep
team: ACE
state: Backlog
flow: queue
urgency: 2
importance: 1
due: 2026-07-06
created: 2026-06-17
---

## Description

Consolidated prep plan for the ISN interview. All ISN interview prep work should live here rather than in separate Linear issues.

**Confirmed interview details:**
- Date/Time: July 6, 2026, 1:00–2:00 PM Central Time
- Interviewers: Ahlam Asad ([LinkedIn](https://www.linkedin.com/in/ahlam-asad-6383469/)), Nathan Crabb
- Format: Video call via Microsoft Teams — camera on, clean background, professional dress
- Recruiter: Isabel Crowe, Prestige Staffing

**Topics they plan to cover (per recruiter email):**
- Azure Subscriptions and certifications
- How to publish public-facing websites
- IIS
- Storage Accounts
- Scripting/Automating
- How you revision systems
- How you've used Copilot or Claude
- Elastic Search
- Anything on the resume — expect follow-up drilling until you hit "I don't know" (that's OK to say)

**Priority focus area:** freshen up on **IIS** specifically.

**Must-have answers prepared:**
- "Why do you want to work at ISN?"
- Insightful questions to ask them at the end

## Outcomes

- Be ready to explain William's fit for ISN clearly and concretely.
- Have a sharp company/role briefing, tailored narrative, STAR stories, technical examples, questions, and interview-day checklist in one place.
- Practice once before the interview and capture weak spots.

## Prep Checklist

### Company and role research
- [ ] Build a concise briefing on ISN: business model, customers, products/platform, industry position, recent news, likely pain points.
- [ ] Map William's background to the role.
- [ ] Produce 5 role-specific talking points.

### Core narrative and elevator pitch
- [ ] Draft a 60-second answer to “tell me about yourself.”
- [ ] Draft a 2-minute version for deeper context.
- [ ] Emphasize systems thinking, PowerShell/Azure/automation, AI triage, knowledge management, service ownership, and measurable outcomes.
- [x] Draft an answer to “why do you want to work at ISN?”

**Why do you want to work at ISN?**
"I look for problems that are actually hard, not busywork — and cloud engineering is where I get to combine systems thinking with real stakes: identity, access, reliability, at scale. ISN's problem space fits that. You're not just running software — you're managing risk and compliance data (safety, insurance, cybersecurity, ESG) across 850+ hiring clients and 85,000 contractors in 85+ countries. Keeping access, data integrity, and reliability solid at that scale, where the real-world stakes are people's safety and companies' risk exposure — that's a genuinely hard systems problem, and it's the kind of work I want to be doing."

**Tell me about a time you made a mistake — STATUS: still open**
- 2026-07-06: Considered an Aurora RDS incident, explicitly ruled out by William ("let's not pursue that"). No replacement story yet — needs a real one before this is interview-ready. Do not fabricate; a made-up story fails under a real follow-up question.

### STAR stories bank
- [x] Prepare 6–8 STAR stories covering automation, incident response, stakeholder communication, ambiguity, conflict, process improvement, security/compliance, and learning quickly. (3/8 drafted, more to mine from brag doc; "mistake" story still needed — see above)
- [x] For each story: situation, task, action, result, and ISN-relevant lesson.

**Story 1 — Identity-Based Access for Fabric Event Hub Mirroring** (Security/Compliance + Process Improvement)
- Situation: Fabric Event Hub mirroring and Eventstream connections in `ws_ad_dev` depended on user-bound identities and temporary PIM-based access, so connectivity could break or need reconfiguration whenever someone's PIM eligibility expired.
- Task: Move that connectivity onto a durable, permission-scoped identity so Fabric event streaming didn't depend on any one person's standing access, without breaking pipelines currently running.
- Action: Granted the user-assigned managed identity `umi-skpad-dev-usw2-003` the specific Azure RBAC roles it needed plus workspace contributor-group membership. Built the runbook for service-principal-based Fabric Eventstream connections so future connections default to that pattern instead of a personal account.
- Result: Fabric Event Hub mirroring now runs on identity-based access that doesn't expire with PIM, eliminating reconfiguration churn from relying on temporary elevated access, and setting the reusable pattern for future Fabric identity work.
- ISN-relevant lesson: Least-privilege, service-identity-first design isn't just a security checkbox — it's operational reliability. "Temporary access that works today" is a silent future outage.

**Story 2 — Building SkpWatch From Scratch** (Ambiguity + Ownership + Systems Thinking)
- Situation: There was no dedicated monitoring surface for critical services like GitHub Actions and Aurora RDS. Visibility was ad hoc, and ownership across the estate was unclear, which slowed triage.
- Task: Build a monitoring solution (SkpWatch) essentially from zero — figure out what needed watching, who owned it, and how the monitoring system itself should run reliably — with no existing blueprint.
- Action: Built the first monitoring blades for GitHub Actions and Aurora RDS to get real visibility live. Did the source-inventory and routing-boundary work to clarify ownership. Built a durable-function backbone underneath so the monitoring system itself had a resilient execution model instead of a fragile script.
- Result: SkpWatch went from nonexistent to a working, durable monitoring platform with clear ownership boundaries, improving visibility for critical services and killing the "whose alert is this" ambiguity that existed before.
- ISN-relevant lesson: When building the first version of something with no existing pattern, the ownership/boundary work matters as much as the code — a monitoring tool nobody's sure is "theirs" doesn't get watched.

**Story 3 — Driving GitHub Actions / Cloud-Native Adoption Through Enablement, Not Just Tooling** (Stakeholder Communication + Process Improvement)
- Situation: Teams needed to modernize away from legacy patterns toward cloud-native, application-development-style, text-based workflows (e.g., GitHub Actions) — but building the tooling alone doesn't guarantee anyone uses it.
- Task: Get an actual new workflow/repo adopted by the team, not just built and ignored.
- Action: Built the GitHub Actions workflow/repository with a clean setup. Recognized that visibility and hands-on comfort — not the tooling itself — were the real adoption blockers, so built a sandbox environment where the team could safely practice and get familiar before using it for real. Backed it with documentation (dozens of Confluence pages) and instructional videos — a documentation/training pattern honed doing this professionally at Microsoft — so people had a self-serve path to competence instead of needing hand-holding.
- Result: Teams became comfortable enough with the new workflow to actually adopt it, turning a "built it, nobody used it" risk into real day-to-day usage.
- ISN-relevant lesson: Modernization succeeds or fails on adoption, not code quality — pairing new tooling with a safe practice environment and clear documentation is what actually moves a team's habits, especially in a compliance-heavy, process-driven organization like ISN.

_Note: Stories 1–2 drafted from brag-doc log entries; Story 3 drafted from William's own account (2026-07-06) — verify specifics (which repos/teams, any adoption metrics) before using live. 5 more stories to mine for full 6–8 coverage, including a real "mistake" story._

### Technical examples and architecture talking points
- [ ] Collect 4–6 examples William can discuss: Azure administration, PowerShell automation, identity/access, ticket triage, CI/CD or GitHub workflows, Semantic Kernel/AI-assisted operations, documentation-as-code.
- [ ] Add concise bullets or diagrams where useful.
- [ ] **IIS refresher (priority):** app pools & recycling, bindings/SNI, request pipeline (modules/handlers), SSL/TLS cert binding, app pool identity & permissions, log locations/troubleshooting, publishing a site (Web Deploy vs. manual), common failure modes (502/503, app pool crashes).
- [ ] Storage Accounts: redundancy tiers (LRS/ZRS/GRS), access tiers (hot/cool/archive), blob vs. file vs. queue vs. table, SAS tokens & access keys, static website hosting.
- [ ] Elastic Search: index basics, querying, cluster health, common ops use cases (log search, alerting).
- [ ] Scripting/automation and "how you revision systems" — have concrete PowerShell/Azure examples and a clear answer on change-management/versioning practices.
- [ ] Copilot/Claude usage — concrete examples of how AI tools speed up or improve your daily work (this repo's CLI/skills setup is a strong example).

### Resume, LinkedIn, and portfolio alignment
- [ ] Review resume/LinkedIn/portfolio for ISN fit.
- [ ] Identify gaps and sharpen outcome phrasing.
- [ ] Prepare links or artifacts to mention during the interview.

### Questions to ask ISN
- [x] Draft thoughtful questions about team priorities, success measures, operational pain points, tooling, security/compliance expectations, growth path, and first-90-days expectations.
- [x] Mark must-ask vs optional.

1. **(must-ask) Scale & reliability** — "ISNetworld runs across 850+ hiring clients and 85,000 contractor/supplier customers in 85+ countries — at that scale, where does the infrastructure team feel the most operational pain today, and what does the on-call/incident model look like?"
2. **(must-ask) Modernization / technical direction** — "Where is the team on modernizing identity and access patterns — things like moving from legacy service accounts to managed identities, or service-principal-based connections — is that an active initiative, or already established practice?"
3. **(optional) Success criteria / first 90 days** — "How does the team define success in the first 90 days for this role — what would make you confident six months in that this was the right hire?"

Also published to Notion: ISN Interview Prep — STAR Stories (https://app.notion.com/p/ISN-Interview-Prep-STAR-Stories-395202bafe7181ce818ed0b89abd4093)

### Mock interview and rehearsal
- [ ] Run a timed mock interview.
- [ ] Practice intro, behavioral questions, technical deep dives, salary/availability if relevant, and close.
- [ ] Capture weak spots and revise prep notes.

### Interview day checklist
- [ ] Confirm schedule/timezone, interviewer names, and meeting link.
- [ ] Check device/audio/video, quiet room, resume/portfolio links, notes, water.
- [ ] Prepare follow-up email draft and post-interview debrief template.

## Actions

### 2026-07-02
WORKLOG: Updated ACE-24 with confirmed interview details from recruiter email (July 6, 2026 1pm CT, interviewers Ahlam Asad & Nathan Crabb, Teams video call) and expanded the technical talking-points checklist with an IIS-focused refresher plus Storage Accounts and Elastic Search bullets, per the topics list ISN's recruiter provided.
COMMENT: Added confirmed interview logistics and an IIS-priority technical refresher checklist to ACE-24 based on the recruiter's topic list.

### Round 2 — Friday 2026-07-10, 3:00 PM CDT — Technical (Nathan + Cloud Engineer)
- Interviewers: Nathan Crabb (repeat, from Round 1) + a Cloud Engineer (name TBD — research once known).
- [ ] Look up the Cloud Engineer's background/expertise (LinkedIn or ISN team info) once name is confirmed.
- [ ] Brush up: split-brain DNS — what it is, when/why it's used, how to explain it clearly in an interview answer.
- [ ] Brush up: scoping GPOs — targeting via OU/security group/WMI filtering, precedence/inheritance/blocking, loopback processing.
- [ ] Brush up: on-prem Active Directory fundamentals — domains/forests/trusts, FSMO roles, replication, sites/subnets.
- [ ] Brush up: Fedora/Linux fundamentals — likely systemd, networking basics, package management, how it interacts with AD (e.g. SSSD/realmd/Kerberos joins) given the on-prem focus.
- [ ] Do a timed mock run on these on-prem topics specifically before Friday.

## Consolidation Note

This issue supersedes ACE-25 through ACE-31, which were created as separate prep work items and then archived so the project has one canonical ISN interview prep ticket.

## Actions

### 2026-07-07
WORKLOG: William confirmed Round 2 is scheduled for Friday 2026-07-10 at 3:00 PM CDT — technical interview, likely Nathan again plus a Cloud Engineer (name TBD). Added a dedicated prep section: brush up on split-brain DNS, GPO scoping (OU/security group/WMI filtering, precedence/inheritance/loopback), on-prem Active Directory fundamentals, and Fedora/Linux fundamentals given the on-prem angle. Also flagged researching the Cloud Engineer interviewer's background once the name is known.
COMMENT: Round 2 confirmed — Friday 2026-07-10, 3:00 PM CDT, technical interview (likely Nathan again + a Cloud Engineer, name TBD). Added a prep checklist: split-brain DNS, GPO scoping, on-prem Active Directory fundamentals, and Fedora/Linux fundamentals. Will research the Cloud Engineer's background once their name is confirmed.

### 2026-07-06
WORKLOG: 1h | Ran a mock-interview warm-up on IIS fundamentals (traffic flow via HTTP.sys, app pool isolation/recycling, common failure modes) as general technical-interview practice. Mined the 2026 brag doc for STAR material and drafted two stories (Fabric UMI identity access, SkpWatch monitoring build-out). Researched ISN Software Corporation (ISNetworld: contractor/supplier risk-management platform, 850+ hiring clients, 85,000 contractor/supplier customers, 85+ countries, Dallas HQ) and drafted 3 targeted questions to ask. Published all of the above to a new Notion page. William confirmed the "why ISN" answer draft; ruled out an Aurora RDS incident as the "mistake" story and instead described a GitHub Actions adoption/communication pattern (build tooling → sandbox → docs/video → adoption), which became STAR Story 3 instead. The "tell me about a mistake" question remains genuinely open.
COMMENT: Drafted 3 STAR stories, 3 interview questions, and a "why ISN" answer for the ISN interview prep; published to Notion (https://app.notion.com/p/ISN-Interview-Prep-STAR-Stories-395202bafe7181ce818ed0b89abd4093) and mirrored into this issue file. Still open: a real "tell me about a mistake" story (nothing fabricated), core narrative/elevator pitch, technical talking points writeup, resume alignment, mock interview rehearsal, and interview-day checklist.

### 2026-06-17
WORKLOG: Consolidated the ISN interview prep plan into ACE-24 and archived the duplicate prep tickets ACE-25 through ACE-31.
COMMENT: Consolidated the interview prep checklist into ACE-24 so there is one canonical work item for ISN interview prep.

## Follow-up

Status: Backlog
TODO:
- [ ] Work through the consolidated prep checklist above
- [ ] Run a mock interview before the scheduled ISN interview
