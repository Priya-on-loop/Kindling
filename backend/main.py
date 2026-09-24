"""
Kindling – Chat / Intake & Dashboard API
Phase 1: 7-Turn Structured Intake & Scoring
Phase 2: Open Exploration & Mentorship (No Scoring Impact)
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from typing import Optional, Dict, Any, List

BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent

sys.path.append(str(BACKEND_DIR))            # Fixes 'No module named db'
sys.path.append(str(ROOT_DIR / "ai_core"))  # Fixes 'No module named call_llm'
sys.path.append(str(ROOT_DIR / "Scripts"))  # Fixes 'No module named matching'
load_dotenv(ROOT_DIR / ".env")

import bcrypt
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
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_sessions_for_user,
    set_session_title,
    get_session_user_id,
    count_pinned_sessions,
    set_session_pinned,
    delete_session,
    delete_empty_sessions_for_user,
)

from backend.shap_explainer import explain_match
from call_llm import call_llm
from score_session import score_session
from rag_explanation import get_top_tasks_for_occupation, compose_explanation, validate_explanation
from matching import match_occupations, load_career_graph, MAX_RESULTS
from title_generator import generate_title, build_fallback_title
from career_tree import build_career_tree
from tree_enrichment import enrich_tree_with_ai

TITLE_FALLBACK_TURN = 1  # a real title-ish placeholder the moment the first message lands
TITLE_AI_TURN = 3        # upgrade to a real generated title once there's enough to work with


class OccupationContext(BaseModel):
    """
    What career-graph.js stores in sessionStorage when "Explore this
    in a conversation" is clicked — the same real title/description/
    tasks already shown in the node's own detail panel, nothing
    invented. Optional so ordinary (non-occupation-grounded) messages
    are unaffected.
    """
    title: str
    description: Optional[str] = None
    tasks: Optional[List[str]] = None


def build_context_note(context: Optional[OccupationContext]) -> str:
    """
    Turns a real occupation the student just viewed on Career Graph
    into a system-prompt addition, so "this job" in their next
    message actually resolves to it instead of the model answering
    about nothing in particular (or, worse, an unrelated occupation
    from its own training data).
    """
    if not context:
        return ""

    lines = [f"\n\nThe student just viewed this real occupation on Career Graph: {context.title}."]
    if context.description:
        lines.append(f"Description: {context.description}")
    if context.tasks:
        lines.append("Real sample tasks for this occupation: " + "; ".join(context.tasks[:5]))
    lines.append(
        "If their next message could reasonably be about this occupation "
        "(e.g. it says \"this job\", \"it\", or otherwise doesn't name a "
        "different one), answer about THIS occupation specifically, using "
        "only the real details above — never a different or invented one."
    )
    return "\n".join(lines)


def set_fallback_title(session_id: str) -> None:
    """
    Cheap, no-LLM title set the moment the first real user message
    lands (see ai_core/title_generator.py's build_fallback_title —
    strips a filler opener, trims to ~40 real chars at a word
    boundary, capitalizes). A thread never shows the raw "New
    conversation" placeholder once it has a real message, even if
    the later AI upgrade below never runs for some reason.
    """
    messages = get_messages(session_id)
    first_user = next((m["content"] for m in messages if m["role"] == "user"), "").strip()
    set_session_title(session_id, build_fallback_title(first_user))


def maybe_generate_title(session_id: str) -> None:
    """
    Upgrades the cheap fallback above to a real AI-generated title
    (ai_core/title_generator.py) once there's enough conversation to
    work with, and once more at intake completion since the fuller
    transcript can suggest a better title. On failure, falls back to
    the same real, non-fabricated trimmed-message title — never
    leaves the thread untitled.
    """
    messages = get_messages(session_id)
    title = generate_title(messages)

    if title is None:
        first_user = next((m["content"] for m in messages if m["role"] == "user"), "").strip()
        title = build_fallback_title(first_user)

    set_session_title(session_id, title)

OPENING_QUESTION = "What have you been curious about lately — even something small?"
TOTAL_PHASE1_QUESTIONS = 7

REQUIRED_DIMENSIONS = {
    "builds_tinkers",
    "investigates_why",
    "creates_expresses",
    "works_with_people",
    "organizes_systems",
    "leads_persuades",
}

# --- PROMPTS ---

# Phase 1 Prompt: Structured Follow-ups (Turns 1-7)
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

# Phase 2 Prompt: Open Exploration & Mentorship (Turns 8+)
PHASE2_SYSTEM_PROMPT = """\
You are Kindling, a warm, encouraging mentor talking with a HIGH-SCHOOL \
STUDENT who is casually exploring a possible interest or direction. They are \
not a professional planning a curriculum, not a college student choosing a \
major, and have not committed to anything — they're just curious.

Rules:
- Keep answers SHORT: 3-5 sentences maximum, unless the student explicitly \
  asks you to go deeper or for more detail.
- Use plain, everyday language a high schooler would use with a friend. \
  No jargon dumps, no numbered or bulleted lists of prerequisites, no dense \
  technical breakdowns, and no naming tools, software, or coursework without \
  explaining in one plain phrase why it matters.
- If a question is genuinely broad or technical (like "what math do I need for \
  this?"), give ONE simple, honest, encouraging answer first — not an exhaustive \
  syllabus. Only add more technical detail if the student asks a follow-up \
  asking for it.
- Answer the student's actual question directly and conversationally, the way \
  a friendly mentor would explain something over coffee — never the way a \
  textbook, a curriculum planner, or a job-requirements page would.
- Help them explore hobbies, skills, projects, and general fields they are \
  curious about.
- Be encouraging and open-ended. Do not push them toward rigid job titles \
  unless they specifically ask.
- Keep the tone casual, warm, and human — like a mentor, not a manual."""

CLOSING_MESSAGE = (
    "Thanks for sharing all of that! I've got a good sense of what draws you in. "
    "Your initial career profile is complete! You can view your career matches now, "
    "or feel free to keep chatting with me to explore any specific activities or questions further."
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

@app.get("/")
@app.get("/health")
def root_health():
    return {
        "status": "ok",
        "service": "Kindling Backend API",
        "docs": "https://kindling-backend.onrender.com/docs"
    }

# ── Schemas ───────────────────────────────────────────────────

class StartRequest(BaseModel):
    # Optional: the signed-in user's token (their row id — see
    # AuthResponse). Anonymous callers omit it or send {}, exactly
    # as before; the frontend already sends body: {} unconditionally.
    token: Optional[str] = None

class StartResponse(BaseModel):
    session_id: str
    opening_question: str

class MessageRequest(BaseModel):
    session_id: str
    message: str
    context: Optional[OccupationContext] = None

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

class TraitDecisionRequest(BaseModel):
    session_id: str
    trait: str
    action: str
    override_value: Optional[float] = None

class SignupRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    token: str
    email: str

# ── Authentication ────────────────────────────────────────────
# Real accounts, additive to the existing anonymous session model.
# Nothing below gates Explore/Inference/Career Graph — those keep
# working entirely without a token, exactly as before.

MIN_PASSWORD_LENGTH = 8

@app.post("/api/auth/signup", response_model=AuthResponse)
def signup(req: SignupRequest) -> AuthResponse:
    email = req.email.strip()

    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Enter a valid email address.")

    if len(req.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )

    password_hash = bcrypt.hashpw(
        req.password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    user_id = create_user(email, password_hash)

    if user_id is None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    return AuthResponse(token=user_id, email=email.strip().lower())

@app.post("/api/auth/login", response_model=AuthResponse)
def login(req: LoginRequest) -> AuthResponse:
    user = get_user_by_email(req.email)

    # 1. No account exists with this email
    if user is None:
        raise HTTPException(
            status_code=404, 
            detail="No account found with this email. Please create an account first."
        )

    # 2. Check password
    password_matches = bcrypt.checkpw(
        req.password.encode("utf-8"),
        user["password_hash"].encode("utf-8")
    )

    if not password_matches:
        raise HTTPException(
            status_code=401, 
            detail="Incorrect password. Please try again."
        )

    return AuthResponse(token=user["id"], email=user["email"])

def resolve_user_id(token: Optional[str]) -> Optional[str]:
    """
    A token is just a user's row id (see AuthResponse) — no expiry,
    no separate token table. Resolves to a real user id only if one
    actually exists; an invalid/forged token silently resolves to
    None rather than erroring, since linking a session to a user is
    additive, not a security boundary.
    """
    if not token:
        return None

    user = get_user_by_id(token)
    return user["id"] if user else None

@app.get("/api/auth/sessions")
def list_user_sessions(token: str):
    user_id = resolve_user_id(token)

    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or missing token.")

    sessions = get_sessions_for_user(user_id)

    return {
        "status": "success",
        "sessions": [
            {
                "session_id": row["session_id"],
                "created_at": row["created_at"],
                "label": row["title"] or "New conversation",
                "pinned": bool(row["pinned"]),
                "pinned_at": row["pinned_at"],
            }
            for row in sessions
        ]
    }

# ── Signals API (Phase 1 & Phase 2 Ingestion) ───────────────────

@app.post("/api/chat/start", response_model=StartResponse)
def chat_start(req: StartRequest = StartRequest()) -> StartResponse:
    user_id = resolve_user_id(req.token)

    # Real cleanup, not just hiding: a "New thread" click that never
    # got a first message doesn't leave a row behind once the user
    # starts (or re-starts) another one — clicking New Thread
    # repeatedly never accumulates empty sessions in the database.
    if user_id:
        delete_empty_sessions_for_user(user_id)

    session_id = create_session(user_id=user_id)
    add_message(session_id, "assistant", OPENING_QUESTION)
    log_event(session_id, "session_started", {"source": "api", "max_turns": TOTAL_PHASE1_QUESTIONS})
    return StartResponse(session_id=session_id, opening_question=OPENING_QUESTION)


class PinRequest(BaseModel):
    token: str
    pin: bool


@app.post("/api/chat/session/{session_id}/pin")
def pin_session(session_id: str, req: PinRequest):
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    user_id = resolve_user_id(req.token)
    owner_id = get_session_user_id(session_id)
    if user_id is None or owner_id != user_id:
        raise HTTPException(status_code=403, detail="This thread doesn't belong to you.")

    if req.pin:
        if count_pinned_sessions(user_id) >= 5:
            raise HTTPException(status_code=400, detail="You can pin up to 5 threads.")
        set_session_pinned(session_id, True, datetime.now(timezone.utc).isoformat())
    else:
        set_session_pinned(session_id, False, None)

    return {"status": "success", "session_id": session_id, "pinned": req.pin}


@app.delete("/api/chat/session/{session_id}")
def delete_thread(session_id: str, token: str):
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    user_id = resolve_user_id(token)
    owner_id = get_session_user_id(session_id)
    if user_id is None or owner_id != user_id:
        raise HTTPException(status_code=403, detail="This thread doesn't belong to you.")

    # Real deletion, not a derived view: messages and events (real
    # scores, node_time, trait decisions — everything Inference,
    # Career Graph, and Reflection read) are both session_id-scoped
    # and stored nowhere else, so removing both here is the whole
    # story — see db.delete_session().
    delete_session(session_id)

    return {"status": "success", "session_id": session_id}

@app.post("/api/chat/message", response_model=MessageResponse)
def chat_message(req: MessageRequest) -> MessageResponse:
    if not session_exists(req.session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    # Save user message to DB
    add_message(req.session_id, "user", req.message)
    question_index = count_user_messages(req.session_id)

    # ─────────────────────────────────────────────────────────────
    # PHASE 1: STRUCTURED INTAKE (TURNS 1 TO 7)
    # ─────────────────────────────────────────────────────────────
    if question_index <= TOTAL_PHASE1_QUESTIONS:
        log_event(req.session_id, "message_sent", {"turn": question_index, "character_count": len(req.message)})

        if question_index == TITLE_FALLBACK_TURN:
            set_fallback_title(req.session_id)
        if question_index == TITLE_AI_TURN:
            maybe_generate_title(req.session_id)

        # Turn 7 Checkpoint: Score Phase 1 transcript ONLY
        if question_index == TOTAL_PHASE1_QUESTIONS:
            add_message(req.session_id, "assistant", CLOSING_MESSAGE)
            log_event(req.session_id, "session_completed", {"total_turns": TOTAL_PHASE1_QUESTIONS})

            # One optional refresh now that the full intake is in —
            # the thread's title may fit better with the complete
            # picture than the one generated after turn 3.
            maybe_generate_title(req.session_id)

            # Score ONLY the Phase 1 transcript (messages 1..7)
            phase1_transcript = get_messages(req.session_id)
            scores = score_session(phase1_transcript)
            log_event(req.session_id, "score_computed", scores)
            print(f"[session {req.session_id}] Phase 1 scoring completed & saved: {scores}")

            return MessageResponse(
                reply=CLOSING_MESSAGE,
                question_index=TOTAL_PHASE1_QUESTIONS,
                total_questions=TOTAL_PHASE1_QUESTIONS,
            )

        # Turns 1 to 6: Generate Phase 1 Follow-up
        history = get_messages(req.session_id)
        try:
            reply = call_llm(messages=history, system_prompt=FOLLOWUP_SYSTEM_PROMPT + build_context_note(req.context))
        except Exception as e:
            print(f"\n[LLM ERROR]: {e}\n")
            reply = "Sorry, I'm having trouble responding right now — try again in a moment."

        add_message(req.session_id, "assistant", reply)
        log_event(req.session_id, "followup_generated", {"turn": question_index, "reply_length": len(reply)})

        return MessageResponse(
            reply=reply,
            question_index=question_index,
            total_questions=TOTAL_PHASE1_QUESTIONS,
        )

    # ─────────────────────────────────────────────────────────────
    # PHASE 2: OPEN EXPLORATION (TURNS 8+)
    # NO SCORING / NO INFERENCE IMPACT — BEHAVIORAL TELEMETRY ONLY
    # ─────────────────────────────────────────────────────────────
    else:
        # Log specifically as Phase 2 telemetry event
        log_event(
            req.session_id, 
            "phase2_message", 
            {"turn": question_index, "character_count": len(req.message)}
        )

        history = get_messages(req.session_id)
        try:
            # Use Phase 2 conversational prompt
            reply = call_llm(messages=history, system_prompt=PHASE2_SYSTEM_PROMPT + build_context_note(req.context))
        except Exception as e:
            print(f"\n[PHASE 2 LLM ERROR]: {e}\n")
            reply = "I'm here to help you explore! What else would you like to talk about?"

        add_message(req.session_id, "assistant", reply)
        log_event(req.session_id, "phase2_followup", {"turn": question_index, "reply_length": len(reply)})

        # Phase 2 messages DO NOT trigger score_session()!
        return MessageResponse(
            reply=reply,
            question_index=question_index,
            total_questions=TOTAL_PHASE1_QUESTIONS,
        )

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
        raise HTTPException(
            status_code=404, 
            detail=f"Inference scores are not available yet. Please complete at least {TOTAL_PHASE1_QUESTIONS} chat turns."
        )

    clean_scores = {k: v for k, v in scores.items() if k != "inference_failed"}

    return {
        "status": "success",
        "session_id": session_id,
        "inference": clean_scores,
        "inference_failed": scores.get("inference_failed", False)
    }

# ── Career Graph API Endpoint ─────────────────────────────────

@app.get("/api/career-graph/{session_id}")
def get_career_graph(session_id: str, max_results: int = MAX_RESULTS):
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    scores = get_latest_inference_scores(session_id)
    if scores is None:
        raise HTTPException(
            status_code=404,
            detail=f"Inference scores are not available yet. Please complete at least {TOTAL_PHASE1_QUESTIONS} chat turns."
        )

    riasec_cols = ["creates_expresses", "organizes_systems", "investigates_why", "builds_tinkers", "works_with_people", "leads_persuades"]
    student_vector = [float(scores.get(col, 0.0)) for col in riasec_cols]

    # No fixed result count: every occupation above the real
    # similarity threshold is returned, capped at max_results as
    # a display safeguard (not a ranking claim). A sharply-shaped
    # profile can legitimately return far fewer than a broad one.
    faiss_matches = match_occupations(student_vector, max_results=max_results)
    all_occupations = {occ["id"]: occ for occ in load_career_graph()}

    enriched_careers = []
    for match in faiss_matches:
        occ_id = match["id"]
        full_occ = all_occupations.get(occ_id, {})

        # The occupation's own real RIASEC vector (raw O*NET importance
        # ratings, same source matching.py uses) — its dominant_area is
        # just that vector's argmax, not a separate invented category.
        occ_riasec = full_occ.get("riasec") or {}
        dominant_area = max(occ_riasec, key=occ_riasec.get) if occ_riasec else None

        # sample_tasks is now [{"task_id": "...", "text": "..."}, ...]
        # (see Scripts/add_task_ids.py) so the career tree can keep a
        # real sourceTaskId — but the "tasks" field this endpoint has
        # always returned is a plain string array, and existing
        # frontend code (explore.js's occupation-context handoff,
        # career-graph.js's task list) still expects exactly that.
        task_texts = [t["text"] for t in full_occ.get("sample_tasks", [])]

        enriched_careers.append({
            "occupation_id": occ_id,
            "title": match["title"],
            "match_score": round(match["similarity"], 2),
            "family": str(full_occ.get("family", "General")),
            "description": full_occ.get("description", ""),
            "tasks": task_texts,
            "dominant_area": dominant_area
        })

    return {
        "status": "success",
        "session_id": session_id,
        "careers": enriched_careers
    }

@app.get("/api/career-tree/{session_id}")
def get_career_tree(session_id: str):
    """
    Phase 3 of the star->tree rebuild (see career_tree.py, Phase 1,
    and tree_enrichment.py, Phase 2). A new endpoint, deliberately
    separate from /api/career-graph above — that endpoint (the flat
    star) stays exactly as-is until the frontend actually switches
    over to this one (Phase 4), so nothing currently live breaks in
    between.
    """
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    scores = get_latest_inference_scores(session_id)
    if scores is None:
        raise HTTPException(
            status_code=404,
            detail=f"Inference scores are not available yet. Please complete at least {TOTAL_PHASE1_QUESTIONS} chat turns."
        )

    tree = build_career_tree(session_id)
    tree = enrich_tree_with_ai(tree, session_id)

    return {
        "status": "success",
        "session_id": session_id,
        "nodes": tree["nodes"],
        "edges": tree["edges"],
    }

# ── User Control & Profile Endpoints ─────────────────────────

@app.get("/api/user/profile/{session_id}")
def get_user_profile(session_id: str):
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    scores = get_latest_inference_scores(session_id)
    if scores is None:
        raise HTTPException(
            status_code=404, 
            detail=f"Inference scores are not available yet. Please complete at least {TOTAL_PHASE1_QUESTIONS} chat turns."
        )

    clean_scores = {k: v for k, v in scores.items() if k != "inference_failed"}

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

    missing_keys = REQUIRED_DIMENSIONS - set(inf.keys())
    if missing_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required dimensions: {list(missing_keys)}. All 6 dimensions must be provided."
        )

    validated_inference = {}
    for k in REQUIRED_DIMENSIONS:
        v = inf[k]
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0.0 or v > 1.0:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid value for '{k}': {v}. All dimension values must be numbers between 0.0 and 1.0."
            )
        validated_inference[k] = float(v)

    log_event(req.session_id, "profile_updated", validated_inference)

    return {
        "status": "success",
        "session_id": req.session_id,
        "message": "User profile successfully updated",
        "inference": validated_inference
    }

@app.post("/api/user/trait/decision")
def trait_decision(req: TraitDecisionRequest):
    if not session_exists(req.session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    if req.trait not in REQUIRED_DIMENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid trait '{req.trait}'. Must be one of: {list(REQUIRED_DIMENSIONS)}"
        )

    if req.action not in ["accept", "reject"]:
        raise HTTPException(status_code=400, detail="Action must be 'accept' or 'reject'")

    scores = get_latest_inference_scores(req.session_id)
    if not scores:
        raise HTTPException(status_code=404, detail="Inference scores are not available yet.")

    clean_scores = {k: float(v) for k, v in scores.items() if k in REQUIRED_DIMENSIONS}

    if req.action == "accept":
        log_event(req.session_id, "trait_accepted", {"trait": req.trait, "score": clean_scores[req.trait]})
        return {
            "status": "success",
            "session_id": req.session_id,
            "message": f"Trait '{req.trait}' accepted.",
            "inference": clean_scores
        }

    elif req.action == "reject":
        new_val = req.override_value if req.override_value is not None else 0.0
        if new_val < 0.0 or new_val > 1.0:
            raise HTTPException(status_code=400, detail="override_value must be between 0.0 and 1.0")

        clean_scores[req.trait] = float(new_val)
        log_event(req.session_id, "trait_rejected", {"trait": req.trait, "new_score": new_val})
        log_event(req.session_id, "profile_updated", clean_scores)

        return {
            "status": "success",
            "session_id": req.session_id,
            "message": f"Trait '{req.trait}' rejected and updated to {new_val}.",
            "inference": clean_scores
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
            detail="Inference scores are not available yet. Please complete at least 7 chat turns."
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