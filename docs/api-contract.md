# API Contract (Sprint 1)

The single source of truth for what the frontend and backend agree on.
**Change this file in a PR before changing any endpoint shape**, so both sides can review it.

Base URL (local): `http://localhost:8000`
Auth: token authentication for protected endpoints.
Send `Authorization: Token <token>` with protected requests.
Registration and login do not require a token.
Lecture data is hardcoded through the seed script.

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
- No class-code join yet.

## Authentication

Send JSON request bodies with `Content-Type: application/json`.

### POST /api/auth/register/

Creates an account. No token required.

Request:
```json
{
  "email": "student@example.com",
  "password": "Maple!River82",
  "role": "student"
}
```

Rules:
- Email must be valid and at most 150 characters.
- Emails are trimmed and stored in lowercase.
- Duplicate emails are rejected regardless of capitalization.
- Role must be `"student"` or `"professor"`.
- Password must have at least 8 characters and pass Django's
  checks for common, entirely numeric, and user-similar passwords.

Success: `201 Created`
```json
{
  "token": "<token>",
  "user": {
    "id": 1,
    "email": "student@example.com",
    "role": "student"
  }
}
```

Invalid input: `400 Bad Request`, with errors under the relevant field.

Duplicate email example:
```json
{
  "email": ["An account with this email already exists."]
}
```

Weak password example:
```json
{
  "password": [
    "This password is too short. It must contain at least 8 characters."
  ]
}
```

Password error wording can vary according to the failed check.

### POST /api/auth/login/

Logs in using email and password. No token required.

Request:
```json
{
  "email": "student@example.com",
  "password": "Maple!River82"
}
```

Success: `200 OK`, with the same token and user response
structure as registration.

Invalid credentials: `401 Unauthorized`
```json
{
  "detail": "Invalid email or password."
}
```

Missing or non-string credentials: `400 Bad Request`
```json
{
  "detail": "Email and password are required."
}
```

### GET /api/auth/me/

Returns the current user's information. Requires this header:

```text
Authorization: Token <token>
```

Success: `200 OK`
```json
{
  "id": 1,
  "email": "student@example.com",
  "role": "student"
}
```

Missing token: `401 Unauthorized`
```json
{
  "detail": "Authentication credentials were not provided."
}
```

Invalid token: `401 Unauthorized`
```json
{
  "detail": "Invalid token."
}
```

Tokens are reused on login and do not automatically expire.
Existing users without a role profile receive `"role": null`.