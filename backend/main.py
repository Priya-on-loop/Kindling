"""
Kindling – Chat / Intake & Dashboard API
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Dict, Any

BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent

sys.path.append(str(BACKEND_DIR))            # Fixes 'No module named db'
sys.path.append(str(ROOT_DIR / "ai_core"))  # Fixes 'No module named call_llm'
sys.path.append(str(ROOT_DIR / "Scripts"))  # Fixes 'No module named matching'
load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
    get_latest_inference_scores,
)

from backend.shap_explainer import explain_match
from call_llm import call_llm
from score_session import score_session
from rag_explanation import get_top_tasks_for_occupation, compose_explanation, validate_explanation
from matching import match_occupations, load_career_graph

OPENING_QUESTION = "What have you been curious about lately — even something small?"
TOTAL_QUESTIONS = 7

REQUIRED_DIMENSIONS = {
    "builds_tinkers",
    "investigates_why",
    "creates_expresses",
    "works_with_people",
    "organizes_systems",
    "leads_persuades",
}

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

app = FastAPI(title="Kindling Chat API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()

# ── Schemas ───────────────────────────────────────────────────

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

class ProfileUpdateRequest(BaseModel):
    session_id: str
    inference: Dict[str, float]

# ── Signals API (Preserved 100%) ───────────────────────────────

@app.post("/api/chat/start", response_model=StartResponse)
def chat_start() -> StartResponse:
    session_id = create_session()
    add_message(session_id, "assistant", OPENING_QUESTION)
    log_event(session_id, "session_started", {"source": "api", "max_turns": TOTAL_QUESTIONS})
    return StartResponse(session_id=session_id, opening_question=OPENING_QUESTION)

@app.post("/api/chat/message", response_model=MessageResponse)
def chat_message(req: MessageRequest) -> MessageResponse:
    if not session_exists(req.session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    add_message(req.session_id, "user", req.message)
    question_index = count_user_messages(req.session_id)

    log_event(req.session_id, "message_sent", {"turn": question_index, "character_count": len(req.message)})

    # Guard: If question cap reached or exceeded
    if question_index >= TOTAL_QUESTIONS:
        add_message(req.session_id, "assistant", CLOSING_MESSAGE)

        # [FIX 1]: ONLY compute scores on turn 7 EXACTLY.
        # Messages sent AFTER turn 7 will not re-trigger scoring or overwrite user profile edits.
        if question_index == TOTAL_QUESTIONS:
            log_event(req.session_id, "session_completed", {"total_turns": TOTAL_QUESTIONS})
            full_transcript = get_messages(req.session_id)
            scores = score_session(full_transcript)
            log_event(req.session_id, "score_computed", scores)
            print(f"[session {req.session_id}] initial scoring completed & saved: {scores}")

        return MessageResponse(reply=CLOSING_MESSAGE, question_index=TOTAL_QUESTIONS, total_questions=TOTAL_QUESTIONS)

    history = get_messages(req.session_id)
    try:
        reply = call_llm(messages=history, system_prompt=FOLLOWUP_SYSTEM_PROMPT)
    except Exception as e:
        print(f"\n[LLM ERROR]: {e}\n") 
        reply = "Sorry, I'm having trouble responding right now — try again in a moment."

    add_message(req.session_id, "assistant", reply)
    log_event(req.session_id, "followup_generated", {"turn": question_index, "reply_length": len(reply)})

    return MessageResponse(reply=reply, question_index=question_index, total_questions=TOTAL_QUESTIONS)

@app.get("/api/chat/session/{session_id}")
def get_session_history(session_id: str):
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    history = get_messages(session_id)
    user_count = count_user_messages(session_id)
    return {"session_id": session_id, "total_messages": len(history), "user_messages_count": user_count, "transcript": history}

# ── Inference API Endpoint ────────────────────────────────────

@app.get("/api/chat/inference/{session_id}")
def get_inference_scores(session_id: str):
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    scores = get_latest_inference_scores(session_id)
    if scores is None:
        raise HTTPException(status_code=404, detail="Inference scores are not available yet. Please complete the 7-question chat.")

    clean_scores = {k: v for k, v in scores.items() if k != "inference_failed"}
    
    # [FIX 2]: Explicitly surface inference_failed flag
    return {
        "status": "success",
        "session_id": session_id,
        "inference": clean_scores,
        "inference_failed": scores.get("inference_failed", False)
    }

# ── Career Graph API Endpoint ─────────────────────────────────

@app.get("/api/career-graph/{session_id}")
def get_career_graph(session_id: str, top_k: int = 5):
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    scores = get_latest_inference_scores(session_id)
    if scores is None:
        raise HTTPException(status_code=404, detail="Inference scores are not available yet. Please complete the 7-question chat.")

    riasec_cols = ["creates_expresses", "organizes_systems", "investigates_why", "builds_tinkers", "works_with_people", "leads_persuades"]
    student_vector = [float(scores.get(col, 0.0)) for col in riasec_cols]

    faiss_matches = match_occupations(student_vector, top_k=top_k)
    all_occupations = {occ["id"]: occ for occ in load_career_graph()}

    enriched_careers = []
    for match in faiss_matches:
        occ_id = match["id"]
        full_occ = all_occupations.get(occ_id, {})
        enriched_careers.append({
            "occupation_id": occ_id,
            "title": match["title"],
            "match_score": round(match["similarity"], 2),
            "family": str(full_occ.get("family", "General")),
            "description": full_occ.get("description", ""),
            "tasks": full_occ.get("sample_tasks", [])
        })

    return {
        "status": "success",
        "session_id": session_id,
        "careers": enriched_careers
    }

# ── User Control & Profile Endpoints ─────────────────────────

@app.get("/api/user/profile/{session_id}")
def get_user_profile(session_id: str):
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    scores = get_latest_inference_scores(session_id)
    if scores is None:
        raise HTTPException(status_code=404, detail="Inference scores are not available yet. Please complete the 7-question chat.")

    clean_scores = {k: v for k, v in scores.items() if k != "inference_failed"}

    # [FIX 2]: Explicitly surface inference_failed flag
    return {
        "status": "success",
        "session_id": session_id,
        "inference": clean_scores,
        "inference_failed": scores.get("inference_failed", False)
    }

@app.post("/api/user/profile/update")
def update_user_profile(req: ProfileUpdateRequest):
    if not session_exists(req.session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    inf = req.inference

    # [FIX 3]: Require all 6 dimensions
    missing_keys = REQUIRED_DIMENSIONS - set(inf.keys())
    if missing_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required dimensions: {list(missing_keys)}. All 6 dimensions must be provided."
        )

    # [FIX 3]: Validate float range [0.0, 1.0] for all dimensions
    validated_inference = {}
    for k in REQUIRED_DIMENSIONS:
        v = inf[k]
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0.0 or v > 1.0:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid value for '{k}': {v}. All dimension values must be numbers between 0.0 and 1.0."
            )
        validated_inference[k] = float(v)

    # Log validated edit event
    log_event(req.session_id, "profile_updated", validated_inference)

    return {
        "status": "success",
        "session_id": req.session_id,
        "message": "User profile successfully updated",
        "inference": validated_inference
    }

# ── Telemetry & Analytics Endpoints ───────────────────────────

@app.post("/api/events/log")
def record_event(req: EventLogRequest):
    if not session_exists(req.session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    log_event(req.session_id, req.event_type, req.event_data)
    return {"status": "logged", "session_id": req.session_id, "event_type": req.event_type}

@app.get("/api/dashboard/metrics")
def get_metrics():
    return {"status": "success", "metrics": get_dashboard_metrics()}

@app.get("/api/dashboard/timeline/{session_id}")
def get_timeline(session_id: str):
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "timeline": get_session_timeline(session_id)}

@app.get("/api/dashboard/field-summary")
def get_field_metrics():
    return {"status": "success", "field_summary": get_field_summary()}

# ── SHAP Match Explainer Endpoint ────────────────────────────────

@app.get("/api/chat/explain/{session_id}/{occupation_id}")
def get_match_explanation(session_id: str, occupation_id: str):
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    scores = get_latest_inference_scores(session_id)
    if not scores:
        raise HTTPException(
            status_code=404,
            detail="Inference scores are not available yet. Please complete the 7-question chat."
        )

    student_vector = [
        float(scores.get("creates_expresses", 0.0)),
        float(scores.get("organizes_systems", 0.0)),
        float(scores.get("investigates_why", 0.0)),
        float(scores.get("builds_tinkers", 0.0)),
        float(scores.get("works_with_people", 0.0)),
        float(scores.get("leads_persuades", 0.0)),
    ]

    try:
        shap_explanation = explain_match(student_vector, occupation_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Explanation generation failed: {str(e)}")

    all_occupations = {occ["id"]: occ for occ in load_career_graph()}
    occ_record = all_occupations.get(occupation_id)

    narrative = None
    narrative_validation = None
    if occ_record:
        tasks = get_top_tasks_for_occupation(occupation_id)
        if tasks:
            narrative = compose_explanation(occ_record["title"], tasks)
            narrative_validation = validate_explanation(narrative, tasks)

    return {
        "status": "success",
        "session_id": session_id,
        "explanation": shap_explanation,
        "narrative": narrative,
        "narrative_validation": narrative_validation,
    }