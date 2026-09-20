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

## System Architecture Diagram
                        ┌──────────────────────────────────┐
                        │         STUDENT (User)           │
                        └────────────────┬─────────────────┘
                                         │
                                         ▼
                        ┌──────────────────────────────────┐
                        │     FRONTEND LAYER (Gokul)       │
                        │   Figma Prototype / Chat UI      │
                        └────────────────┬─────────────────┘
                                         │
                              HTTP REST (JSON)
                                         │
                                         ▼
                        ┌──────────────────────────────────┐
                        │   BACKEND SESSION API (Priya)    │
                        │         FastAPI (main.py)        │
                        │  /session/start                  │
                        │  /session/message                │
                        │  /session/history                │
                        └────────┬─────────────┬───────────┘
                                 │             │
                 ┌───────────────┘             └───────────────┐
                 │                                             │
                 ▼                                             ▼
       ┌─────────────────────────┐                 ┌─────────────────────────┐
       │  PERSISTENCE LAYER      │                 │  AI SCORING ENGINE      │
       │  SQLite (kindling.db)   │                 │  (Sruthi)               │
       │                         │                 │  inference_prompt.py    │
       │  - sessions table       │                 │                         │
       │  - messages table       │                 │  6D Interest Vector:    │
       └─────────────────────────┘                 │  builds_tinkers         │
                                                   │  investigates_why       │
                                                   │  creates_expresses      │
                                                   │  works_with_people      │
                                                   │  organizes_systems      │
                                                   │  leads_persuades        │
                                                   └────────────┬────────────┘
                                                            │
                                                            ▼
                                               ┌─────────────────────────┐
                                               │  LLM WRAPPER (Sruthi)   │
                                               │      call_llm.py        │
                                               └────────────┬────────────┘
                                                            │
                                              ┌─────────────┴─────────────┐
                                              │                           │
                                     (1. Primary)                (2. Fallback)
                                              │                           │
                                              ▼                           ▼
                                   ┌──────────────────┐        ┌──────────────────┐
                                   │     Groq API     │        │    Gemini API    │
                                   │  gpt-oss-120b    │        │ gemini-3.6-flash │
                                   └────────┬─────────┘        └────────┬─────────┘
                                            │                           │
                                            └─────────────┬─────────────┘
                                                          │
                                                          ▼
                                               ┌─────────────────────────┐
                                               │   VALIDATED 6D VECTOR   │
                                               │  + inference_failed flag│
                                               └────────────┬────────────┘
                                                            │
                                                            ▼
                                               ┌─────────────────────────┐
                                               │ CAREER GRAPH ENGINE     │
                                               │ (Aleena)                │
                                               │ O*NET 923 Occupations   │
                                               │ GMM Clustering          │
                                               └────────────┬────────────┘
                                                            │
                                                            ▼
                                               ┌─────────────────────────┐
                                               │  OCCUPATION MATCHES /   │
                                               │  CAREER RECOMMENDATIONS │
                                               └─────────────────────────┘
---

## LLM Resilience & Fallback Engine

To guarantee zero downtime during API outages or rate limits, the LLM client executes an automatic failover strategy:

       ┌────────────────────────┐
       │  User Dialogue Input   │
       └───────────┬────────────┘
                   │
                   ▼
       ┌────────────────────────┐
       │  Backend Session API   │
       └───────────┬────────────┘
                   │
                   ▼
       ┌────────────────────────┐
       │      call_llm.py       │
       └───────────┬────────────┘
                   │
         ┌─────────┴─────────┐
         │                   │
  
    (1. Primary)     (2. Fallback on Error)
         
         │                   │
         ▼                   ▼
    ┌─────────────────┐ ┌───────────────────┐
    │    Groq API     │ │    Gemini API     │
    │ (gpt-oss-120b)  │ │(gemini-3.6-flash) │
    └────────┬────────┘ └─────────┬─────────┘
         │                    │
         │     (Success)      │
         └─────────┬──────────┘
                   │
                   ▼
      
       ┌────────────────────────┐
       │  Return Output String  │
       └────────────────────────┘

---

## Core Technical Principles
* **Fail Loud, Not Silent:** If LLM inference fails twice, return neutral scores with `"inference_failed": true`.
* **Injection Resistance:** Treat all user input inside transcripts strictly as data, never as executable commands.
* **Schema Validation:** Enforce strict float checks (0.0 to 1.0) on all 6 required dimension keys.
