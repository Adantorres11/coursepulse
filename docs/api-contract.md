# API Contract (Sprint 1)

The single source of truth for what the frontend and backend agree on.
**Change this file in a PR before changing any endpoint shape**, so both sides can review it.

Base URL (local): `http://localhost:8000`
Auth: token authentication for protected endpoints.
Send `Authorization: Token <token>` with protected requests.
Registration and login do not require a token.
Lecture data is hardcoded through the seed script.
GET /api/lectures/ and GET /api/lectures/{id}/quiz/ need no token; an invalid token still returns 401. POST /api/lectures/{id}/answers/ requires a token.

## GET /api/health/
Liveness check for Docker and CI.
```json
{ "status": "ok", "service": "coursepulse-api" }
```

## GET /api/lectures/
Lectures with a published quiz, newest first. Powers the Student Hub.
A lecture is listed when its `published_at` has arrived and it has at least one question.
Drafts, future publications, and lectures without questions are never returned.
Success: `200 OK`. Returns `[]` when no lecture qualifies.
`classroom_id` identifies the classroom. `classroom` is its name, set by whoever created it.
```json
[
  {
    "id": 1,
    "title": "Tuesday's Lecture: Agile and Scrum",
    "classroom_id": 1,
    "classroom": "CS 3398 Software Engineering",
    "published_at": "2026-09-22T15:00:00Z",
    "question_count": 5
  }
]
```

## GET /api/lectures/{id}/quiz/
The full quiz for one lecture. Powers the Arena (game screen).
Success: `200 OK`.
```json
{
  "lecture_id": 1,
  "title": "Tuesday's Lecture: Agile and Scrum",
  "questions": [
    {
      "id": 11,
      "prompt": "Why does Scrum use fixed-length sprints?",
      "choices": ["Option A", "Option B", "Option C", "Option D"],
      "difficulty": "easy"
    }
  ],
  "answered_question_ids": [11],
  "total_points": 100
}
```

Field rules
- `choices`: exactly 4 strings.
- The quiz does not include the correct answer. The correct answer comes from
  `POST /api/lectures/{id}/answers/`.
- `difficulty`: `"easy"` (100 pts), `"medium"` (200 pts) or `"hard"` (300 pts).
- Questions are returned in a fixed order.
- `answered_question_ids`: the ids of the questions the logged-in student has
  answered in their open attempt. `total_points`: the points of that open attempt.
  The open attempt is the student's newest attempt for this lecture with no
  `completed_at`. Send the token to get these fields. When the request has no
  token, or there is no open attempt, they are `[]` and `0`.

Errors: `404` with `{"detail": "Not found."}` for an unknown lecture id. The same
`404` is returned when the lecture is not published yet or has no questions.

## POST /api/lectures/{id}/answers/
Grades one answer on the server. The Arena (game screen) calls it after each
question. Requires a token. Send `Content-Type: application/json`.

Request:
```json
{
  "question_id": 11,
  "chosen_index": 2,
  "time_taken_ms": 4200
}
```

Success: `201 Created`
```json
{
  "is_correct": true,
  "points_awarded": 100,
  "total_points": 100,
  "correct_index": 2
}
```

Rules:
- The lecture must be available, as in GET /api/lectures/{id}/quiz/.
  The question must belong to that lecture.
- `question_id`: integer. `chosen_index`: integer 0-3. `time_taken_ms`:
  integer, 0 or more. All three are required.
- `chosen_index` is always required. When time runs out, the screen sends
  `chosen_index` 0 with a `time_taken_ms` over the limit.
- The time limit is 15 seconds per question: `QUESTION_TIME_LIMIT_MS = 15000`.
  An answer timed out when `time_taken_ms` is greater than 15000.
- `points_awarded` is 100 for an easy question, 200 for medium, and 300 for
  hard. A correct answer gets 50 more points when it is the 3rd or later
  correct answer in a row in the attempt. The current answer counts toward
  the run. Every correct answer after the 3rd also gets the 50. It is 0
  when the answer is wrong or timed out. A timed-out answer is never
  correct, so `is_correct` is `false`.
- A wrong or timed-out answer sets the run of correct answers to 0.
- A new attempt starts with a run of correct answers of 0, so a replay
  starts the bonus count again.
- `total_points` is the running total of the attempt, including this answer.
- `correct_index` is always returned, so the screen can show green and red
  feedback.
- The server picks the attempt. It uses the student's newest attempt for the
  lecture with no `completed_at`, or starts a new one.
- When every question in the lecture has an answer, the attempt is completed
  (`completed_at` is set). The next answer starts a new attempt.
- A second answer to the same question in the same attempt is rejected.

Errors:
- `400`: Invalid body. Errors appear under the field name, as in
  POST /api/auth/register/.
```json
{
  "chosen_index": ["Ensure this value is less than or equal to 3."]
}
```
- `400`: The question already has an answer in this attempt.
```json
{
  "detail": "This question was already answered in this attempt."
}
```
- `401`: Missing or invalid authentication token.
- `404`: `{"detail": "Not found."}` for an unknown or unavailable lecture, or
  a question that is not in that lecture.

## Known Sprint 1 shortcuts (tracked for Sprint 2)
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

## GET /api/classes/

Returns only the logged-in student's enrolled classrooms.
Requires a student account and this header:

```text
Authorization: Token <token>
```

Success: `200 OK`
```json
[
  {
    "id": 1,
    "name": "Software Engineering",
    "course_code": "CS 3398",
    "professor": {
      "id": 2,
      "name": "Alex Smith"
    },
    "quiz_count": 5,
    "new_quiz_count": 3
  }
]
```

Rules:
- Classes are ordered by name, then ID.
- No enrollments returns `[]` with `200 OK`.
- Professor is `null` if no professor is assigned.
- Professor name falls back to username when their full name is empty.
- Course code may be empty for existing classrooms.
- Each lecture with questions counts as one quiz if its publication
  time has arrived.
- Drafts, future publications, and lectures without questions are excluded.
- New quizzes are available quizzes the current student has not completed.
- Completion is recorded through QuizCompletion. The quiz-submission
  handler must create this record when a student completes a quiz;
  this endpoint only reads completion records.
- Duplicate enrollment in the same classroom is prevented by the database.

Errors:
- `401`: Missing or invalid authentication token.
- `403`: Authenticated user does not have the student role.

## Class access codes

Each classroom has a unique six-character access code.
Generated codes use uppercase letters and numbers.
Code input is case-insensitive; surrounding whitespace is ignored.
The demo classroom's code is `DEMO01`.

Both endpoints below require a student account and this header:

```text
Authorization: Token <token>
```

### GET /api/classes/lookup/?code=ABC123

Previews a classroom without enrolling the student.

Success: `200 OK`
```json
{
  "id": 1,
  "name": "Software Engineering",
  "course_code": "CS 3398",
  "professor": {
    "id": 2,
    "name": "Alex Smith"
  },
  "quiz_count": 5,
  "new_quiz_count": 3
}
```

Fields and quiz-count rules match GET /api/classes/.
Professor may be null when no professor is assigned.

### POST /api/classes/join/

Enrolls the logged-in student in the classroom.

Send `Content-Type: application/json`.

Request:
```json
{
  "code": "ABC123"
}
```

Success:
- `201 Created` for a new enrollment.
- `200 OK` if already enrolled; no duplicate is created.
- Both return the same classroom response structure as lookup.

### Lookup and join errors

Unknown six-character code: `404 Not Found`
```json
{
  "detail": "We couldn't find a class with that code"
}
```

Other errors:
- `400`: Missing or malformed code; errors appear under `code`.
- `401`: Missing or invalid authentication token.
- `403`: Authenticated user does not have the student role.

## GET /api/classes/{id}/leaderboard/

Returns the class's enrolled students ranked by total quiz points.
Requires a student account and token authentication.

Success: `200 OK`
```json
[
  {
    "rank": 1,
    "display_name": "Bharat K.",
    "points": 500,
    "is_current_user": true
  },
  {
    "rank": 1,
    "display_name": "Alex S.",
    "points": 500,
    "is_current_user": false
  },
  {
    "rank": 3,
    "display_name": "Sam R.",
    "points": 0,
    "is_current_user": false
  }
]
```

Rules:
- Includes enrolled users with the student role.
- Points are the sum of total_points from completed attempts across
  all lectures in this class. Incomplete attempts are excluded.
- All completed attempts count, including repeat attempts.
- Attempts from other classes are excluded.
- Students are ordered by points descending, then user ID ascending
  for consistent ordering within ties.
- Equal points share the same rank using competition ranking:
  1, 1, 3.
- Students with no completed attempts receive zero points.
- Zero-point students appear last and share the same rank.
- display_name uses the first name and last initial, such as "Bharat K.".
- If the last name is missing, only the first name is shown.
- If the first name is missing, display_name is "Student".
  Email addresses and usernames are not used as name fallbacks.
- is_current_user is true only for the requesting student's entry.
- The response is an unpaginated array.

Errors:
- `401`: Missing or invalid authentication token.
- `404`: Unknown class ID.
- `403`: For an existing class, the requester does not have the
  student role or is not enrolled.

## GET /api/classes/{id}/stats/

Returns one student's progress in one class. The Class Hub screen uses
it. Requires a student account and token authentication.

Success: `200 OK`
```json
{
  "classroom_id": 1,
  "classroom": "Intro to Biology",
  "total_points": 500,
  "rank": 2,
  "points_to_next_rank": 120,
  "quizzes_played": 1,
  "quizzes_total": 2,
  "day_streak": 3,
  "answer_streak": 2,
  "up_next": {
    "id": 7,
    "title": "Cell Structure",
    "published_at": "2026-11-03T15:00:00Z",
    "question_count": 10,
    "best_score": 0,
    "correct_count": 0,
    "is_new": true
  },
  "lectures": [
    {
      "id": 7,
      "title": "Cell Structure",
      "published_at": "2026-11-03T15:00:00Z",
      "question_count": 10,
      "best_score": 0,
      "correct_count": 0,
      "is_new": true
    },
    {
      "id": 5,
      "title": "Intro to Cells",
      "published_at": "2026-10-27T15:00:00Z",
      "question_count": 8,
      "best_score": 500,
      "correct_count": 7,
      "is_new": false
    }
  ]
}
```

Rules:
- The class is identified by classroom_id. The name is returned in
  classroom.
- An available quiz is a lecture in this class with published_at in
  the past and at least one question. Only available quizzes appear
  in lectures and count in quizzes_total.
- A quiz is played when the student has an attempt for it with
  completed_at set. Incomplete attempts do not count.
- quizzes_played is the number of available quizzes the student has
  played. Repeat attempts do not add to it.
- total_points is the sum of total_points from the student's completed
  attempts across all lectures in this class, including repeat
  attempts. It matches the student's points in the leaderboard.
- rank uses competition ranking, the same as the leaderboard:
  1, 1, 3.
- points_to_next_rank is the gap to the nearest student with strictly
  more points. It is 0 for a student at rank 1, including when all
  students are tied at the top.
- lectures are ordered newest first by published_at, the same as
  GET /api/lectures/.
- up_next is the first unplayed lecture in that order, which is the
  newest unplayed lecture. It has the same shape as a lectures item.
  It is null when every available quiz is played.
- best_score is the highest total_points among the student's completed
  attempts for the lecture.
- correct_count is the number of correct answers in that same attempt.
  If two attempts tie on score, the attempt with the lowest attempt ID
  is used.
- An unplayed lecture has best_score 0, correct_count 0, and is_new
  true. A played lecture has is_new false.
- A student with no completed attempts gets total_points 0,
  quizzes_played 0, and points_to_next_rank as defined above. The
  student shares the last rank with the other zero-point students.
- day_streak is the number of days in a row on which the student answered
  at least one question in any class. A day is a UTC calendar date. The
  count goes back from today, or from yesterday if the student has not
  answered yet today. It is 0 when the student answered neither
  yesterday nor today.
- answer_streak is the run of correct answers at the last answer of the
  student's newest attempt in this class. It is 0 when the student has
  no attempt.
- A student who has never answered a question gets day_streak 0.
- A student with no attempt in this class gets answer_streak 0. Their
  day_streak can still be above 0 from answers in other classes.

Errors:
- `401`: Missing or invalid authentication token.
- `404`: Unknown class ID.
- `403`: For an existing class, the requester does not have the
  student role or is not enrolled.

## POST /api/classes/{id}/lectures/

Allows a professor to upload a lecture recording to a class they own.

Authentication: Required (professor and class owner).

Content-Type: multipart/form-data

Request fields:
- title: Required string (max 255 characters)
- recording: Required audio/video file
- Allowed extensions: .mp3, .mp4, .m4a, .wav
- Maximum file size: 100 MB

Success: 201 Created

```json
{
  "id": 1,
  "title": "Introduction",
  "status": "pending"
}
```

Errors:
- 400: Invalid file type, oversized file, or missing fields
- 403: Student or professor who does not own the class
- 404: Class does not exist
- 401: Missing or invalid authentication

Transcription:
- New lectures are saved with status "pending".
- Transcription job integration depends on Celery and Redis setup.