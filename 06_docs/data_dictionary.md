# Data Dictionary — Squad Delivery Performance

Governance reference. Every field in the modeled view `vw_squad_delivery`, plus the
derived metrics and their source of truth.

## Modeled view: `vw_squad_delivery` (one row per ticket)

| Column | Type | Definition | Source |
|---|---|---|---|
| `issue_key` | text | Unique ticket identifier (e.g. AUTOQ-4830) | jira_issues |
| `squad` | text | Owning squad | jira_issues |
| `sprint` | text | Sprint the ticket belongs to | jira_issues |
| `issue_type` | text | Story or Bug | jira_issues |
| `assignee_id` | text | Raw assignee ID (resolved to name in reporting) | jira_issues |
| `cycle_time_hours` | number | Hours from first Staging to first Done; null if never completed | jira_changelog (derived) |
| `is_rework` | 0/1 | 1 if ticket bounced In Review → Staging at least once | jira_changelog (derived) |
| `is_priority` | Yes/No | Whether the ticket's project is priority/funded | clarity_projects (joined) |

## Derived metrics

| Metric | Definition | Derivation |
|---|---|---|
| Cycle Time | First Staging → First Done (hrs) | MIN of each transition timestamp from changelog, differenced |
| Rework % | Share of tickets returned Review → Staging | Reverse transition flag, averaged |
| Throughput | Tickets reaching Done per squad per sprint | Count of non-null cycle times |
| Review Time | Avg hours a ticket sits In Review | Time-in-status (interval labeled by status entered) |
| Incident Rate | ServiceNow incidents per project per sprint | servicenow_incidents joined on project_key |

## Key governance notes

- **Source of truth for durations is the changelog, not the issues table.** The issues
  table holds current status only; durations are derived from status-transition history.
- **Metrics are defined once** in `vw_squad_delivery`, so every downstream report agrees.
- **Exclusions are explicit and consistent** (see metric_definitions.md): never-completed
  tickets excluded from cycle time; Dismissed/Cancelled excluded; null story points
  excluded from velocity (not zero-filled); unmatched project keys surfaced, not dropped.
- **Reconciliation gate:** modeled rows = source issues; completed = distinct Done
  transitions. Numbers are trusted because they tie out.
