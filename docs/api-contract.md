# API Contract (Sprint 1)

The single source of truth for what the frontend and backend agree on.
**Change this file in a PR before changing any endpoint shape**, so both sides can review it.

Base URL (local): `http://localhost:8000`
Auth: none in Sprint 1. Data is hardcoded through the seed script.

## GET /api/health/
Liveness check for Docker and CI.
```json
{ "status": "ok", "service": "coursepulse-api" }
```

## GET /api/lectures/
Lectures with a published quiz, newest first. Powers the Student Hub.
```json
[
  {
    "id": 1,
    "title": "Tuesday's Lecture: Agile and Scrum",
    "classroom": "CS 3398 Software Engineering",
    "published_at": "2026-09-22T15:00:00Z",
    "question_count": 5
  }
]
```

## GET /api/lectures/{id}/quiz/
The full quiz for one lecture. Powers the Arena (game screen).
```json
{
  "lecture_id": 1,
  "title": "Tuesday's Lecture: Agile and Scrum",
  "questions": [
    {
      "id": 11,
      "prompt": "Why does Scrum use fixed-length sprints?",
      "choices": ["Option A", "Option B", "Option C", "Option D"],
      "correct_index": 2,
      "difficulty": "easy"
    }
  ]
}
```

Field rules
- `choices`: exactly 4 strings. `correct_index`: integer 0-3.
- `difficulty`: `"easy"` (100 pts), `"medium"` (200 pts) or `"hard"` (300 pts).
- Questions are returned in a fixed order.

Errors: `404` with `{"detail": "Not found."}` for an unknown lecture id.

## Known Sprint 1 shortcuts (tracked for Sprint 2)
- `correct_index` is sent to the browser so scoring can happen client-side.
  Sprint 2 moves grading to a `POST` endpoint on the server so scores cannot be faked.
- No authentication or class-code join yet.
