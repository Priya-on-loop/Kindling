import sqlite3
import uuid
from datetime import datetime, timezone
import os

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

if __name__ == "__main__":
    # 1. Initialize tables
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

