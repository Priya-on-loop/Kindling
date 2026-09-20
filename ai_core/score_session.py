from inference_prompt import score_transcript


def messages_to_transcript(messages: list[dict]) -> str:
    """Converts db.get_messages()'s role/content format into the
    Q:/A: text block score_transcript() actually expects."""
    lines = []
    for m in messages:
        prefix = "Q" if m["role"] == "assistant" else "A"
        lines.append(f"{prefix}: {m['content']}")
    return "\n".join(lines)


def score_session(messages: list[dict]) -> dict:
    """One clean call: raw session messages in, RIASEC scores out.
    This is the function main.py should call once a session ends -
    it hides the format conversion so the caller doesn't need to know
    score_transcript()'s internal text format."""
    transcript = messages_to_transcript(messages)
    return score_transcript(transcript)


if __name__ == "__main__":
    fake_session = [
        {"role": "assistant", "content": "What have you been curious about lately?"},
        {"role": "user", "content": "I keep taking apart my brother's RC cars, not to fix them, just to see how the motor connects to the wheels."},
        {"role": "assistant", "content": "And after you've taken one apart, do you usually put it back exactly how it was, or does something change?"},
        {"role": "user", "content": "Something always changes. Last time I rewired it so both motors ran off a single switch."},
    ]
    import json
    print(json.dumps(score_session(fake_session), indent=2))