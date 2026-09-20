"""
Kindling – Chat / Intake API
Endpoints:
  POST /api/chat/start   → { session_id, opening_question }
  POST /api/chat/message → { reply, question_index, total_questions }
  GET  /api/chat/session/{session_id} → { session_id, total_messages, user_messages_count, transcript }

Review 2 additions (additive only):
  POST /api/events/log        → log custom UI / interaction events (TCP-41)
  GET  /api/dashboard/metrics → aggregated analytics for dashboard (TCP-51 / TCP-52)
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Dict, Any  # [NEW FOR REVIEW 2]

# 1. Locate folders and add BOTH backend and ai_core to sys.path
BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent

sys.path.append(str(BACKEND_DIR))            # [FIX]: Fixes 'No module named db'
sys.path.append(str(ROOT_DIR / "ai_core"))  # Fixes 'No module named call_llm'
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
    # [NEW FOR REVIEW 2] TCP-41 / TCP-52
    log_event,
    get_dashboard_metrics,
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
    "Thanks for sharing all of that. I've got a good sense of what draws "
    "you in."
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


# [NEW FOR REVIEW 2] TCP-41: Request model for custom event logging
class EventLogRequest(BaseModel):
    session_id: str
    event_type: str
    event_data: Optional[Dict[str, Any]] = None


# ── Endpoints ─────────────────────────────────────────────────

@app.post("/api/chat/start", response_model=StartResponse)
def chat_start() -> StartResponse:
    """Creates a new session, logs the opening question, and returns it."""
    # 1. Generate a new session in SQLite
    session_id = create_session()

    # 2. Store the opening question as an assistant message in DB
    add_message(session_id, "assistant", OPENING_QUESTION)

    # [NEW FOR REVIEW 2] TCP-40 / TCP-41: Log session start event
    log_event(session_id, "session_started", {"source": "api", "max_turns": TOTAL_QUESTIONS})

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

    # [NEW FOR REVIEW 2] TCP-40 / TCP-41: Log that a user message was sent
    log_event(
        req.session_id,
        "message_sent",
        {"turn": question_index, "character_count": len(req.message)},
    )

    # 4. Check if we reached the question cap
    if question_index >= TOTAL_QUESTIONS:
        add_message(req.session_id, "assistant", CLOSING_MESSAGE)

        # [NEW FOR REVIEW 2] TCP-40 / TCP-41: Log session completion
        log_event(
            req.session_id,
            "session_completed",
            {"total_turns": TOTAL_QUESTIONS},
        )

        return MessageResponse(
            reply=CLOSING_MESSAGE,
            question_index=TOTAL_QUESTIONS,
            total_questions=TOTAL_QUESTIONS,
        )

    # 5. Generate LLM follow-up using Sruthi's real wrapper
    history = get_messages(req.session_id)
    try:
        reply = call_llm(messages=history, system_prompt=FOLLOWUP_SYSTEM_PROMPT)
    except Exception as e:
        print(f"\n[LLM ERROR]: {e}\n") 
        reply = "Sorry, I'm having trouble responding right now — try again in a moment."

    # 6. Log assistant follow-up
    add_message(req.session_id, "assistant", reply)

    # [NEW FOR REVIEW 2] TCP-40 / TCP-41: Log assistant follow-up generation
    log_event(
        req.session_id,
        "followup_generated",
        {"turn": question_index, "reply_length": len(reply)},
    )

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


# =====================================================================
# [NEW FOR REVIEW 2] TELEMETRY & DASHBOARD ENDPOINTS
# TCP-41, TCP-51, TCP-52
# =====================================================================

@app.post("/api/events/log")
def record_event(req: EventLogRequest):
    """
    TCP-41: Endpoint for frontend UI to log custom interaction events
    (e.g. career_card_clicked, filter_applied, tab_switched).
    """
    if not session_exists(req.session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    log_event(req.session_id, req.event_type, req.event_data)
    return {
        "status": "logged",
        "session_id": req.session_id,
        "event_type": req.event_type,
    }


@app.get("/api/dashboard/metrics")
def get_metrics():
    """
    TCP-51 / TCP-52: Returns aggregated system metrics for the
    analytics / admin dashboard view.
    """
    metrics = get_dashboard_metrics()
    return {
        "status": "success",
        "metrics": metrics,
    }