"""
Generate synthetic source data for the USAA Squad Delivery Performance case study.
Deliberately messy: cryptic assignee IDs, nulls, drifting status labels,
mismatched project keys, never-completed tickets, rework loops.
All data is invented for interview practice.
"""
import csv, random, datetime as dt
random.seed(42)

OUT = "data"

SQUADS = ["Mobile Banking", "Auto Quote", "Claims Portal"]
# Note the DRIFTING status labels across squads -- this is intentional mess.
# Canonical work-start = "Staging"; canonical done = "Done".
STATUS_FLOWS = {
    "Mobile Banking": ["To Do", "Staging", "In Review", "Done"],
    "Auto Quote":     ["Backlog", "Staging", "Code Review", "Done"],   # 'Code Review' drifts from 'In Review'
    "Claims Portal":  ["To Do", "Staging", "In Review", "Accepted"],   # 'Accepted' drifts from 'Done'
}
# Map each squad's terminal/'work-start'/'review' to canonical later in SQL.
ASSIGNEES = {  # cryptic IDs -> resolved later via crosswalk
    "712020:a3f9": "J. Rivera", "712020:b1c2": "M. Okonkwo",
    "712020:c4d5": "T. Nguyen", "712020:e6f7": "S. Delgado",
    "712020:g8h9": "P. Adeyemi",
}
PRIORITY_PROJECTS = {"AUTOQ", "CLAIMS"}  # Clarity says these are priority

issues = []
changelog = []
sprints_rows = []

issue_counter = 4800
base = dt.datetime(2026, 4, 6, 9, 0)  # PI start-ish

def iso(t): return t.strftime("%Y-%m-%dT%H:%M:%SZ")

# 6 sprints, 2 weeks each
sprint_starts = [base + dt.timedelta(days=14*i) for i in range(6)]

proj_key = {"Mobile Banking":"MOB", "Auto Quote":"AUTOQ", "Claims Portal":"CLAIMS"}

# --- Clean, unconfounded design for a PORTFOLIO piece ---
# Finding 1 (bottleneck = In Review): ALL squads have a long review dwell;
#   the pre-Staging wait and rework dwell are kept SHORT so 'In Review' is
#   unambiguously the largest time-in-status bucket.
# Finding 2 (priority work is faster, de-confounded): the SLOW squad is
#   Mobile Banking, which is NON-priority. Priority squads (Auto Quote,
#   Claims Portal) are kept faster. So 'priority is faster' is real, not an
#   artifact of one slow priority project.
# Finding 3 (quality dips on the volume push): Auto Quote Sprint 45 gets a
#   volume bump + higher rework + an incident spike.

SLOW_SQUAD = "Mobile Banking"   # non-priority, deliberately slowest

for sidx, sstart in enumerate(sprint_starts, start=43):
    sprint_name = f"Sprint {sidx}"
    sprints_rows.append([sprint_name, iso(sstart), iso(sstart+dt.timedelta(days=14))])
    for squad in SQUADS:
        flow = STATUS_FLOWS[squad]
        work_start_status = "Staging"
        done_status = flow[-1]
        review_status = flow[-2]

        n = random.randint(7, 10)
        if squad == "Auto Quote" and sidx == 45:
            n = random.randint(13, 16)   # the volume push

        for _ in range(n):
            issue_counter += 1
            key = f"{proj_key[squad]}-{issue_counter}"
            itype = random.choices(["Story","Bug"], weights=[0.7,0.3])[0]
            assignee = random.choice(list(ASSIGNEES.keys()))
            created = sstart + dt.timedelta(hours=random.randint(0, 36), minutes=random.choice([0,15,30,45]))
            sp = "" if itype=="Bug" and random.random()<0.7 else random.choice([1,2,3,5,8])

            # rework rate: baseline ~15%, elevated for the Auto Quote push
            rework_p = 0.15
            if squad == "Auto Quote" and sidx == 45:
                rework_p = 0.45
            fate = random.choices(["normal","rework","never_done","dismissed"],
                                  weights=[1-rework_p-0.10-0.05, rework_p, 0.10, 0.05])[0]

            # SHORT pre-Staging wait (keeps Staging bucket small)
            t = created + dt.timedelta(hours=random.randint(1, 6))
            changelog.append([key, "status", flow[0], work_start_status, iso(t)])
            started = t
            resolved = ""
            cur_status = work_start_status

            if fate == "never_done":
                t2 = started + dt.timedelta(hours=random.randint(4, 12))
                changelog.append([key, "status", work_start_status, review_status, iso(t2)])
                cur_status = review_status
            elif fate == "dismissed":
                t2 = started + dt.timedelta(hours=random.randint(2, 8))
                changelog.append([key, "status", work_start_status, "Dismissed", iso(t2)])
                cur_status = "Dismissed"
            else:
                # active work (Staging dwell) -- modest
                work_h = random.randint(4, 10)
                t2 = started + dt.timedelta(hours=work_h)
                changelog.append([key, "status", work_start_status, review_status, iso(t2)])
                # rework loop: SHORT staging bounce so it doesn't dominate Staging
                if fate == "rework":
                    tb = t2 + dt.timedelta(hours=random.randint(2,5))
                    changelog.append([key, "status", review_status, work_start_status, iso(tb)])
                    tre = tb + dt.timedelta(hours=random.randint(2,5))
                    changelog.append([key, "status", work_start_status, review_status, iso(tre)])
                    t2 = tre
                # REVIEW dwell -- the bottleneck, long for every squad
                review_dwell = random.randint(20, 36)
                if squad == SLOW_SQUAD:
                    review_dwell += random.randint(18, 30)  # slowest squad, NON-priority
                t3 = t2 + dt.timedelta(hours=review_dwell)
                changelog.append([key, "status", review_status, done_status, iso(t3)])
                cur_status = done_status
                resolved = iso(t3)

            issues.append([
                key, itype, cur_status,
                random.choice(["High","Medium","Low","Highest"]),
                sp, iso(created), resolved, assignee, sprint_name, squad
            ])

# ServiceNow incidents (post-release defects) keyed by project key prefix
incidents = []
inc_id = 9000
for squad in SQUADS:
    pk = proj_key[squad]
    # Auto Quote sprint-3 volume push -> spike in incidents
    for sidx in range(43,49):
        base_inc = random.randint(0,1)
        if squad=="Auto Quote" and sidx==45:
            base_inc += 6  # quality dip on the volume push
        for _ in range(base_inc):
            inc_id += 1
            incidents.append([f"INC{inc_id}", pk, f"Sprint {sidx}",
                              random.choice(["P2","P3","P3","P4"])])

# Clarity projects -- note keys here use PROJECT names that need a crosswalk to Jira prefixes
clarity = [
    ["PRJ-100","Mobile Banking Modernization","MOB","Funded","No"],
    ["PRJ-101","Auto Quote Rewrite","AUTOQ","Funded","Yes"],
    ["PRJ-102","Claims Portal Uplift","CLAIMS","Funded","Yes"],
    ["PRJ-103","Internal Tooling","TOOL","Proposed","No"],
]

def write(name, header, rows):
    with open(f"{OUT}/{name}","w",newline="") as f:
        w=csv.writer(f); w.writerow(header); w.writerows(rows)

write("jira_issues.csv",
      ["issue_key","issue_type","current_status","priority","story_points","created","resolved","assignee_id","sprint","squad"],
      issues)
write("jira_changelog.csv",
      ["issue_key","field","from_status","to_status","changed_at"],
      changelog)
write("jira_sprints.csv", ["sprint","start","end"], sprints_rows)
write("servicenow_incidents.csv", ["incident_id","project_key","sprint","priority"], incidents)
write("clarity_projects.csv",
      ["clarity_id","project_name","project_key","status","is_priority"], clarity)

print(f"issues={len(issues)} changelog={len(changelog)} incidents={len(incidents)} clarity={len(clarity)}")
