# Metric Definitions — Squad Delivery Performance

The single source of truth for every number in the dashboard. A metric is only as
trustworthy as the rule behind it, so each is defined explicitly, with its source and
its exclusions. These would be confirmed with the VP and PMO before building.

---

## Cycle Time

**Definition:** Hours from the first transition into `Staging` (work started) to the
first transition into `Done` (complete), per ticket.

**Source:** `jira_changelog` (status transition history) — NOT the issues table. The
issues table holds only the current status; the duration lives in the event history.

**Why Staging→Done (not Created→Resolved):** A ticket is created and then sits in a
backlog before anyone picks it up. Created→Resolved counts that waiting time and
overstates how long work actually took. Starting the clock at `Staging` measures
handling time, not queue time.

**Exclusions:** Tickets that never reached `Done` (still in flight, or ended in
`Dismissed`) have no end timestamp and are excluded from cycle-time averages — they are
not treated as zero or as an open-ended maximum.

---

## Time in Status (bottleneck)

**Definition:** For each ticket, the hours between one status transition and the next,
attributed to the status the ticket **entered** at the first transition.

**Source:** `jira_changelog`, using `LEAD()` over each ticket's transitions ordered by time.

**Subtlety (a real correctness trap):** the interval between transition N and N+1 is time
spent in the status `to_status` of transition N — the status entered — not `from_status`.
Using `from_status` inverts the result. Caught during QA by tracing a single ticket.

---

## Rework Rate

**Definition:** Share of tickets that bounced back from `In Review` to `Staging` at least
once (a "Needs Fix" style return for corrections).

**Source:** `jira_changelog` — any reverse transition `In Review → Staging`.

**Use:** A quality signal. Rising rework alongside rising volume is the warning sign that
a team is pushing throughput at the cost of quality.

---

## Throughput

**Definition:** Count of tickets that reached `Done` per squad per sprint.

**Source:** `vw_squad_delivery`, counting non-null cycle times by sprint and squad.

**Note:** Only meaningful against a consistent two-week sprint cadence. If cadence varied,
normalize to a per-week basis before comparing across time.

---

## Quality (post-release incidents)

**Definition:** Count of ServiceNow incidents tied to a squad's project in a sprint —
defects that escaped to production.

**Source:** `servicenow_incidents`, joined to `clarity_projects` on `project_key`.

**Use:** The downstream half of the quality picture. Rework catches problems before
release; incidents catch what slipped through.

---

## Priority Flag

**Definition:** Whether a ticket's project is flagged priority/funded in the PPM system.

**Source:** `clarity_projects.is_priority`, joined to Jira via a project-key crosswalk
(Jira keys carry a prefix like `AUTOQ-1234`; Clarity carries the same `project_key`).

**Use:** Lets leadership filter to the work that matters — avoiding the "vanity chart" the
VP explicitly didn't want.

---

## Exclusions summary (applied consistently)

| Situation | Treatment |
|---|---|
| Never reached Done | Excluded from cycle time |
| Dismissed / Cancelled | Excluded from cycle time and throughput |
| Bug with null story points | Excluded from velocity, not counted as zero |
| Status label varies by squad | Standardized to canonical (Staging / In Review / Done) |
| Jira key has no Clarity match | Priority flag null; surfaced, not silently dropped |
