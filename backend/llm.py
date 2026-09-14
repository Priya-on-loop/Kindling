"""
Kindling – LLM wrapper stub.
Sruthi will supply the real Groq + Gemini fallback implementation.
Signature MUST NOT change:
    call_llm(messages: list[dict], system_prompt: str = "") -> str
"""

def call_llm(messages: list[dict], system_prompt: str = "") -> str:
    # ── STUB: Temporary mock response for local testing ──
    return "That's interesting — what part of that caught your attention the most?"


if __name__ == "__main__":
    # Quick test
    sample_history = [{"role": "user", "content": "I love building mechanical keyboards."}]
    response = call_llm(sample_history)
    print("Stub LLM returned:", response)