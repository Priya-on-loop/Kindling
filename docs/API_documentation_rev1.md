# Kindling API Documentation

**Base URL:** `https://kindling-backend.onrender.com`  
**Swagger UI:** `https://kindling-backend.onrender.com/docs`  
**Database:** SQLite (`kindling.db`)  
**Backend Owner:** Priya

---

## Database Schema (`kindling.db`)

* **`sessions`**: Stores session state.
  * `session_id` (Text, Primary Key)
  * `created_at` (Timestamp)
* **`messages`**: Stores conversation history.
  * `id` (Integer, Primary Key)
  * `session_id` (Text, Foreign Key)
  * `sender` (`user` or `assistant`)
  * `content` (Text message)
  * `timestamp` (Timestamp)

---

## API Response Scoring Benchmarks

The `/session/message` endpoint processes natural dialogue payloads and returns a calibrated `scores` object. To verify endpoint accuracy, the API was tested against single-dimension high-signal input payloads.

### Benchmark Validation Table

| API Request Input Snippet (`content`) | Target Score Key | Target Threshold | Actual Score | Status |
| :--- | :--- | :---: | :---: | :---: |
| *"Rewired RC car so both motors ran off one switch..."* | `builds_tinkers` | > 0.80 | **0.90** | **PASSED** |
| *"Asked science teacher 3 follow-ups about circuit overheating..."* | `investigates_why` | > 0.80 | **0.90** | **PASSED** |
| *"Spent weekend sketching comic strip nobody asked for..."* | `creates_expresses` | > 0.80 | **0.90** | **PASSED** |
| *"Volunteered to run study group; like being person people come to..."* | `works_with_people` | > 0.80 | **0.90** | **PASSED** |
| *"Organized notes into a colour-coded folder system..."* | `organizes_systems` | > 0.80 | **0.85** | **PASSED** |
| *"Talked whole team into scrapping first idea and starting over..."* | `leads_persuades` | > 0.80 | **0.90** | **PASSED** |

---

### Sample Execution

**Request (`POST /session/message`):**
```json
{
  "session_id": "sess_Me3f71745",
  "content": "Organized notes into a colour-coded folder system..."
}

Response (200 OK):

{
  "session_id": "sess_Me3f71745",
  "user_message": "Organized notes into a colour-coded folder system...",
  "assistant_reply": "That's interesting! What part of that caught your attention the most?",
  "scores": {
    "builds_tinkers": 0.10,
    "investigates_why": 0.30,
    "creates_expresses": 0.15,
    "works_with_people": 0.10,
    "organizes_systems": 0.85,
    "leads_persuades": 0.10,
    "inference_failed": false
  }
}
