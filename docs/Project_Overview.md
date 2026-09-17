# Kindling: Conversational Career Exploration Engine

Kindling is an AI-driven career guidance platform that evaluates conversational dialogue to uncover student behavioral interests and map them to a 923-occupation career graph.

---

## 1. Problem Statement
Traditional career guidance tools suffer from significant limitations:
* **Stated vs. Revealed Passions:** Students struggle to self-report interests accurately ("I like science").
* **Static Surveys:** Tools like O*NET Interest Profiler use rigid, multi-question surveys that feel like tests.
* **Lack of Context Grounding:** Generic chatbots give ungrounded career advice and hallucinate stats.

---

## 2. Proposed Solution
Kindling replaces static forms with an ongoing, natural dialogue assistant. Instead of asking what students *claim* to like, Kindling scores *how* students communicate across **6 behavioral dimensions**:

1. `builds_tinkers` (Hands-on experimentation / modification)
2. `investigates_why` (Root-cause curiosity and follow-up questioning)
3. `creates_expresses` (Artistic and creative expression)
4. `works_with_people` (Empathy, teaching, and helping others)
5. `organizes_systems` (Structure, planning, and categorizing)
6. `leads_persuades` (Leadership, persuasion, and influence)

---

## 3. Team Roles & Responsibilities
* **Aleena (Data Engineering):** O*NET database processing and 923-occupation career graph clustering using Gaussian Mixture Models (GMM).
* **Sruthi (AI Core):** Multi-provider LLM wrapper with automatic failover (`call_llm.py`), 6D behavioral prompt design, and prompt-injection defense (`inference_prompt.py`).
* **Priya (Backend Engineering):** Session API layer, SQLite database integration (`kindling.db`), and state management (`db.py`, `main.py`).
* **Gokul (Frontend & UI):** User experience design and interactive student dialogue prototypes in Figma.

---

## 4. Academic & Theoretical Grounding
1. **Holland's Theory of Vocational Choice (RIASEC):** Maps personality traits directly to work environments. Kindling's 6 dimensions align with Holland's Realistic, Investigative, Artistic, Social, Conventional, and Enterprising domains.
2. **Krumboltz's Planned Happenstance Theory:** Recognizes that career interests emerge dynamically through curiosity and unplanned exploration.
3. **Samuelson's Revealed Preference Theory:** Evaluates actual behavioral tendencies rather than self-reported statements.
4. **Deci & Ryan's Self-Determination Theory (SDT):** Fosters student intrinsic motivation through autonomous exploration.