"""
One-time migration for the "every thread shows New conversation" bug
(root cause: the old title trigger only fired at an EXACT user-message
count of 3 or 7 — any thread that had already passed those counts
before the title feature existed could never trigger it again, since
the count only increases). Two things:

1. Every existing thread with at least one real user message but no
   title gets a real title now — an AI-generated one where possible,
   the same honest fallback used elsewhere otherwise.
2. Every existing thread with ZERO real user messages (an abandoned
   "New thread" click) is deleted outright, matching the new rule
   that a thread isn't real until its first message is sent.

Prints a before/after report for every thread it touches.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR / "backend"))
sys.path.append(str(ROOT_DIR / "ai_core"))

import db
from title_generator import generate_title, build_fallback_title


def backfill_titles():
    conn = db.get_db()
    rows = conn.execute("""
        SELECT s.session_id, s.title,
               (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.session_id AND m.sender = 'user') AS user_msg_count
        FROM sessions s
        WHERE s.user_id IS NOT NULL
    """).fetchall()
    conn.close()

    to_title = [dict(r) for r in rows if r["title"] is None and r["user_msg_count"] > 0]
    to_delete = [dict(r) for r in rows if r["user_msg_count"] == 0]

    print(f"Found {len(to_title)} real thread(s) with messages but no title.")
    print(f"Found {len(to_delete)} empty thread(s) (0 user messages) to delete.\n")

    for row in to_title:
        sid = row["session_id"]
        messages = db.get_messages(sid)
        first_user = next((m["content"] for m in messages if m["role"] == "user"), "").strip()

        title = generate_title(messages)
        source = "AI"
        if title is None:
            title = build_fallback_title(first_user)
            source = "fallback"

        db.set_session_title(sid, title)
        print(f"[{source}] {sid}")
        print(f"  before: None")
        print(f"  after:  {title!r}\n")

    for row in to_delete:
        sid = row["session_id"]
        db.delete_session(sid)
        print(f"[deleted empty thread] {sid}")

    print(f"\nDone. Titled {len(to_title)} thread(s), deleted {len(to_delete)} empty thread(s).")


if __name__ == "__main__":
    backfill_titles()
