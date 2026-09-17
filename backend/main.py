"""
Kindling – Chat / Intake API
Endpoints:
  POST /api/chat/start   → { session_id, opening_question }
  POST /api/chat/message → { reply, question_index, total_questions }
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

# 1. Locate root folder and load .env BEFORE importing call_llm
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))
load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 2. Import DB helpers and Sruthi's real LLM wrapper
from db import (
    init_db,
    create_session,
    add_message,
    get_messages,
    count_user_messages,
    session_exists,
)
from call_llm import call_llm

# ── Constants ─────────────────────────────────────────────────

OPENING_QUESTION = "What have you been curious about lately — even something small?"
TOTAL_QUESTIONS = 7

# System prompt for LLM follow-ups (enforces Design Principle #3: No judgment!)
FOLLOWUP_SYSTEM_PROMPT = """\
You are a warm, curious guide helping a young adult explore what genuinely \
interests them. Ask exactly ONE short follow-up question (under 25 words).

Rules:
- Gently probe toward what draws them to the *activity* (e.g., movement, rhythm, \
  building, organizing, analyzing, creating).
- NEVER act like a therapist or counselor. If the user mentions stress, anxiety, \
  or personal pain, acknowledge it warmly without digging into their feelings or trauma.
- Never evaluate, judge, score, or label their interests. \
  No phrases like "that's great," "you seem good at," or "that shows you're creative."
- If the user says "I don't know" or "it just makes me happy," do not ask "why" again. \
  Instead, shift to a concrete or sensory detail (e.g., "Do you prefer dancing alone or in a group?").
- Never steer toward a specific career or job title. Stay open-ended.
- Output ONLY the question — no preamble, no commentary."""

CLOSING_MESSAGE = (
    "Thanks for sharing all of that — I've got a good sense of what draws "
    "you in. Head over to the Inference page to see what we noticed."
)

# ── FastAPI App Setup ─────────────────────────────────────────

app = FastAPI(title="Kindling Chat API")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    """Runs automatically when the web server starts up."""
    init_db()


# ── Request / Response Pydantic Schemas ───────────────────────

class StartResponse(BaseModel):
    session_id: str
    opening_question: str


class MessageRequest(BaseModel):
    session_id: str
    message: str


class MessageResponse(BaseModel):
    reply: str
    question_index: int
    total_questions: int


# ── Endpoints ─────────────────────────────────────────────────

@app.post("/api/chat/start", response_model=StartResponse)
def chat_start() -> StartResponse:
    """Creates a new session, logs the opening question, and returns it."""
    # 1. Generate a new session in SQLite
    session_id = create_session()

    # 2. Store the opening question as an assistant message in DB
    add_message(session_id, "assistant", OPENING_QUESTION)

    # 3. Return the JSON response matching Gokul's contract
    return StartResponse(
        session_id=session_id,
        opening_question=OPENING_QUESTION,
    )


@app.post("/api/chat/message", response_model=MessageResponse)
def chat_message(req: MessageRequest) -> MessageResponse:
    """Accepts a user message, logs it, and returns the next LLM follow-up or closing message."""

    # 1. Validate session
    if not session_exists(req.session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    # 2. Log user message
    add_message(req.session_id, "user", req.message)

    # 3. Determine question index
    question_index = count_user_messages(req.session_id)

    # 4. Check if we reached the question cap
    if question_index >= TOTAL_QUESTIONS:
        add_message(req.session_id, "assistant", CLOSING_MESSAGE)
        return MessageResponse(
            reply=CLOSING_MESSAGE,
            question_index=TOTAL_QUESTIONS,
            total_questions=TOTAL_QUESTIONS,
        )

    # 5. Generate LLM follow-up using Sruthi's real wrapper
    history = get_messages(req.session_id)
    reply = call_llm(messages=history, system_prompt=FOLLOWUP_SYSTEM_PROMPT)

    # 6. Log assistant follow-up
    add_message(req.session_id, "assistant", reply)

    return MessageResponse(
        reply=reply,
        question_index=question_index,
        total_questions=TOTAL_QUESTIONS,
    )

@app.get("/api/chat/session/{session_id}")
def get_session_history(session_id: str):
    """Returns the full conversation transcript for a given session."""
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    history = get_messages(session_id)
    user_count = count_user_messages(session_id)

    return {
        "session_id": session_id,
        "total_messages": len(history),
        "user_messages_count": user_count,
        "transcript": history,
    }