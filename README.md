# Kindling

A career-discovery system that infers a person's interests from how they explore and communicate, not from a self-report quiz.

## Overview

Career guidance tools like the O*NET Interest Profiler ask people to say what they enjoy before they've actually tried it. Kindling takes a different approach : It infers interest from real behavior during exploration (time spent, whether someone returns to something, depth of follow-up questions), scores it using a large language model, and matches it against real occupational data from the U.S. Department of Labor's O*NET database.

## Tech stack

- Backend : FastAPI (Python)
- LLM : Groq (primary) + Gemini (fallback)
- Retrieval : FAISS
- Storage : SQLite
- Explainability : SHAP
- Dataset : O*NET 31.0 (U.S. Dept. of Labor, CC-BY 4.0)
- Hosting : Render (free tier)

## Setup

git clone https://github.com/Priya-on-loop/Kindling.git
cd Kindling
pip install -r requirements.txt

Create a `.env` file in the project root (never commit this, it's already covered by `.gitignore`) :

GROQ_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here


## Team

Priya Shill, Sruthi G S, Gokul V S, Aleena Philip Shaji

## Project tracking

Jira dashboard (status overview + Review 1 progress) : https://priyainloop.atlassian.net/jira/dashboards/10003

Jira backlog (full sprint board, all issues) : https://priyainloop.atlassian.net/jira/software/projects/TCP/boards/4/backlog

## License

MIT License