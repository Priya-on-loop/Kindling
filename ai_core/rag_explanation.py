import csv
import json
from call_llm import call_llm

TASK_STATEMENTS_PATH = "Data/task_statements.csv"

def get_top_tasks_for_occupation(soc_code: str, max_tasks: int = 3) -> list[str]:
    """TCP-26: Pull the top task statements for one occupation."""
    tasks = []
    with open(TASK_STATEMENTS_PATH, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['O*NET-SOC Code'] == soc_code:
                tasks.append(row['Task'])
    return tasks[:max_tasks]

EXPLANATION_SYSTEM_PROMPT = """You write a short, honest explanation of why a career might fit a student, \
using ONLY the real task statements provided below. Do not invent duties, skills, or facts that are not \
directly present in the provided tasks. If the tasks don't give enough to say something specific, say \
something more general rather than inventing a specific-sounding claim.

Write 2-3 sentences, warm and plain, not corporate-sounding. No bullet points."""

def compose_explanation(occupation_title: str, tasks: list[str]) -> str:
    """TCP-27: Ground the explanation in the retrieved task text."""
    task_block = "\n".join(f"- {t}" for t in tasks)
    user_message = f"Occupation: {occupation_title}\n\nReal tasks for this occupation:\n{task_block}\n\nWrite the explanation now."
    return call_llm(messages=[{"role": "user", "content": user_message}], system_prompt=EXPLANATION_SYSTEM_PROMPT)

def validate_explanation(explanation: str, tasks: list[str]) -> dict:
    """TCP-28: Check the explanation doesn't assert anything absent from the retrieved tasks."""
    task_block = "\n".join(f"- {t}" for t in tasks)
    validation_prompt = f"""Retrieved tasks:
{task_block}

Generated explanation:
{explanation}

Does the explanation assert any specific fact, duty, or skill NOT supported by the retrieved tasks above? \
Answer with ONLY a JSON object: {{"unsupported_claim_found": true or false, "reason": "one sentence"}}"""
    raw = call_llm(messages=[{"role": "user", "content": validation_prompt}])
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"unsupported_claim_found": None, "reason": "validation response was not valid JSON, check manually"}


if __name__ == "__main__":
    test_code = "15-1252.00"
    test_title = "Software Developers"

    tasks = get_top_tasks_for_occupation(test_code)
    print(f"--- Retrieved tasks for {test_title} ({test_code}) ---")
    for t in tasks:
        print(" -", t)

    if not tasks:
        print("\nNo tasks found - check TASK_STATEMENTS_PATH matches your actual file location.")
    else:
        print()
        explanation = compose_explanation(test_title, tasks)
        print("--- Generated explanation ---")
        print(explanation)

        print()
        validation = validate_explanation(explanation, tasks)
        print("--- Validation result ---")
        print(json.dumps(validation, indent=2))