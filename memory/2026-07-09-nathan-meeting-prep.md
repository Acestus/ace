# Meeting Prep — Nathan + Manager (ISN)

**Role: Site Reliability Engineer, sub-5-minute incident management.** This
reframes everything — Nathan's AD/GPO/DNS questions weren't AD trivia, they
were incident-triage scenarios. He's testing whether you can go from "here's
a symptom" to "here's the likely cause and the fix" fast, under pressure, with
a clear diagnostic sequence — not whether you can recite trust topology.
Upcoming meeting adds his manager, who started as a SQL DBA. Goal: demonstrate
a fast, repeatable incident-response mental model on the AD/GPO/DNS material,
*and* bridge into data/SQL-adjacent strengths since that's the manager's home
turf.

## The sub-5-minute framing (lead with this, not with theory)

For an SRE screen, the answer shape matters as much as the content. For every
scenario question, structure the answer as a fast triage loop, out loud:

1. **Symptom** — what's the user/system actually seeing (timeout, wrong host,
   policy not applying, auth failure)?
2. **Fast checks (first 2 minutes)** — the 2-3 commands/checks that either
   confirm or rule out the most likely cause, in order of speed-to-signal,
   not order of thoroughness. Cheapest/fastest check first.
2. **Likely cause, ranked** — state the most probable cause first (base rate:
   "90% of the time this is X"), with a fallback if the first check doesn't
   confirm it.
4. **Mitigate vs. fix** — call out the difference explicitly: what stops the
   bleeding right now (restart, clear one bad record, force replication) vs.
   what actually prevents recurrence (enable scavenging, fix delegation
   config, add monitoring). SRE interviewers want to hear you separate these.
5. **Blast radius / rollback** — one sentence on who else is affected and how
   you'd back out if the fix makes it worse.

Saying this framing explicitly ("here's how I'd triage that in the first five
minutes") answers the actual job requirement, not just the trivia question.

## AD/GPO Quick-Recall — as incident triage, not trivia (see portfolio page for full depth)

### Scenario: "A GPO isn't applying to some machines in an OU"
1. **Symptom**: policy missing on a subset of machines in a linked OU.
2. **Fast checks**: `gpresult /r` or `gpresult /h report.html` on an affected
   machine (30 sec, tells you Applied vs Denied and *why* — security filter,
   WMI filter, or precedence loss). Cross-check `gpupdate /force` isn't
   silently failing.
3. **Likely cause, ranked**: (1) security filtering excludes that machine/user
   — check the GPO's Scope tab ACL first, it's the most common cause and the
   fastest to confirm. (2) WMI filter not matching (OS/hardware mismatch).
   (3) a higher-precedence GPO with Enforced is overriding it further up the tree.
4. **Mitigate vs. fix**: mitigate = manually add the machine/group to the
   security filter or run `gpupdate /force` to unstick a caching issue. Fix =
   correct the underlying filter/group membership so it's not a one-off.
5. **Blast radius**: security filtering changes affect only the filtered
   group, so blast radius is contained — low risk to touch live.

### Scenario: "One hostname resolves to two different IPs"
1. **Symptom**: intermittent connection failures/timeouts to a named host;
   some clients succeed, some don't.
2. **Fast checks (first 2 min)**: `nslookup <host>` against 2+ DCs to rule out
   simple replication lag first — cheapest check, and if it's just lag it
   clears on its own. Then check the record's timestamp in DNS Manager (0 =
   static, won't self-heal; nonzero = dynamic, should age out).
3. **Likely cause, ranked**: (1) stale dynamic-registration record left behind
   after a re-IP, with scavenging off or interval too loose — most common in
   practice. (2) legitimate multi-homed host or round-robin LB (verify both
   IPs are actually live before assuming "stale"). (3) split-horizon DNS
   returning different answers by view (expected, not a bug).
4. **Mitigate vs. fix**: mitigate = manually delete the stale record or force
   `ipconfig /registerdns` on the correct host to restore consistent
   resolution immediately. Fix = enable DNS scavenging/aging (7-day/7-day is
   the common default) so this stops recurring without manual cleanup.
5. **Blast radius**: every client resolving that name is at risk of hitting
   the dead IP — treat as user-facing until confirmed contained; rollback is
   trivial (re-add a record if you're wrong about which one is stale).

### Scenario: "Federated transitive trust" / cross-forest auth or delegation failure
1. **Symptom**: user auths fine directly, but an app-to-app double-hop
   (web app impersonating user to hit SQL/back-end) fails across a forest trust.
2. **Fast checks**: reproduce the failure and read the actual error —
   "target principal name incorrect" or an SSPI/Kerberos failure at the
   second hop is the signature. Confirm first-hop auth succeeded (rules out
   a plain trust/connectivity problem) before chasing delegation config.
3. **Likely cause, ranked**: forest trust transitivity gives you
   *authentication* across the boundary automatically, one hop deep — it does
   **not** give you *delegation*. Most likely cause: constrained/resource-based
   constrained delegation was never configured on both sides of the trust for
   that specific service account.
4. **Mitigate vs. fix**: mitigate = often none available quickly — delegation
   gaps usually require an actual config change, so be honest that this one
   isn't a fast hot-fix, it's a scoped change with a maintenance window. Fix =
   configure constrained/RBCD delegation explicitly for the SPN pair, verify
   selective authentication settings on the trust aren't blocking it either.
5. **Blast radius**: limited to the specific double-hop workflow, not
   first-hop auth broadly — good thing to state explicitly so you're not
   over-escalating a contained issue.

## VM & SQL Server Incident Triage (what the SQL-DBA-background manager will probe)

Same Symptom → Fast Checks → Likely Cause → Mitigate vs. Fix → Blast Radius shape,
applied one layer down from AD — the VM/Hyper-V and SQL Server layer. Full detail
is on the portfolio page (section 5); here's the compressed recall version.

### Scenario: "SQL Server on a VM is suddenly slow"
- **Fast checks**: CPU ready time on the VM (host contention) in parallel with
  `sp_whoisactive`/`sys.dm_exec_requests` for blocking + top wait types.
- **Likely cause, ranked**: (1) VM-level contention — CPU ready time high or
  Dynamic Memory ballooning the guest. (2) SQL-side blocking/lock chain or
  missing index causing scans. (3) Storage latency — `PAGEIOLATCH_*` waits,
  check `sys.dm_io_virtual_file_stats`.
- **Mitigate vs. fix**: kill blocking session / move VM off oversubscribed
  host vs. right-size reservations, add index, move files to faster storage.
- **Blast radius**: check if other guests on the same host are degraded too
  before assuming it's isolated to this one instance.

### Scenario: "SQL Server / VM won't fail over" (Always On AG or Failover Cluster)
- **Fast checks**: `sys.dm_hadr_availability_replica_states` for sync health
  and failover mode (automatic vs. manual); cluster quorum state for VMM/Hyper-V.
- **Likely cause, ranked**: (1) replica set to manual failover, not automatic
  — easy to mistake for "broken." (2) quorum lost, cluster refuses to act to
  avoid split-brain. (3) sync unhealthy (async commit/secondary behind), so
  auto-failover is blocked to avoid data loss.
- **Mitigate vs. fix**: force manual failover once data-loss risk is
  confirmed acceptable, or restore quorum vs. review failover mode/witness
  config long-term.
- **Blast radius**: explicitly call out RPO impact before forcing a failover
  — this is exactly the kind of judgment call a DBA-background manager wants
  to hear you articulate, not skip past.

### Scenario: "Hyper-V host unresponsive, SQL guest along with it"
- **Fast checks**: confirm from a second management path (direct console,
  different VMM server) that it's really the host and not just a VMM
  agent/WinRM issue — common false alarm.
- **Likely cause, ranked**: (1) VMM agent/WinRM failure on an otherwise-healthy
  host (most common). (2) host actually hung — cluster should auto-failover
  VMs. (3) network partition risking false failover if quorum is misconfigured.
- **Mitigate vs. fix**: let/force cluster move the SQL VM to a healthy node
  vs. restart the VMM agent / investigate the host hang.
- **Blast radius**: every VM on that host is at risk, not just the SQL guest
  — check full host inventory before declaring a single-VM incident.

### Key vocabulary to drop naturally (signals depth without over-explaining)
- CPU ready time, Dynamic Memory/ballooning, `PAGEIOLATCH_*` waits,
  Always On Availability Groups vs. Windows Failover Clustering (two
  independent layers), quorum, RPO/RTO trade-off, live migration vs. cluster
  failover.

## Bridging to the Manager (SQL DBA background)

He'll likely care about data platform depth, not just AD/infra. Lean into:

- **KQL** — comfortable filtering, projecting, summarizing over large log/telemetry
  datasets (Log Analytics / Eventhouse). Natural translation point from his
  T-SQL background: `where`/`project`/`summarize` map conceptually to
  `WHERE`/`SELECT`/`GROUP BY`, but built for high-cardinality time-series and
  semi-structured data rather than relational tables.
- **Medallion architecture** (Bronze → Silver → Gold in Fabric) — raw landing,
  cleaned/conformed, curated/aggregated. Good talking point: this is the
  modern analogue to staging → ODS → data mart patterns a DBA already knows,
  just decoupled from a single RDBMS and built for lakehouse-scale data.
- **Kappa architecture / streaming** — Event Hub → Eventstream → Eventhouse.
  Contrast with classic batch ETL: single streaming path handles both
  real-time and historical replay instead of maintaining separate batch and
  speed layers (Lambda). Relevant if he asks about real-time reporting vs.
  nightly batch jobs he's used to from SQL Server Agent jobs/SSIS.
- **Microservices architecture** — decompose by bounded context, own data per
  service, async messaging over shared-DB coupling. Useful contrast point:
  a DBA background often comes from a monolith-single-database mindset, so
  be ready to explain *why* you'd split data ownership and how that changes
  transactional guarantees (eventual consistency, saga pattern vs. ACID
  transactions he's used to).
- **On-prem .NET Framework reality check** — don't oversell cloud-native.
  Acknowledge ISN still runs a lot of on-prem .NET Framework, so be ready to
  talk about pragmatic hybrid patterns: classic SQL Server + on-prem AD/GPO
  alongside newer Fabric/Azure work, not a full lift-and-shift narrative.
  Shows you can meet him where his experience is instead of only pitching
  greenfield cloud architecture.

## Suggested framing if asked "what's your SQL background"

- Comfortable with T-SQL fundamentals, but where you differentiate is
  *analytical* querying at scale (KQL) and pipeline/architecture design
  (medallion, streaming ingestion) rather than deep DBA-level tuning/maintenance
  (index internals, backup/recovery strategy, HA/DR configuration). If he
  probes there, be honest about the gap and pivot to where your strength
  actually is — the data platform architecture around the database, not the
  database engine internals.

## If they ask directly about incident management process (not just scenarios)

Have a crisp answer ready for "walk me through how you'd handle an incident"
separate from the technical scenarios above:

- **Detect → Triage → Mitigate → Fix → Review**, and be explicit that
  mitigate and fix are different steps with different time budgets. Sub-5-min
  target is almost always about *mitigation* (stop user impact), not root
  cause fix.
- **Say the first move out loud**: acknowledge/claim the incident, establish
  scope/blast radius, communicate status early even if the update is "still
  investigating" — silence during an incident is worse than an uncertain update.
- **Runbook-first instinct**: check for an existing runbook/known-error match
  before deep investigation — fastest path to sub-5-min resolution is
  pattern-matching to something that's happened before, not re-deriving root
  cause from scratch every time.
- **Escalation discipline**: know your own time-box — state a personal rule
  like "if I don't have a mitigation path in 3 minutes, I loop in a second
  person or escalate" rather than heroically debugging solo past the point
  where it's still "sub-5-minute."
- **Post-incident**: blameless review, update the runbook/monitoring so the
  same class of issue is faster to catch next time (e.g., DNS scavenging
  alerting, GPO drift detection) — ties back to the specific AD/DNS/GPO fixes
  above as concrete examples of "turning an incident into a monitoring rule."

## Portfolio artifact

Live page (once deployed): `portfolio.acestus.com/articles/ad-gpo-fundamentals.html`
— linked from the hub under the "📊 Professional" section as
"AD & GPO Fundamentals." Good to have pulled up during the call if he wants
to see it laid out.
