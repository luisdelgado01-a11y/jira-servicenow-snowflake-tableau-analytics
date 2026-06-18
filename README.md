## Jira → ServiceNow → Snowflake → Tableau

An end-to-end delivery analytics case study that mirrors a real enterprise reporting workflow. Synthetic Jira, ServiceNow, and Clarity (PPM) data flow through a Snowflake-style SQL transformation layer where cycle time, rework, bottlenecks, and quality metrics are defined and modeled before being surfaced through Tableau dashboards and executive reporting.

> Companion to my Bank Churn Risk Engine.
>
> Same philosophy: the value isn't the query or the model — it's translating outputs into decisions.

**Stack:** Jira · ServiceNow · Clarity (PPM) → Snowflake → SQL → Tableau

**Skills demonstrated:** Data Modeling · SQL (CTEs, Window Functions, Date Math) · ETL/Transformation · Metric Definition · Changelog-Based Event Analysis · Executive Reporting · Data Governance

---

## Business Question

A VP asked:

*"Which squads are actually fast versus just busy, where does work get stuck, and is quality holding as we push volume — tied to the projects that matter?"*

No detailed specification existed. The analyst's job was to define the metrics, establish the business rules, and build the answer.

---

## Architecture

Jira + ServiceNow + Clarity

↓

Snowflake

↓

SQL Transform Layer

↓

vw_squad_delivery

↓

Tableau Dashboard

↓

Executive Decisions

---

## What I Built (End to End)

| Stage                         | Artifact                                                                                               |
| ----------------------------- | ------------------------------------------------------------------------------------------------------ |
| Synthetic source systems      | `01_source_data/` — Jira issues + changelog, ServiceNow incidents, Clarity projects (messy on purpose) |
| Transformation layer          | `02_sql/transforms.sql` — Snowflake SQL deriving cycle time, time-in-status, rework, and project joins |
| Modeled view + dashboard data | `03_tableau/vw_squad_delivery.csv` and summary extracts                                                |
| Executive readout             | `04_executive_readout/Executive_Readout.pdf` — one-page findings and recommendations                   |
| Architecture                  | `05_architecture/architecture.png` — end-to-end data flow                                              |
| Slide deck                    | `07_slide_deck/USAA_Squad_Delivery_Deck.pptx` — stakeholder presentation with native charts            |
| Governance                    | `06_docs/` — metric definitions, data dictionary, and analysis summary                                 |
| Reproducible scripts          | `scripts/` — regenerate data and execute transforms end-to-end                                         |

---

## The Key Technical Insight

**Cycle time does not exist in the issue table. It is derived from status-transition history in the changelog.**

A ticket's current record only shows that it is "Done." The duration lives in the event history. The transformation layer identifies the first transition into `Staging` (work start) and the first transition into `Done`, calculates the elapsed time between them, and excludes tickets that never reached completion so they cannot skew the metric.

```sql
WITH transitions AS (
  SELECT issue_key,
    MIN(CASE WHEN to_status_canon='Staging' THEN changed_at END) AS started_at,
    MIN(CASE WHEN to_status_canon='Done' THEN changed_at END) AS done_at
  FROM stg_changelog
  GROUP BY issue_key
)
SELECT issue_key,
       DATEDIFF('hour', started_at, done_at) AS cycle_time_hours
FROM transitions
WHERE done_at IS NOT NULL;
```

---

## Key Findings

### 1. Review Is the Bottleneck, Not Coding

~29 hours spent in review versus ~6 hours in active work (~82% of workflow delay).

**Recommendation:** Increase reviewer capacity or establish review SLAs before adding engineering headcount.

### 2. Throughput Gains Came at the Expense of Quality

The sprint with the largest increase in output also experienced rework rates exceeding 60% and a spike in production incidents.

**Recommendation:** Implement quality guardrails before scaling delivery volume.

### 3. Priority Work Is Being Protected

Priority projects averaged ~38 hours cycle time versus ~61 hours for non-priority work.

**Recommendation:** Report priority and non-priority delivery separately to avoid misleading averages.

---

## Reproduce the Project

```bash
python scripts/generate_data.py
python scripts/run_transforms.py
```

Reconciliation gate:

* Modeled rows = Source Issues (157 = 157)
* Completed Tickets = Distinct Done Transitions (132 = 132)

All metrics reconcile back to source data.

> **Note on SQL Dialect:** The transformation layer is written in Snowflake SQL (the production target). `run_transforms.py` translates the logic to SQLite for local execution so the project can run without a warehouse. SQLite is only the local test harness and is not part of the architecture.

---

## Project Philosophy

Dashboards are not the deliverable.

The deliverable is a decision.

This project demonstrates how operational data from multiple systems can be transformed into trusted metrics, executive insights, and actionable recommendations.

---

*All data is synthetic and generated solely for portfolio demonstration purposes. No real, confidential, or proprietary data is included.*
