"""
One-time migration: Outputs/career_graph.json's sample_tasks was built
by part_b.py as bare task-text strings (top 3 real Core tasks per
occupation), with the real Task ID from Data/task_statements.csv
dropped. The career tree's "Try it out" cards need to keep a real
sourceTaskId, so this re-derives the exact same top-3-Core-tasks
selection (same groupby + .head(3), same row order) but keeps the
Task ID this time, and rewrites sample_tasks as
[{"task_id": "...", "text": "..."}, ...]. Everything else in
career_graph.json (title, description, riasec, family) is untouched.
"""

import json
import pandas as pd

CAREER_GRAPH_PATH = "Outputs/career_graph.json"
TASK_STATEMENTS_PATH = "Data/task_statements.csv"

with open(CAREER_GRAPH_PATH, "r", encoding="utf-8") as f:
    career_graph = json.load(f)

task_df = pd.read_csv(TASK_STATEMENTS_PATH)
core_tasks = task_df[task_df["Task Type"] == "Core"].copy()

sample_tasks_with_ids = (
    core_tasks
    .groupby("O*NET-SOC Code")
    .head(3)
    .groupby("O*NET-SOC Code")
    .apply(lambda g: [
        {"task_id": str(row["Task ID"]), "text": row["Task"]}
        for _, row in g.iterrows()
    ])
    .to_dict()
)

updated = 0
unchanged_no_tasks = 0

for occupation in career_graph:
    soc_id = occupation["id"]
    tasks_with_ids = sample_tasks_with_ids.get(soc_id, [])

    if tasks_with_ids:
        # Sanity check: same text, same order, as the existing
        # bare-string sample_tasks this occupation already has —
        # this migration must not silently change WHICH tasks are
        # shown, only add the id alongside the text already there.
        existing_texts = occupation.get("sample_tasks", [])
        new_texts = [t["text"] for t in tasks_with_ids]
        if isinstance(existing_texts[0] if existing_texts else None, str) and existing_texts != new_texts:
            raise ValueError(
                f"Task text mismatch for {soc_id}: existing={existing_texts} new={new_texts}"
            )
        occupation["sample_tasks"] = tasks_with_ids
        updated += 1
    else:
        occupation["sample_tasks"] = []
        unchanged_no_tasks += 1

with open(CAREER_GRAPH_PATH, "w", encoding="utf-8") as f:
    json.dump(career_graph, f, indent=2, ensure_ascii=False)

print(f"Updated {updated} occupations with task IDs.")
print(f"{unchanged_no_tasks} occupations have no Core tasks in the source data (left as []).")
print("Total occupations:", len(career_graph))
