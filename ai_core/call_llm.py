import os
from dotenv import load_dotenv
from groq import Groq
from google import genai
from google.genai import types

load_dotenv()

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def call_llm(messages: list[dict], system_prompt: str = "", temperature: float | None = None) -> str:
    """
    messages: list like [{"role": "user", "content": "hello"}]
    system_prompt: optional instruction for how the model should behave
    temperature: optional sampling temperature. Left as the provider
        default (None) for normal conversational replies, which want
        natural variety; callers that need stable, reproducible output
        (e.g. RIASEC scoring) pass a low value explicitly.
    Tries Groq first. If anything goes wrong, falls back to Gemini.
    Always returns a plain string.
    """
    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    try:
        kwargs = {"model": "openai/gpt-oss-120b", "messages": full_messages}
        if temperature is not None:
            kwargs["temperature"] = temperature
        response = groq_client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    except Exception as e:
        print(f"Groq failed ({e}), falling back to Gemini...")
        text_block = ""
        if system_prompt:
            text_block += f"Instructions: {system_prompt}\n\n"
        for m in messages:
            text_block += f"{m['role']}: {m['content']}\n"
        try:
            config = types.GenerateContentConfig(temperature=temperature) if temperature is not None else None
            response = gemini_client.models.generate_content(
                model="gemini-3.6-flash",
                contents=text_block,
                config=config,
            )
            return response.text
        except Exception as e2:
            raise RuntimeError(f"Both providers failed. Groq: {e}. Gemini: {e2}")


if __name__ == "__main__":
    print("--- Smoke test: Groq directly ---")
    try:
        r = groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": "Say hello in one short sentence."}],
        )
        print("Groq OK:", r.choices[0].message.content)
    except Exception as e:
        print("Groq FAILED:", e)

    print("\n--- Smoke test: Gemini directly ---")
    try:
        r = gemini_client.models.generate_content(
            model="gemini-3.6-flash",
            contents="Say hello in one short sentence.",
        )
        print("Gemini OK:", r.text)
    except Exception as e:
        print("Gemini FAILED:", e)

    print("\n--- Smoke test: call_llm() wrapper ---")
    reply = call_llm(messages=[{"role": "user", "content": "Say hello in one short sentence."}])
    print("Wrapper reply:", reply)