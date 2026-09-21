"""
Kindling – Chat / Intake API
Endpoints:
  POST /api/chat/start   → { session_id, opening_question }
  POST /api/chat/message → { reply, question_index, total_questions }
  GET  /api/chat/session/{session_id} → { session_id, total_messages, user_messages_count, transcript }

Review 2 additions (additive only):
  POST /api/events/log                    → log custom UI / interaction events (TCP-41)
  GET  /api/dashboard/metrics             → aggregated analytics for dashboard (TCP-51 / TCP-52)
  GET  /api/dashboard/timeline/{session_id}→ chronological timeline of user turns and events (TCP-54)
  GET  /api/dashboard/field-summary       → summary of interaction types (TCP-53)

Gokul Frontend Contracts:
  GET  /api/chat/inference/{session_id}           → fetch already-computed 6D scores from SQLite
  GET  /api/chat/explain/{session_id}/{occ_id}   → SHAP breakdown of score contributions
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Dict, Any

# 1. Locate folders and add backend, ai_core, and Scripts to sys.path
BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent

sys.path.append(str(BACKEND_DIR))            # Fixes 'No module named db'
sys.path.append(str(ROOT_DIR / "ai_core"))  # Fixes 'No module named call_llm'
sys.path.append(str(ROOT_DIR / "Scripts"))  # Fixes 'No module named matching'
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
    log_event,
    get_dashboard_metrics,
    get_session_timeline,
    get_field_summary,
    get_latest_inference_scores,  # [ADDED FOR GOKUL]
)
from backend.shap_explainer import explain_match
from call_llm import call_llm
from score_session import score_session

# ── Constants ─────────────────────────────────────────────────

OPENING_QUESTION = "What have you been curious about lately — even something small?"
TOTAL_QUESTIONS = 7

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


class EventLogRequest(BaseModel):
    session_id: str
    event_type: str
    event_data: Optional[Dict[str, Any]] = None


# ── Endpoints ─────────────────────────────────────────────────

@app.post("/api/chat/start", response_model=StartResponse)
def chat_start() -> StartResponse:
    """Creates a new session, logs the opening question, and returns it."""
    session_id = create_session()
    add_message(session_id, "assistant", OPENING_QUESTION)
    log_event(session_id, "session_started", {"source": "api", "max_turns": TOTAL_QUESTIONS})

    return StartResponse(
        session_id=session_id,
        opening_question=OPENING_QUESTION,
    )


@app.post("/api/chat/message", response_model=MessageResponse)
def chat_message(req: MessageRequest) -> MessageResponse:
    """Accepts a user message, logs it, and returns the next LLM follow-up or closing message."""

    if not session_exists(req.session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    add_message(req.session_id, "user", req.message)
    question_index = count_user_messages(req.session_id)

    log_event(
        req.session_id,
        "message_sent",
        {"turn": question_index, "character_count": len(req.message)},
    )

    if question_index >= TOTAL_QUESTIONS:
        add_message(req.session_id, "assistant", CLOSING_MESSAGE)

        log_event(
            req.session_id,
            "session_completed",
            {"total_turns": TOTAL_QUESTIONS},
        )

        full_transcript = get_messages(req.session_id)
        scores = score_session(full_transcript)
        log_event(req.session_id, "score_computed", scores)
        print(f"[session {req.session_id}] scored & saved: {scores}")

        return MessageResponse(
            reply=CLOSING_MESSAGE,
            question_index=TOTAL_QUESTIONS,
            total_questions=TOTAL_QUESTIONS,
        )

    history = get_messages(req.session_id)
    try:
        reply = call_llm(messages=history, system_prompt=FOLLOWUP_SYSTEM_PROMPT)
    except Exception as e:
        print(f"\n[LLM ERROR]: {e}\n") 
        reply = "Sorry, I'm having trouble responding right now — try again in a moment."

    add_message(req.session_id, "assistant", reply)

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
# [GOKUL CONTRACT]: INFERENCE SCORE RETRIEVAL
# =====================================================================

@app.get("/api/chat/inference/{session_id}")
def get_inference_scores(session_id: str):
    """
    Retrieves the already-computed 6D inference scores from SQLite events table
    without re-running the LLM scoring engine.
    """
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    scores = get_latest_inference_scores(session_id)

    if scores is None:
        raise HTTPException(
            status_code=404, 
            detail="Inference scores not found for this session yet."
        )

    return {
        "status": "success",
        "session_id": session_id,
        "scores": scores
    }


# =====================================================================
# TELEMETRY & DASHBOARD ENDPOINTS (TCP-41, TCP-51, TCP-52, TCP-53, TCP-54)
# =====================================================================

@app.post("/api/events/log")
def record_event(req: EventLogRequest):
    """TCP-41: Endpoint for frontend UI to log custom interaction events."""
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
    """TCP-51 / TCP-52: Returns aggregated system metrics for dashboard."""
    metrics = get_dashboard_metrics()
    return {
        "status": "success",
        "metrics": metrics,
    }


@app.get("/api/dashboard/timeline/{session_id}")
def get_timeline(session_id: str):
    """TCP-54: Returns a chronological timeline of all user turns and events."""
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    timeline = get_session_timeline(session_id)
    return {"session_id": session_id, "total_items": len(timeline), "timeline": timeline}


@app.get("/api/dashboard/field-summary")
def get_field_metrics():
    """TCP-53: Returns interaction distribution per field/type for dashboard visuals."""
    summary = get_field_summary()
    return {"status": "success", "field_summary": summary}


# =====================================================================
# SHAP MATCH EXPLAINER ENDPOINT
# =====================================================================

@app.get("/api/chat/explain/{session_id}/{occupation_id}")
def get_match_explanation(session_id: str, occupation_id: str):
    """
    Uses Aleena's SHAP explainer (explain_match) to break down feature contributions.
    """
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    full_transcript = get_messages(session_id)
    scores = score_session(full_transcript)
    
    student_vector = [
        float(scores.get("creates_expresses", 0.0)),
        float(scores.get("organizes_systems", 0.0)),
        float(scores.get("investigates_why", 0.0)),
        float(scores.get("builds_tinkers", 0.0)),
        float(scores.get("works_with_people", 0.0)),
        float(scores.get("leads_persuades", 0.0)),
    ]

    try:
        explanation = explain_match(student_vector, occupation_id)
        return {"status": "success", "session_id": session_id, "explanation": explanation}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Explanation generation failed: {str(e)}")