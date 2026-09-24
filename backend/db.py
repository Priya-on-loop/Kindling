import sqlite3
import uuid
from datetime import datetime, timezone
import os
import json  # Needed to serialize event_data to JSON strings

DB_PATH = os.path.join(os.path.dirname(__file__), "kindling.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id  TEXT PRIMARY KEY,
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT NOT NULL,
            sender      TEXT NOT NULL CHECK (sender IN ('user', 'assistant')),
            content     TEXT NOT NULL,
            timestamp   TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );

        -- [REVIEW 2] TCP-41: Telemetry events table
        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT NOT NULL,
            event_type  TEXT NOT NULL,
            event_data  TEXT,
            timestamp   TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );

        CREATE TABLE IF NOT EXISTS users (
            id             TEXT PRIMARY KEY,
            email          TEXT NOT NULL UNIQUE,
            password_hash  TEXT NOT NULL,
            created_at     TEXT NOT NULL
        );

        -- Career tree AI-naming layer cache (Phase 2). Most generated
        -- strings (field names, career short titles, "try it" text)
        -- are session-independent — the same real occupation/task
        -- always gets the same real treatment, so they're cached
        -- once and reused by every user. "why it's connected" is the
        -- one kind that depends on a specific user's real evidence,
        -- so its cache_key includes a hash of that evidence — see
        -- ai_core/tree_naming.py.
        CREATE TABLE IF NOT EXISTS generated_strings (
            cache_key   TEXT PRIMARY KEY,
            kind        TEXT NOT NULL,
            value       TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );
    """)

    # sessions already existed (with real data) before user_id was
    # added, so CREATE TABLE IF NOT EXISTS above never adds it to an
    # existing database — migrate explicitly, once, only if missing.
    existing_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()
    }
    if "user_id" not in existing_columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT")

    if "title" not in existing_columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN title TEXT")

    if "pinned" not in existing_columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")

    if "pinned_at" not in existing_columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN pinned_at TEXT")

    conn.commit()
    conn.close()

def create_session(user_id: str | None = None) -> str:
    """
    Generates a new session_id, saves it to the DB, and returns the
    ID. user_id is nullable — anonymous sessions (no auth token
    sent) keep working exactly as before, with NULL here.
    """
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    conn = get_db()
    conn.execute(
        "INSERT INTO sessions (session_id, created_at, user_id) VALUES (?, ?, ?)",
        (session_id, now, user_id)
    )
    conn.commit()
    conn.close()
    return session_id


def get_sessions_for_user(user_id: str) -> list[dict]:
    """
    Returns every REAL session belonging to a signed-in user (at
    least one real user message — a "New thread" click that was
    never actually used doesn't count as a thread), newest first,
    with its generated title (NULL until enough turns have happened
    to generate one — the caller decides the "New conversation"
    placeholder) and pin state.
    """
    conn = get_db()
    rows = conn.execute("""
        SELECT s.session_id, s.created_at, s.title, s.pinned, s.pinned_at
        FROM sessions s
        WHERE s.user_id = ?
          AND EXISTS (SELECT 1 FROM messages m WHERE m.session_id = s.session_id AND m.sender = 'user')
        ORDER BY s.created_at DESC
    """, (user_id,)).fetchall()
    conn.close()

    return [dict(row) for row in rows]


def set_session_title(session_id: str, title: str) -> None:
    conn = get_db()
    conn.execute("UPDATE sessions SET title = ? WHERE session_id = ?", (title, session_id))
    conn.commit()
    conn.close()


def get_session_title(session_id: str) -> str | None:
    conn = get_db()
    row = conn.execute("SELECT title FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
    conn.close()
    return row["title"] if row else None


def get_session_user_id(session_id: str) -> str | None:
    conn = get_db()
    row = conn.execute("SELECT user_id FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
    conn.close()
    return row["user_id"] if row else None


def count_pinned_sessions(user_id: str) -> int:
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM sessions WHERE user_id = ? AND pinned = 1", (user_id,)
    ).fetchone()
    conn.close()
    return row["c"]


def set_session_pinned(session_id: str, pinned: bool, pinned_at: str | None) -> None:
    conn = get_db()
    conn.execute(
        "UPDATE sessions SET pinned = ?, pinned_at = ? WHERE session_id = ?",
        (1 if pinned else 0, pinned_at, session_id)
    )
    conn.commit()
    conn.close()


def delete_session(session_id: str) -> None:
    """Removes a thread completely: its messages, its events (real
    scores, node_time, trait decisions — everything Inference,
    Career Graph, and Reflection read is session_id-scoped and
    stored in these two tables, nothing duplicated elsewhere), and
    the session row itself."""
    conn = get_db()
    conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM events WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()


def delete_empty_sessions_for_user(user_id: str, exclude_session_id: str | None = None) -> int:
    """
    Real cleanup for abandoned "New thread" clicks: sessions with a
    user_id but zero real user messages. Called opportunistically
    right before a new session is created, so the DB itself never
    accumulates empty rows — not just hiding them in the list.
    Returns how many were removed.
    """
    conn = get_db()
    rows = conn.execute("""
        SELECT s.session_id FROM sessions s
        WHERE s.user_id = ?
          AND s.session_id != COALESCE(?, '')
          AND NOT EXISTS (SELECT 1 FROM messages m WHERE m.session_id = s.session_id AND m.sender = 'user')
    """, (user_id, exclude_session_id)).fetchall()

    for row in rows:
        sid = row["session_id"]
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
        conn.execute("DELETE FROM events WHERE session_id = ?", (sid,))
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (sid,))

    conn.commit()
    conn.close()
    return len(rows)


def create_user(email: str, password_hash: str) -> str | None:
    """
    Creates a new user with an already-hashed password. Returns
    the new user's id, or None if the email is already taken.
    Email is normalized (trimmed + lowercased) so the same
    address can't be registered twice under different casing.
    """
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    normalized_email = email.strip().lower()

    conn = get_db()

    try:
        conn.execute(
            "INSERT INTO users (id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (user_id, normalized_email, password_hash, now)
        )
        conn.commit()
        return user_id

    except sqlite3.IntegrityError:
        return None

    finally:
        conn.close()


def get_user_by_id(user_id: str) -> sqlite3.Row | None:
    """Looks up a user by id (the value used as their auth token)."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()

    return row


def get_user_by_email(email: str) -> sqlite3.Row | None:
    """Looks up a user by email (case-insensitive)."""
    normalized_email = email.strip().lower()

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?",
        (normalized_email,)
    ).fetchone()
    conn.close()

    return row


def add_message(session_id: str, sender: str, content: str) -> None:
    """Saves a single message (from 'user' or 'assistant') to the DB."""
    now = datetime.now(timezone.utc).isoformat()
    
    conn = get_db()
    conn.execute(
        "INSERT INTO messages (session_id, sender, content, timestamp) VALUES (?, ?, ?, ?)",
        (session_id, sender, content, now)
    )
    conn.commit()
    conn.close()

def get_messages(session_id: str) -> list[dict]:
    """Retrieves all messages for a session formatted for the LLM."""
    conn = get_db()
    cursor = conn.execute(
        "SELECT sender, content FROM messages WHERE session_id = ? ORDER BY id",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    formatted_messages = []
    for row in rows:
        formatted_messages.append({
            "role": "user" if row["sender"] == "user" else "assistant",
            "content": row["content"]
        })
        
    return formatted_messages

def count_user_messages(session_id: str) -> int:
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM messages WHERE session_id = ? AND sender = 'user'",
        (session_id,)
    ).fetchone()
    conn.close()
    return row["cnt"]

def session_exists(session_id: str) -> bool:
    """Returns True if the session_id exists in SQLite, False otherwise."""
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM sessions WHERE session_id = ?", 
        (session_id,)
    ).fetchone()
    conn.close()
    return row is not None


# =====================================================================
# [REVIEW 2] TELEMETRY & DASHBOARD DB FUNCTIONS
# TCP-41, TCP-52, TCP-53, TCP-54
# =====================================================================

def log_event(session_id: str, event_type: str, event_data: dict = None) -> None:
    """
    TCP-41: Logs an interaction event into the events table.
    e.g., event_type='session_started', 'message_sent', 'career_card_clicked'
    """
    now = datetime.now(timezone.utc).isoformat()
    data_str = json.dumps(event_data) if event_data else "{}"

    conn = get_db()
    conn.execute(
        "INSERT INTO events (session_id, event_type, event_data, timestamp) VALUES (?, ?, ?, ?)",
        (session_id, event_type, data_str, now)
    )
    conn.commit()
    conn.close()


def get_latest_inference_scores(session_id: str) -> dict | None:
    """
    Retrieves the most recent computed or user-updated 6D scores for a session from SQLite events table.
    Checks 'profile_updated' first (if user edited scores), then 'score_computed'.
    """
    conn = get_db()
    cursor = conn.execute("""
        SELECT event_data FROM events 
        WHERE session_id = ? AND event_type IN ('score_computed', 'profile_updated')
        ORDER BY id DESC LIMIT 1
    """, (session_id,))
    row = cursor.fetchone()
    conn.close()

    if row and row["event_data"]:
        try:
            return json.loads(row["event_data"])
        except Exception:
            return None
    return None


def get_latest_trait_decisions(session_id: str) -> dict:
    """
    The most recent accept/reject decision per RIASEC trait, from the
    real trait_accepted/trait_rejected events POST /api/user/trait/
    decision already logs — there's no dedicated calibration table,
    so this reads the same events table score/timeline queries use.
    Returns {trait: "accept" | "reject"}; a trait never decided on
    is simply absent, not a fabricated "neutral" entry.
    """
    conn = get_db()
    rows = conn.execute("""
        SELECT event_type, event_data FROM events
        WHERE session_id = ? AND event_type IN ('trait_accepted', 'trait_rejected')
        ORDER BY id ASC
    """, (session_id,)).fetchall()
    conn.close()

    decisions = {}
    for row in rows:
        try:
            data = json.loads(row["event_data"])
        except Exception:
            continue
        trait = data.get("trait")
        if trait:
            decisions[trait] = "accept" if row["event_type"] == "trait_accepted" else "reject"

    return decisions


def get_cached_string(cache_key: str) -> str | None:
    conn = get_db()
    row = conn.execute(
        "SELECT value FROM generated_strings WHERE cache_key = ?", (cache_key,)
    ).fetchone()
    conn.close()
    return row["value"] if row else None


def set_cached_string(cache_key: str, kind: str, value: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO generated_strings (cache_key, kind, value, created_at) VALUES (?, ?, ?, ?)",
        (cache_key, kind, value, now)
    )
    conn.commit()
    conn.close()


def get_dashboard_metrics() -> dict:
    """
    TCP-52: Computes aggregated analytics for the admin/dashboard view.
    Returns counts for total sessions, total user messages, total events, and breakdown by event type.
    """
    conn = get_db()

    total_sessions = conn.execute("SELECT COUNT(*) AS cnt FROM sessions").fetchone()["cnt"]

    total_user_messages = conn.execute(
        "SELECT COUNT(*) AS cnt FROM messages WHERE sender = 'user'"
    ).fetchone()["cnt"]

    total_events = conn.execute("SELECT COUNT(*) AS cnt FROM events").fetchone()["cnt"]

    event_rows = conn.execute("""
        SELECT event_type, COUNT(*) AS cnt
        FROM events
        GROUP BY event_type
        ORDER BY cnt DESC
    """).fetchall()
    event_breakdown = {row["event_type"]: row["cnt"] for row in event_rows}

    recent_rows = conn.execute("""
        SELECT session_id, created_at
        FROM sessions
        ORDER BY created_at DESC
        LIMIT 5
    """).fetchall()
    recent_sessions = [{"session_id": r["session_id"], "created_at": r["created_at"]} for r in recent_rows]

    conn.close()

    return {
        "total_sessions": total_sessions,
        "total_user_messages": total_user_messages,
        "total_events": total_events,
        "event_breakdown": event_breakdown,
        "recent_sessions": recent_sessions,
    }


def get_session_timeline(session_id: str) -> list[dict]:
    """
    TCP-54: Returns an ordered, chronological timeline combining messages and events for a session.
    """
    conn = get_db()
    cursor = conn.execute("""
        SELECT 'message' AS item_type, sender AS detail, content AS data, timestamp 
        FROM messages WHERE session_id = ?
        UNION ALL
        SELECT 'event' AS item_type, event_type AS detail, event_data AS data, timestamp 
        FROM events WHERE session_id = ?
        ORDER BY timestamp ASC
    """, (session_id, session_id))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_field_summary() -> dict:
    """
    TCP-53: Returns event frequencies and distribution across telemetry types for dashboard charts.
    """
    conn = get_db()
    cursor = conn.execute("""
        SELECT event_type, COUNT(*) AS total_count, MAX(timestamp) AS last_seen
        FROM events
        GROUP BY event_type
        ORDER BY total_count DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return {r["event_type"]: {"count": r["total_count"], "last_seen": r["last_seen"]} for r in rows}


if __name__ == "__main__":
    init_db()
    test_session_id = create_session()
    add_message(test_session_id, "assistant", "What have you been curious about lately?")
    add_message(test_session_id, "user", "I've been tinkering with mechanical keyboards.")
    log_event(test_session_id, "session_started", {"source": "test_script"})
    print(f"Created & verified session: {test_session_id}")
    print("\n[REVIEW 2 TEST] Dashboard Metrics:")
    print(json.dumps(get_dashboard_metrics(), indent=2))