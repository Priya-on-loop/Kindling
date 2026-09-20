import sqlite3
import uuid
from datetime import datetime, timezone
import os
import json  # [NEW FOR REVIEW 2]: Needed to serialize event_data to JSON strings

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

        -- [NEW FOR REVIEW 2] TCP-41: Telemetry events table
        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT NOT NULL,
            event_type  TEXT NOT NULL,
            event_data  TEXT,
            timestamp   TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );
    """)
    conn.commit()
    conn.close()

def create_session() -> str:
    """Generates a new session_id, saves it to the DB, and returns the ID."""
    session_id = str(uuid.uuid4())  # Generates a random unique string like "c9bf9e57-1685-4c89-bafb-ff5af830be8a"
    now = datetime.now(timezone.utc).isoformat()  # Current timestamp in standard ISO format
    
    conn = get_db()
    conn.execute(
        "INSERT INTO sessions (session_id, created_at) VALUES (?, ?)",
        (session_id, now)
    )
    conn.commit()
    conn.close()
    return session_id


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
    
    # Convert each DB row into the {"role": ..., "content": ...} shape
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
# [NEW FOR REVIEW 2] TELEMETRY & DASHBOARD DB FUNCTIONS
# TCP-41, TCP-52
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


def get_dashboard_metrics() -> dict:
    """
    TCP-52: Computes aggregated analytics for the admin/dashboard view.
    Returns counts for total sessions, total user messages, total events, and breakdown by event type.
    """
    conn = get_db()

    # 1. Total Sessions
    total_sessions = conn.execute("SELECT COUNT(*) AS cnt FROM sessions").fetchone()["cnt"]

    # 2. Total User Messages
    total_user_messages = conn.execute(
        "SELECT COUNT(*) AS cnt FROM messages WHERE sender = 'user'"
    ).fetchone()["cnt"]

    # 3. Total Events
    total_events = conn.execute("SELECT COUNT(*) AS cnt FROM events").fetchone()["cnt"]

    # 4. Breakdown by Event Type
    event_rows = conn.execute("""
        SELECT event_type, COUNT(*) AS cnt
        FROM events
        GROUP BY event_type
        ORDER BY cnt DESC
    """).fetchall()
    event_breakdown = {row["event_type"]: row["cnt"] for row in event_rows}

    # 5. Recent Active Sessions
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


if __name__ == "__main__":
    # 1. Initialize tables (including the new 'events' table)
    init_db()
    
    # 2. Test creating a session
    test_session_id = create_session()
    print(f"Created session: {test_session_id}")
    
    # 3. Test adding messages
    add_message(test_session_id, "assistant", "What have you been curious about lately?")
    add_message(test_session_id, "user", "I've been tinkering with mechanical keyboards.")
    
    # 4. Test getting messages
    history = get_messages(test_session_id)
    print("Conversation history:")
    for msg in history:
        print(f"  {msg['role']}: {msg['content']}")
        
    # 5. Test counting user messages
    user_count = count_user_messages(test_session_id)
    print(f"User message count: {user_count}")

    # 6. Create a real session
    real_session_id = create_session()
    print(f"Created real session: {real_session_id}")
    
    # 7. Test session_exists with a REAL session ID (should print True)
    print("Does real session exist?", session_exists(real_session_id))
    
    # 8. Test session_exists with a FAKE session ID (should print False)
    print("Does fake session exist?", session_exists("this-is-a-fake-id-12345"))

    # 9. [NEW FOR REVIEW 2]: Test logging an event and getting metrics
    log_event(real_session_id, "session_started", {"source": "test_script"})
    log_event(real_session_id, "message_sent", {"character_count": 42})
    print("\n[REVIEW 2 TEST] Dashboard Metrics:")
    print(json.dumps(get_dashboard_metrics(), indent=2))