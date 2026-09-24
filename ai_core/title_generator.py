import re
from call_llm import call_llm

FILLER_STARTS = ["honestly", "so", "um", "uh", "like", "well", "okay", "ok", "idk", "i mean", "i guess"]


def build_fallback_title(text: str) -> str:
    """
    The real first user message, cleaned up into something readable
    for a thread row — not generated, just trimmed: strip a filler
    opener ("honestly", "so", "um", "idk", ...), cut to ~40 real
    characters at a word boundary, add an ellipsis if it was cut,
    and capitalize the first letter. Never invents words.
    """
    cleaned = text.strip()

    changed = True
    while changed:
        changed = False
        for filler in FILLER_STARTS:
            pattern = r"^" + re.escape(filler) + r"[,\s]+"
            new_cleaned = re.sub(pattern, "", cleaned, count=1, flags=re.IGNORECASE)
            if new_cleaned != cleaned:
                cleaned = new_cleaned.strip()
                changed = True

    if not cleaned:
        return "New conversation"

    if len(cleaned) <= 40:
        result = cleaned
    else:
        truncated = cleaned[:40]
        last_space = truncated.rfind(" ")
        if last_space > 0:
            truncated = truncated[:last_space]
        result = truncated.rstrip(",.!?;: ") + "…"

    return result[0].upper() + result[1:] if result else result


TITLE_SYSTEM_PROMPT = """You read part of a career-exploration chat between a guide and a student, and write a short neutral title for the thread.

Rules:
- 3 to 5 words, Title Case.
- No quotation marks, no ending punctuation.
- Describe the topic or theme the student is actually exploring, not the guide's questions.
- Respond with ONLY the title text. No other words, no explanation, no markdown."""


def generate_title(messages: list[dict]) -> str | None:
    """
    Real messages in (role/content, same shape db.get_messages()
    returns) -> a short generated title, or None if the call fails
    or the model's response doesn't look like a real title. Callers
    fall back to a trimmed first message on None, never a fabricated
    default.
    """
    convo = "\n".join(
        f"{'Guide' if m['role'] == 'assistant' else 'Student'}: {m['content']}"
        for m in messages
    )

    try:
        raw = call_llm(
            messages=[{"role": "user", "content": f"Conversation so far:\n{convo}\n\nWrite the title now."}],
            system_prompt=TITLE_SYSTEM_PROMPT,
        )
        title = raw.strip().strip('"').strip("'").rstrip(".!?").strip()

        if not title or len(title) > 60 or "\n" in title:
            return None

        return title

    except Exception:
        return None
