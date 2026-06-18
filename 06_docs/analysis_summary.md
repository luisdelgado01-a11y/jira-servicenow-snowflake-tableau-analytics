# Analysis Summary — Squad Delivery Performance

Prepared for: VP, Auto Underwriting and the PMO
Scope: 3 squads, 6 sprints (43–48), 157 tickets, 132 completed.
All figures reconcile to source (modeled rows = source issues; completed = distinct Done transitions).

---

## The question we set out to answer

*"Which squads are actually fast vs. just busy, where does work get stuck, and is quality
holding as we push volume — tied to the projects that matter?"*

---

## Finding 1 — The bottleneck is review, not coding

Work spends **~29 hours on average in "In Review"** versus only **~6 hours in active work
(Staging)**. The constraint on delivery speed is not how fast people code — it's how long
finished work waits to be reviewed.

**Recommendation:** Address review capacity — reviewer rotation, WIP limits on the review
column, or a service-level target for review turnaround. This is a process fix, not an
effort problem, and it's where the largest time savings sit.

---

## Finding 2 — Quality dips when volume is pushed

In the one sprint a squad surged output (Auto Quote, Sprint 45: completions roughly
doubled), **rework jumped to ~63%** and **post-release incidents rose to 6** from a baseline
near zero. Every other sprint held steady.

**Recommendation:** Treat sustainable pace as the standard. The data shows that pushing
volume past a point trades directly against quality and creates downstream incident load —
which costs more than the throughput gained. Hold pace; ramp only when rework is stable.

---

## Finding 3 — Priority work is protected (the headline understates focus)

On **priority projects, cycle time averages ~38 hours**; on **non-priority work it's ~61
hours**. The slowest squad overall is working primarily non-priority work. That means an
all-projects average makes delivery look slower than it is on the work leadership cares about.

**Recommendation:** Report priority and non-priority separately. Teams are already guarding
the important work; the headline number hides that. This directly answers the "I don't want
a vanity chart" concern — the priority filter changes the story.

---

## One-paragraph version for the executive review

> Across all squads, the thing slowing delivery is review capacity, not coding speed — work
> waits about five times longer in review than it spends being worked. Quality is holding
> everywhere except the one sprint we pushed volume, where rework and production incidents
> both spiked, which is the case for a steady pace. And on the priority projects you actually
> care about, cycle time is meaningfully better than the all-up number suggests — the teams
> are protecting the right work.

---

## How this would be delivered

- **Tableau dashboard** reading `vw_squad_delivery`: KPI tiles (cycle time, throughput,
  rework %), cycle time by squad, time-in-status bottleneck, throughput-vs-rework trend,
  and a priority-projects filter.
- **Refreshed** on a schedule from the Snowflake view, so the metric is defined once and
  every stakeholder sees the same number.
- **Caveat stated up front:** definitions (what counts as "done," which projects are
  priority) were confirmed with PMO; the dashboard footnotes them so the numbers are
  defensible.
