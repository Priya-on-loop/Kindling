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

sys.path.append(str(BACKEND_DIR))
sys.path.append(str(ROOT_DIR / "ai_core"))
sys.path.append(str(ROOT_DIR / "Scripts"))
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

TITLE_FALLBACK_TURN = 1
TITLE_AI_TURN = 3


class OccupationContext(BaseModel):
    title: str
    description: Optional[str] = None
    tasks: Optional[List[str]] = None


def build_context_note(context: Optional[OccupationContext]) -> str:
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
    messages = get_messages(session_id)
    first_user = next((m["content"] for m in messages if m["role"] == "user"), "").strip()
    set_session_title(session_id, build_fallback_title(first_user))


def maybe_generate_title(session_id: str) -> None:
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

# Improved Phase 2 Prompt
PHASE2_SYSTEM_PROMPT = """\
You are Kindling, a warm, encouraging mentor talking with a HIGH-SCHOOL \
STUDENT who is casually exploring a possible interest or direction. They are \
not a professional planning a curriculum, not a college student choosing a \
major, and have not committed to anything — they're just curious.

Rules:
- Keep answers SHORT: 3 sentences maximum. Never write long paragraphs.
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
- Keep the tone casual, warm, and human — like a mentor, not a manual.

Formatting & Tone Rules:
- NEVER write giant walls of text or dense paragraphs.
- Use short, bite-sized bullet points (using '- ') whenever explaining ideas, answering questions, or listing details so it's super fast and easy to read.
- Keep the overall response short (under 70 words total).
- Use plain, everyday language a high schooler would use with a friend.
- End with ONE short, warm question to keep the conversation going.

GOLDEN RULES FOR HIGH ENGAGEMENT:
1. TALK LIKE A COOL MENTOR: Be enthusiastic, warm, and casual. Speak like a friend over coffee, never a textbook or resume guide.
2. HIGHLY SCANNABLE: Never write walls of text or formal numbered lists. Use short lines and 2-3 quick bullet points with bold highlights (`**bold**`).
3. BRING IDEAS TO LIFE: Use vivid, real-world examples, vibes, or creative angles (e.g., storytelling, music, aesthetics, building stuff).
4. KEEP IT BITE-SIZED: Keep total responses under 50-60 words.
5. END WITH A FUN HOOK: Always finish with a low-pressure, genuinely curious question about what *they* think or find cool.

Extra important rules for beginners:
- If they ask for a "demo", "example", or "show me", give something FUN and TINY \
  that a complete beginner can enjoy in 30 seconds. Never give a hard challenge, \
  coding problem, or anything that could intimidate them.
- If they seem unsure, shy, or say things like "I don't know", be extra gentle \
  and ask one small, low-pressure question.
- Match their energy. If they're chill, stay chill. If they're excited, match it.
- Never assume they already know technical terms.
"""

CLOSING_MESSAGE = (
    "Thanks for sharing all of that! I've got a good sense of what draws you in. "
    "Your initial career profile is complete! You can view your career matches now, "
    "or feel free to keep chatting with me to explore any specific activities or questions further."
)

INSUFFICIENT_CONTENT_MESSAGE = (
    "It looks like we didn't get to chat much yet. "
    "To build your career profile, try sharing something you enjoyed doing recently, "
    "or a hobby you find interesting. Even one small detail helps!"
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

    # No account found
    if user is None:
        raise HTTPException(
            status_code=404,
            detail="No account found with this email. Please create an account first."
        )

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

# ── Signals API ───────────────────────────────────────────────

@app.post("/api/chat/start", response_model=StartResponse)
def chat_start(req: StartRequest = StartRequest()) -> StartResponse:
    user_id = resolve_user_id(req.token)
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

    delete_session(session_id)
    return {"status": "success", "session_id": session_id}


@app.post("/api/chat/message", response_model=MessageResponse)
def chat_message(req: MessageRequest) -> MessageResponse:
    if not session_exists(req.session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    add_message(req.session_id, "user", req.message)
    question_index = count_user_messages(req.session_id)

    # ─────────────────────────────────────────────────────────────
    # PHASE 1: STRUCTURED INTAKE (TURNS 1 TO 7)
    # ─────────────────────────────────────────────────────────────
    if question_index <= TOTAL_PHASE1_QUESTIONS:
        log_event(req.session_id, "message_sent", {
            "turn": question_index,
            "character_count": len(req.message)
        })

        if question_index == TITLE_FALLBACK_TURN:
            set_fallback_title(req.session_id)
        if question_index == TITLE_AI_TURN:
            maybe_generate_title(req.session_id)

        # Turn 7 Checkpoint
        if question_index == TOTAL_PHASE1_QUESTIONS:
            phase1_transcript = get_messages(req.session_id)
            user_messages = [m["content"] for m in phase1_transcript if m["role"] == "user"]
            combined_text = " ".join(user_messages).strip().lower()

            # Filter out empty / dismissive responses
            filler = {
                "idk", "i don't know", "dont know", "don't know", "ahh", "ah", "no", "nah",
                "maybe", "hmm", "hm", "ok", "okay", "sure", "yes", "nope", "yeah", "yep",
                "nothing", "not sure", "dunno", "whatever", "idc", "meh"
            }
            meaningful_words = [
                w for w in combined_text.split()
                if w not in filler and len(w) > 2
            ]

            # If user gave almost no real info → don't score
            if len(meaningful_words) < 12:
                add_message(req.session_id, "assistant", INSUFFICIENT_CONTENT_MESSAGE)
                log_event(req.session_id, "insufficient_content", {
                    "word_count": len(meaningful_words)
                })
                return MessageResponse(
                    reply=INSUFFICIENT_CONTENT_MESSAGE,
                    question_index=TOTAL_PHASE1_QUESTIONS,
                    total_questions=TOTAL_PHASE1_QUESTIONS,
                )

            # Normal scoring flow
            add_message(req.session_id, "assistant", CLOSING_MESSAGE)
            log_event(req.session_id, "session_completed", {"total_turns": TOTAL_PHASE1_QUESTIONS})
            maybe_generate_title(req.session_id)

            scores = score_session(phase1_transcript)
            log_event(req.session_id, "score_computed", scores)
            print(f"[session {req.session_id}] Phase 1 scoring completed & saved: {scores}")

            return MessageResponse(
                reply=CLOSING_MESSAGE,
                question_index=TOTAL_PHASE1_QUESTIONS,
                total_questions=TOTAL_PHASE1_QUESTIONS,
            )

        # Turns 1–6: normal follow-up
        history = get_messages(req.session_id)
        try:
            reply = call_llm(
                messages=history,
                system_prompt=FOLLOWUP_SYSTEM_PROMPT + build_context_note(req.context)
            )
        except Exception as e:
            print(f"\n[LLM ERROR]: {e}\n")
            reply = "Sorry, I'm having trouble responding right now — try again in a moment."

        add_message(req.session_id, "assistant", reply)
        log_event(req.session_id, "followup_generated", {
            "turn": question_index,
            "reply_length": len(reply)
        })

        return MessageResponse(
            reply=reply,
            question_index=question_index,
            total_questions=TOTAL_PHASE1_QUESTIONS,
        )

    # ─────────────────────────────────────────────────────────────
    # PHASE 2: OPEN EXPLORATION (TURNS 8+)
    # ─────────────────────────────────────────────────────────────
    else:
        log_event(req.session_id, "phase2_message", {
            "turn": question_index,
            "character_count": len(req.message)
        })

        history = get_messages(req.session_id)
        try:
            reply = call_llm(
                messages=history,
                system_prompt=PHASE2_SYSTEM_PROMPT + build_context_note(req.context)
            )
        except Exception as e:
            print(f"\n[PHASE 2 LLM ERROR]: {e}\n")
            reply = "I'm here to help you explore! What else would you like to talk about?"

        add_message(req.session_id, "assistant", reply)
        log_event(req.session_id, "phase2_followup", {
            "turn": question_index,
            "reply_length": len(reply)
        })

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
    return {
        "session_id": session_id,
        "total_messages": len(history),
        "user_messages_count": user_count,
        "transcript": history
    }

# ── Inference API ─────────────────────────────────────────────

@app.get("/api/chat/inference/{session_id}")
def get_inference_scores(session_id: str):
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    scores = get_latest_inference_scores(session_id)
    if scores is None:
        raise HTTPException(
            status_code=404,
            detail="We need a little more to go on! Please share a few real details about your hobbies or interests in the Explore chat to unlock your inference map."
        )

    clean_scores = {k: v for k, v in scores.items() if k != "inference_failed"}
    return {
        "status": "success",
        "session_id": session_id,
        "inference": clean_scores,
        "inference_failed": scores.get("inference_failed", False)
    }

# ── Career Graph API ──────────────────────────────────────────

@app.get("/api/career-graph/{session_id}")
def get_career_graph(session_id: str, max_results: int = MAX_RESULTS):
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    scores = get_latest_inference_scores(session_id)
    if scores is None:
        raise HTTPException(
            status_code=404,
            detail="Your career map is waiting! Share a few real details about what you enjoy doing in the Explore chat to reveal your connected career directions."
        )

    riasec_cols = ["creates_expresses", "organizes_systems", "investigates_why",
                   "builds_tinkers", "works_with_people", "leads_persuades"]
    student_vector = [float(scores.get(col, 0.0)) for col in riasec_cols]

    faiss_matches = match_occupations(student_vector, max_results=max_results)
    all_occupations = {occ["id"]: occ for occ in load_career_graph()}

    enriched_careers = []
    for match in faiss_matches:
        occ_id = match["id"]
        full_occ = all_occupations.get(occ_id, {})
        occ_riasec = full_occ.get("riasec") or {}
        dominant_area = max(occ_riasec, key=occ_riasec.get) if occ_riasec else None
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


# In-memory cache for instant career tree rendering
CAREER_TREE_CACHE = {}

@app.get("/api/career-tree/{session_id}")
def get_career_tree(session_id: str):
    """
    Returns the 3-tier career tree graph for a session.
    Cached in memory per session + score state for instant 0.01s page loads.
    """
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    scores = get_latest_inference_scores(session_id)
    if scores is None:
        raise HTTPException(
            status_code=404,
            detail=f"Inference scores are not available yet. Please complete at least {TOTAL_PHASE1_QUESTIONS} chat turns."
        )

    # Cache Key based on session_id and scores state
    cache_key = f"{session_id}_{hash(str(scores))}"
    if cache_key in CAREER_TREE_CACHE:
        return CAREER_TREE_CACHE[cache_key]

    # Fast deterministic tree build (<20ms)
    tree = build_career_tree(session_id)

    # Optional AI enrichment with graceful timeout/fallback
    try:
        tree = enrich_tree_with_ai(tree, session_id)
    except Exception as e:
        print(f"[Career Tree Enrichment Fallback Triggered]: {e}")
        # Falls back cleanly to the instant base tree if LLMs are slow

    result = {
        "status": "success",
        "session_id": session_id,
        "nodes": tree["nodes"],
        "edges": tree["edges"],
    }

    # Store in memory cache
    CAREER_TREE_CACHE[cache_key] = result
    return result

# ── User Control & Profile ────────────────────────────────────

@app.get("/api/user/profile/{session_id}")
def get_user_profile(session_id: str):
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    scores = get_latest_inference_scores(session_id)
    if scores is None:
        raise HTTPException(
            status_code=404,
            detail="We need a little more to go on! Please share a few real details about your hobbies or interests in the Explore chat to unlock your profile."
        )

    clean_scores = {k: v for k, v in scores.items() if k != "inference_failed"}
    return {
        "status": "success",
        "session_id": session_id,
        "inference": clean_scores,
        "inference_failed": scores.get("inference_failed", False)
    }

# ── Telemetry & Analytics ─────────────────────────────────────

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

# ── SHAP Match Explainer ──────────────────────────────────────

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