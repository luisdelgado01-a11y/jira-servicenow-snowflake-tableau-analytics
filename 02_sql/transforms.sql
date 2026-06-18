-- =====================================================================
-- USAA Squad Delivery Performance -- TRANSFORM LAYER
-- Author: Luis A. Delgado  |  Analyst-owned transform on warehouse data
-- Target dialect: Snowflake. (A SQLite-compatible runner is provided in
-- run_transforms.py so you can execute end-to-end locally.)
--
-- Division of labor: a data engineer lands raw Jira/ServiceNow/Clarity into
-- the warehouse. THIS layer -- the modeling and metric definition -- is mine.
-- =====================================================================

-- ---------------------------------------------------------------------
-- STEP 0: Canonicalize drifting status names.
-- Squads use different labels for the same workflow stage. Standardize so
-- the math doesn't fragment. (Auto Quote calls review 'Code Review';
-- Claims Portal calls done 'Accepted'.)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW stg_changelog AS
SELECT
    issue_key,
    CASE
        WHEN to_status IN ('In Review','Code Review') THEN 'In Review'
        WHEN to_status IN ('Done','Accepted')         THEN 'Done'
        ELSE to_status
    END AS to_status_canon,
    CASE
        WHEN from_status IN ('In Review','Code Review') THEN 'In Review'
        WHEN from_status IN ('Done','Accepted')         THEN 'Done'
        ELSE from_status
    END AS from_status_canon,
    changed_at
FROM jira_changelog
WHERE field = 'status';

-- ---------------------------------------------------------------------
-- STEP A: CYCLE TIME from the changelog.
-- The duration is NOT in the issues table -- it's in the status history.
-- Cycle time = first transition into 'Staging' (work start)
--              -> first transition into 'Done' (complete).
-- Exclude tickets that never reached Done so they don't poison the average.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW int_cycle_time AS
WITH transitions AS (
    SELECT
        issue_key,
        MIN(CASE WHEN to_status_canon = 'Staging' THEN changed_at END) AS started_at,
        MIN(CASE WHEN to_status_canon = 'Done'    THEN changed_at END) AS done_at
    FROM stg_changelog
    GROUP BY issue_key
)
SELECT
    issue_key,
    started_at,
    done_at,
    DATEDIFF('hour', started_at, done_at) AS cycle_time_hours
FROM transitions
WHERE done_at IS NOT NULL;          -- never-completed excluded

-- ---------------------------------------------------------------------
-- STEP B: TIME-IN-STATUS (the bottleneck view).
-- Order each ticket's transitions; the gap to the next transition is how
-- long it sat in that status. Average across tickets to find stalls.
-- ---------------------------------------------------------------------
-- The interval between transition N and N+1 is time spent in the status the
-- ticket ENTERED at N -- i.e. to_status, not from_status. (Subtle but it
-- inverts the result if you use from_status.)
CREATE OR REPLACE VIEW int_time_in_status AS
SELECT
    issue_key,
    to_status_canon AS status,
    DATEDIFF('hour', changed_at,
        LEAD(changed_at) OVER (PARTITION BY issue_key ORDER BY changed_at)
    ) AS hours_in_status
FROM stg_changelog;

-- ---------------------------------------------------------------------
-- STEP C: REWORK flag -- a Needs-Fix style bounce-back is any transition
-- BACK into 'Staging' from 'In Review' (work returned for fixes).
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW int_rework AS
SELECT
    issue_key,
    MAX(CASE WHEN from_status_canon = 'In Review'
              AND to_status_canon   = 'Staging' THEN 1 ELSE 0 END) AS is_rework
FROM stg_changelog
GROUP BY issue_key;

-- ---------------------------------------------------------------------
-- STEP D: CROSSWALK -- Jira project prefixes to Clarity priority.
-- Jira keys look like 'AUTOQ-4830'; Clarity carries the priority flag by
-- project_key. Extract the prefix and join.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW int_issue_priority AS
SELECT
    i.issue_key,
    SPLIT_PART(i.issue_key, '-', 1) AS project_key,
    c.is_priority
FROM jira_issues i
LEFT JOIN clarity_projects c
    ON SPLIT_PART(i.issue_key, '-', 1) = c.project_key;

-- ---------------------------------------------------------------------
-- STEP E: THE MODELED VIEW -- one clean row per ticket, metric defined once.
-- Dedup is unnecessary here (one row per key already) but the ROW_NUMBER
-- pattern is shown in run_transforms.py for the general case.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_squad_delivery AS
SELECT
    i.issue_key,
    i.squad,
    i.sprint,
    i.issue_type,
    i.assignee_id,
    ct.cycle_time_hours,
    COALESCE(rw.is_rework, 0) AS is_rework,
    pr.is_priority
FROM jira_issues i
LEFT JOIN int_cycle_time   ct ON i.issue_key = ct.issue_key
LEFT JOIN int_rework       rw ON i.issue_key = rw.issue_key
LEFT JOIN int_issue_priority pr ON i.issue_key = pr.issue_key;

-- End of transform layer.
