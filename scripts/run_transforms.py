"""
Run the transform layer end-to-end against the synthetic CSVs using SQLite,
write the modeled output CSVs, and reconcile counts (verify-against-source QA).

This mirrors sql/transforms.sql but uses SQLite-compatible syntax
(DATEDIFF -> julianday math, SPLIT_PART -> substr/instr, LEAD via window).
"""
import sqlite3, csv, os

DATA = "data"; OUT = "output"
os.makedirs(OUT, exist_ok=True)
con = sqlite3.connect(":memory:")
con.row_factory = sqlite3.Row
cur = con.cursor()

def load(name, table):
    with open(f"{DATA}/{name}") as f:
        r = csv.reader(f); header = next(r); rows = list(r)
    cols = ",".join(f'"{c}"' for c in header)
    cur.execute(f'CREATE TABLE {table} ({",".join(c+" TEXT" for c in header)})')
    cur.executemany(f'INSERT INTO {table} ({cols}) VALUES ({",".join("?"*len(header))})', rows)
    return len(rows)

n_iss = load("jira_issues.csv","jira_issues")
load("jira_changelog.csv","jira_changelog")
load("jira_sprints.csv","jira_sprints")
load("servicenow_incidents.csv","servicenow_incidents")
load("clarity_projects.csv","clarity_projects")

# hours between two ISO timestamps
con.create_function("hours_between", 2,
    lambda a,b: None if (a is None or b is None) else
    round((__import__("datetime").datetime.fromisoformat(b.replace("Z","")) -
           __import__("datetime").datetime.fromisoformat(a.replace("Z",""))).total_seconds()/3600, 1))

# STEP 0 canonical changelog
cur.executescript("""
CREATE VIEW stg_changelog AS
SELECT issue_key,
  CASE WHEN to_status IN ('In Review','Code Review') THEN 'In Review'
       WHEN to_status IN ('Done','Accepted') THEN 'Done' ELSE to_status END AS to_status_canon,
  CASE WHEN from_status IN ('In Review','Code Review') THEN 'In Review'
       WHEN from_status IN ('Done','Accepted') THEN 'Done' ELSE from_status END AS from_status_canon,
  changed_at
FROM jira_changelog WHERE field='status';
""")

# STEP A cycle time
cur.executescript("""
CREATE VIEW int_cycle_time AS
WITH transitions AS (
  SELECT issue_key,
    MIN(CASE WHEN to_status_canon='Staging' THEN changed_at END) AS started_at,
    MIN(CASE WHEN to_status_canon='Done' THEN changed_at END) AS done_at
  FROM stg_changelog GROUP BY issue_key)
SELECT issue_key, started_at, done_at,
  hours_between(started_at, done_at) AS cycle_time_hours
FROM transitions WHERE done_at IS NOT NULL;
""")

# STEP B time in status
cur.executescript("""
CREATE VIEW int_time_in_status AS
SELECT issue_key, to_status_canon AS status,
  hours_between(changed_at,
    LEAD(changed_at) OVER (PARTITION BY issue_key ORDER BY changed_at)) AS hours_in_status
FROM stg_changelog;
""")

# STEP C rework
cur.executescript("""
CREATE VIEW int_rework AS
SELECT issue_key,
  MAX(CASE WHEN from_status_canon='In Review' AND to_status_canon='Staging' THEN 1 ELSE 0 END) AS is_rework
FROM stg_changelog GROUP BY issue_key;
""")

# STEP D priority crosswalk (SPLIT_PART -> substr/instr)
cur.executescript("""
CREATE VIEW int_issue_priority AS
SELECT i.issue_key,
  substr(i.issue_key,1,instr(i.issue_key,'-')-1) AS project_key,
  c.is_priority
FROM jira_issues i
LEFT JOIN clarity_projects c
  ON substr(i.issue_key,1,instr(i.issue_key,'-')-1)=c.project_key;
""")

# STEP E modeled view
cur.executescript("""
CREATE VIEW vw_squad_delivery AS
SELECT i.issue_key, i.squad, i.sprint, i.issue_type, i.assignee_id,
  ct.cycle_time_hours, COALESCE(rw.is_rework,0) AS is_rework, pr.is_priority
FROM jira_issues i
LEFT JOIN int_cycle_time ct ON i.issue_key=ct.issue_key
LEFT JOIN int_rework rw ON i.issue_key=rw.issue_key
LEFT JOIN int_issue_priority pr ON i.issue_key=pr.issue_key;
""")

def dump(query, name):
    cur.execute(query); rows = cur.fetchall()
    cols = rows[0].keys() if rows else []
    with open(f"{OUT}/{name}","w",newline="") as f:
        w = csv.writer(f); w.writerow(cols)
        for r in rows: w.writerow([r[c] for c in cols])
    return len(rows)

# main modeled output (for Tableau)
n_model = dump("SELECT * FROM vw_squad_delivery ORDER BY squad, sprint, issue_key",
               "vw_squad_delivery.csv")

# a ready-to-chart squad summary
dump("""
SELECT squad,
  COUNT(*) AS tickets,
  ROUND(AVG(cycle_time_hours),1) AS avg_cycle_hours,
  SUM(CASE WHEN cycle_time_hours IS NOT NULL THEN 1 ELSE 0 END) AS completed,
  ROUND(100.0*SUM(is_rework)/COUNT(*),1) AS rework_pct
FROM vw_squad_delivery GROUP BY squad ORDER BY avg_cycle_hours DESC
""","summary_by_squad.csv")

# bottleneck: avg time in status
dump("""
SELECT status, ROUND(AVG(hours_in_status),1) AS avg_hours_in_status, COUNT(*) AS n
FROM int_time_in_status WHERE hours_in_status IS NOT NULL
GROUP BY status ORDER BY avg_hours_in_status DESC
""","bottleneck_time_in_status.csv")

# throughput + quality per sprint (joins ServiceNow incidents)
dump("""
WITH thru AS (
  SELECT sprint, squad,
    SUM(CASE WHEN cycle_time_hours IS NOT NULL THEN 1 ELSE 0 END) AS completed,
    ROUND(100.0*SUM(is_rework)/COUNT(*),1) AS rework_pct
  FROM vw_squad_delivery GROUP BY sprint, squad),
inc AS (
  SELECT s.sprint, c.project_name AS squad_proj, c.project_key,
         COUNT(*) AS incidents
  FROM servicenow_incidents s
  LEFT JOIN clarity_projects c ON s.project_key=c.project_key
  GROUP BY s.sprint, s.project_key)
SELECT t.sprint, t.squad, t.completed, t.rework_pct,
       COALESCE(i.incidents,0) AS post_release_incidents
FROM thru t
LEFT JOIN clarity_projects cp ON cp.project_name LIKE '%'||substr(t.squad,1,4)||'%'
LEFT JOIN inc i ON i.sprint=t.sprint AND i.project_key=cp.project_key
ORDER BY t.sprint, t.squad
""","throughput_quality_by_sprint.csv")

# priority comparison
dump("""
SELECT CASE WHEN is_priority='Yes' THEN 'Priority projects' ELSE 'Non-priority' END AS bucket,
  COUNT(*) AS tickets, ROUND(AVG(cycle_time_hours),1) AS avg_cycle_hours
FROM vw_squad_delivery WHERE cycle_time_hours IS NOT NULL
GROUP BY bucket ORDER BY avg_cycle_hours
""","priority_comparison.csv")

# ---- RECONCILIATION (verify-against-source QA) ----
cur.execute("SELECT COUNT(*) FROM jira_issues"); src = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM vw_squad_delivery"); mod = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM int_cycle_time"); done = cur.fetchone()[0]
cur.execute("SELECT COUNT(DISTINCT issue_key) FROM stg_changelog WHERE to_status_canon='Done'"); done_cl = cur.fetchone()[0]

print("=== RECONCILIATION ===")
print(f"Source issues:                 {src}")
print(f"Modeled rows (vw_squad):       {mod}   [match: {src==mod}]")
print(f"Completed (cycle time calc'd): {done}")
print(f"Distinct 'Done' in changelog:  {done_cl}   [match: {done==done_cl}]")
print()
print("=== SUMMARY BY SQUAD ===")
cur.execute("SELECT squad, COUNT(*) t, ROUND(AVG(cycle_time_hours),1) avg_h, ROUND(100.0*SUM(is_rework)/COUNT(*),1) rwk FROM vw_squad_delivery GROUP BY squad ORDER BY avg_h DESC")
for r in cur.fetchall(): print(f"  {r['squad']:<16} tickets={r['t']:<4} avg_cycle_h={r['avg_h']:<7} rework%={r['rwk']}")
print()
print("=== BOTTLENECK (avg hours in status) ===")
cur.execute("SELECT status, ROUND(AVG(hours_in_status),1) h FROM int_time_in_status WHERE hours_in_status IS NOT NULL GROUP BY status ORDER BY h DESC")
for r in cur.fetchall(): print(f"  {r['status']:<14} {r['h']} h")
print()
print("=== PRIORITY vs NON-PRIORITY (avg cycle h) ===")
cur.execute("SELECT CASE WHEN is_priority='Yes' THEN 'Priority' ELSE 'Non-priority' END b, ROUND(AVG(cycle_time_hours),1) h FROM vw_squad_delivery WHERE cycle_time_hours IS NOT NULL GROUP BY b ORDER BY h")
for r in cur.fetchall(): print(f"  {r['b']:<14} {r['h']} h")
print(f"\nOutputs written to {OUT}/  ({n_model} modeled rows)")
