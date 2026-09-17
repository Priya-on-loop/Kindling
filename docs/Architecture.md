# System Architecture & Infrastructure

Kindling is built on a modular 6-layer architecture designed for high uptime, clean separation of concerns, and defensive execution.

---

## 6-Layer Architecture

1. **Frontend Layer (Figma/React):** Student chat UI for real-time dialogue and career graph visualization.
2. **Backend / Session API Layer (`main.py`):** Exposes REST endpoints to manage active sessions and message flow.
3. **Persistence Layer (`db.py` / `kindling.db`):** SQLite database storing user sessions and transcript records.
4. **LLM Execution Layer (`call_llm.py`):** Multi-provider LLM wrapper with primary-to-fallback execution.
5. **AI Scoring Engine (`inference_prompt.py`):** Formats transcripts into structured few-shot prompts and parses 6D JSON vectors.
6. **Career Graph Engine:** Matches the validated 6D vector against the 923-occupation O*NET cluster graph.

---

## LLM Resilience & Fallback Engine

To guarantee zero downtime during API outages or rate limits, the LLM client executes an automatic failover strategy:

[User Dialogue Input]
│
▼
[Backend API]
│
▼
[call_llm.py] ───(1. Primary Attempt)───► [Groq API: gpt-oss-120b]
│ │
│ (On Exception / Timeout) │ (Success)
▼ ▼
[2. Fallback] ───────────────────────────► [Return Output String]
│
▼
[Gemini API: gemini-3.6-flash]


---

## Core Technical Principles
* **Fail Loud, Not Silent:** If LLM inference fails twice, return neutral scores with `"inference_failed": true`.
* **Injection Resistance:** Treat all user input inside transcripts strictly as data, never as executable commands.
* **Schema Validation:** Enforce strict float checks (0.0 to 1.0) on all 6 required dimension keys.