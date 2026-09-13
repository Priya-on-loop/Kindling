import os
from dotenv import load_dotenv
from groq import Groq
from google import genai

load_dotenv()

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def call_llm(messages: list[dict], system_prompt: str = "") -> str:
    """
    messages: list like [{"role": "user", "content": "hello"}]
    system_prompt: optional instruction for how the model should behave
    Tries Groq first. If anything goes wrong, falls back to Gemini.
    Always returns a plain string.
    """
    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    try:
        response = groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=full_messages,
        )
        return response.choices[0].message.content

    except Exception as e:
        print(f"Groq failed ({e}), falling back to Gemini...")
        text_block = ""
        if system_prompt:
            text_block += f"Instructions: {system_prompt}\n\n"
        for m in messages:
            text_block += f"{m['role']}: {m['content']}\n"

        response = gemini_client.models.generate_content(
            model="gemini-3.6-flash",
            contents=text_block,
        )
        return response.text


if __name__ == "__main__":
    reply = call_llm(
        messages=[{"role": "user", "content": "Say hello in one short sentence."}]
    )
    print("Reply:", reply)