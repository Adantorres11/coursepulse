API Contract (Sprint 1)
The single source of truth for what the frontend and backend agree on.
Change this file in a PR before changing any endpoint shape, so both sides can review it.

Base URL (local): http://localhost:8000
Auth: token authentication for protected endpoints.
Send Authorization: Token <token> with protected requests.
Registration and login do not require a token.
Lecture data is hardcoded through the seed script.
GET /api/lectures/ and GET /api/lectures/{id}/quiz/ need no token; an invalid token still returns 401. POST /api/lectures/{id}/answers/ requires a token.
GET /api/health/
Liveness check for Docker and CI.
{ "status": "ok", "service": "coursepulse-api" }
GET /api/lectures/
Lectures with a published quiz, newest first. Powers the Student Hub.
A lecture is listed when its published_at has arrived and it has at least one question.
Drafts, future publications, and lectures without questions are never returned.
Success: 200 OK. Returns [] when no lecture qualifies.
classroom_id identifies the classroom. classroom is its name, set by whoever created it.
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
GET /api/lectures/{id}/quiz/
The full quiz for one lecture. Powers the Arena (game screen).
Success: 200 OK.
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
Field rules
- choices: exactly 4 strings.
- The quiz does not include the correct answer. The correct answer comes from
  POST /api/lectures/{id}/answers/.
- difficulty: "easy" (100 pts), "medium" (200 pts) or "hard" (300 pts).
- Questions are returned in a fixed order.
- answered_question_ids: the ids of the questions the logged-in student has
  answered in their open attempt. total_points: the points of that open attempt.
  The open attempt is the student's newest attempt for this lecture with no
  completed_at. Send the token to get these fields. When the request has no
  token, or there is no open attempt, they are [] and 0.
Errors: 404 with {"detail": "Not found."} for an unknown lecture id. The same
404 is returned when the lecture is not published yet or has no questions.
POST /api/lectures/{id}/answers/
Grades one answer on the server. The Arena (game screen) calls it after each
question. Requires a token. Send Content-Type: application/json.

Request:
{
  "question_id": 11,
  "chosen_index": 2
}
Success: 201 Created
{
  "is_correct": true,
  "points_awarded": 100,
  "total_points": 100,
  "correct_index": 2
}
Rules:
- The lecture must be available, as in GET /api/lectures/{id}/quiz/.
  The question must belong to that lecture.
- question_id: integer. chosen_index: integer 0-3, or null when time
  ran out. Both fields are required. chosen_index is still required
  when it is null.
- The server measures the time. It counts from the question's start call
  (POST /api/lectures/{id}/questions/{question_id}/start/) to the moment
  the answer arrives. The client does not send a time.
- The screen shows 15 seconds per question: QUESTION_TIME_LIMIT_MS = 15000.
  The server allows 1000 ms more for network delay: TIME_GRACE_MS = 1000.
  An answer timed out when the measured time is greater than 16000 ms.
- A null answer is never correct, so is_correct is false.
- An answer to a question that was not started in the open attempt is
  rejected. Call the start endpoint first.
- Only an enrolled student can answer. The student must have the student
  role and must be enrolled in the class of the lecture.
- points_awarded is 100 for an easy question, 200 for medium, and 300 for
  hard. A correct answer gets 50 more points when it is the 3rd or later
  correct answer in a row in the attempt. The current answer counts toward
  the run. Every correct answer after the 3rd also gets the 50. It is 0
  when the answer is wrong or timed out. A timed-out answer is never
  correct, so is_correct is false.
- Daily cap: each student gets full base points for the first 35
  first-attempt questions answered in a UTC day. After that, a correct
  answer earns 25% of the base points: 25 for easy, 50 for medium, and 75
  for hard. The 50-point streak bonus is never reduced. Only first-attempt
  answers count toward the cap, and only first-attempt answers are reduced
  by it. Replay answers never count toward the cap and are never reduced.
- The first attempt at each lecture is the only attempt that counts toward
  class totals. For a replay, points_awarded and total_points are the
  score of that replay only. They do not change the leaderboard or the
  class stats.
- A wrong or timed-out answer sets the run of correct answers to 0.
- A new attempt starts with a run of correct answers of 0, so a replay
  starts the bonus count again.
- total_points is the running total of the attempt, including this answer.
- correct_index is always returned, so the screen can show green and red
  feedback.
- The server picks the attempt. It uses the student's open attempt for the
  lecture, the one that the start call created or reused.
- When every question in the lecture has an answer, the attempt is completed
  (completed_at is set). The next start call, not the next answer, begins a
  new attempt.
- A second answer to the same question in the same attempt is rejected.
Errors:
- 400: Invalid body. Errors appear under the field name, as in
  POST /api/auth/register/.
{
  "chosen_index": ["Ensure this value is less than or equal to 3."]
}
- 400: The question already has an answer in this attempt.
{
  "detail": "This question was already answered in this attempt."
}
- 400: The question was not started in the open attempt.
{
  "detail": "Start this question before answering."
}
- 401: Missing or invalid authentication token.
- 403: The user does not have the student role.
{
  "detail": "Only students can answer questions."
}
- 403: The student is not enrolled in the class of the lecture.
{
  "detail": "You must be enrolled in this class."
}
- 404: {"detail": "Not found."} for an unknown or unavailable lecture, or
  a question that is not in that lecture.
Check order: 401, then 404 for the lecture, then 403, then 400 for
body validation, then 404 for a question not in the lecture, then 400
for a question that was not started or was already answered.
POST /api/lectures/{id}/questions/{question_id}/start/
Marks the moment a question appears. The Arena calls it when it shows the
question. Requires a token. Send no body.

Success: 201 Created the first time the question is started in the open
attempt. 200 OK when it was already started in the open attempt. The
original time is kept.
{
  "question_id": 11,
  "started_at": "2026-11-11T15:00:00Z"
}
Rules:
- The lecture must be available, as in GET /api/lectures/{id}/quiz/.
  The question must belong to that lecture.
- The server uses the student's open attempt for the lecture (the newest one
  with no completed_at), or starts a new one. A student has at most one open
  attempt per lecture.
- Only an enrolled student can start a question. The student must have the
  student role and must be enrolled in the class of the lecture.
- The server measures the answer time from started_at.
Errors:
- 400: The question already has an answer in this attempt.
{
  "detail": "This question was already answered in this attempt."
}
- 401: Missing or invalid authentication token.
- 403: {"detail": "Only students can answer questions."} when the user
  does not have the student role.
- 403: {"detail": "You must be enrolled in this class."} when the
  student is not enrolled in the class of the lecture.
- 404: {"detail": "Not found."} for an unknown or unavailable lecture, or
  a question that is not in that lecture.
Check order: 401, then 404 (unknown or unavailable lecture, or a
question not in it), then 403, then 400.
Known Sprint 1 shortcuts (tracked for Sprint 2)
- No class-code join yet.
Authentication
Send JSON request bodies with Content-Type: application/json.
POST /api/auth/register/
Creates an account. No token required.

Request:
{
  "email": "student@example.com",
  "username": "torres11",
  "password": "Maple!River82",
  "role": "student"
}
Rules:
- Email must be valid and at most 150 characters.
- Emails are trimmed and stored in lowercase.
- Duplicate emails are rejected regardless of capitalization.
- Username is required.
- Usernames are trimmed. Blank usernames are rejected with
  "Enter a username."
- A username uses letters, numbers, underscores, or hyphens.
  It cannot be an email address.
- Usernames are unique regardless of capitalization.
  "Torres11" and "torres11" are the same username.
  A taken username is rejected with "That username is already taken."
- The stored username keeps the capitalization the person chose.
- Role must be "student" or "professor".
- Password must have at least 8 characters and pass Django's
  checks for common, entirely numeric, and user-similar passwords.
Success: 201 Created
{
  "token": "<token>",
  "user": {
    "id": 1,
    "email": "student@example.com",
    "username": "torres11",
    "role": "student"
  }
}
Invalid input: 400 Bad Request, with errors under the relevant field.

Duplicate email example:
{
  "email": ["An account with this email already exists."]
}
Blank username example:
{
  "username": ["Enter a username."]
}
Taken username example:
{
  "username": ["That username is already taken."]
}
Weak password example:
{
  "password": [
    "This password is too short. It must contain at least 8 characters."
  ]
}
Password error wording can vary according to the failed check.
POST /api/auth/login/
Logs in using email and password. The username is not a login id.
No token required.

Request:
{
  "email": "student@example.com",
  "password": "Maple!River82"
}
Success: 200 OK, with the same token and user response
structure as registration.

Invalid credentials: 401 Unauthorized
{
  "detail": "Invalid email or password."
}
Missing or non-string credentials: 400 Bad Request
{
  "detail": "Email and password are required."
}
GET /api/auth/me/
Returns the current user's information. Requires this header:
Authorization: Token <token>
Success: 200 OK
{
  "id": 1,
  "email": "student@example.com",
  "username": "torres11",
  "role": "student"
}
Missing token: 401 Unauthorized
{
  "detail": "Authentication credentials were not provided."
}
Invalid token: 401 Unauthorized
{
  "detail": "Invalid token."
}
Tokens are reused on login and do not automatically expire.
Existing users without a role profile receive "role": null.

Usernames
The public name for a person is their username. Login stays email
and password.

Other screens should import one helper instead of reading email,
first name, or last name:

    from accounts.usernames import display_username

display_username(user) returns the username to show. It never returns
an email. When a legacy account still has an email stored as the
username, the helper returns the part before @, keeping letters,
numbers, underscores, and hyphens.

The React helper is displayUsername in frontend/src/lib/displayUsername.ts.
It reads username, then name, then display_name. It does not read email.

The same value is sent as:
- username on POST /api/auth/register/, POST /api/auth/login/, and
  GET /api/auth/me/
- name and username on a professor, a roster row, and a results row
- display_name and username on a leaderboard row

Existing accounts receive a default username in migration
accounts.0002_assign_default_usernames. The default is the part of
the email before @, with _2, _3, and so on when that name is taken.
Accounts that already have a username without @ are left as they are.

GET /api/classes/
Returns only the logged-in student's enrolled classrooms.
Requires a student account and this header:
Authorization: Token <token>
Success: 200 OK
[
  {
    "id": 1,
    "name": "Software Engineering",
    "course_code": "CS 3398",
    "professor": {
      "id": 2,
      "name": "alexsmith",
      "username": "alexsmith"
    },
    "quiz_count": 5,
    "new_quiz_count": 3
  }
]
Rules:
- Classes are ordered by name, then ID.
- No enrollments returns [] with 200 OK.
- Professor is null if no professor is assigned.
- professor.name and professor.username are the public username from
  display_username. They are never an email address. A legacy account
  whose stored username is still an email is shown as the part before @.
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
- 401: Missing or invalid authentication token.
- 403: Authenticated user does not have the student role.
Class access codes
Each classroom has a unique six-character access code.
Generated codes use uppercase letters and numbers.
Code input is case-insensitive; surrounding whitespace is ignored.
The demo classroom's code is DEMO01.

Both endpoints below require a student account and this header:
Authorization: Token <token>
GET /api/classes/lookup/?code=ABC123
Previews a classroom without enrolling the student.

Success: 200 OK
{
  "id": 1,
  "name": "Software Engineering",
  "course_code": "CS 3398",
  "professor": {
    "id": 2,
    "name": "alexsmith",
    "username": "alexsmith"
  },
  "quiz_count": 5,
  "new_quiz_count": 3
}
Fields and quiz-count rules match GET /api/classes/.
Professor may be null when no professor is assigned.
POST /api/classes/join/
Enrolls the logged-in student in the classroom.

Send Content-Type: application/json.

Request:
{
  "code": "ABC123"
}
Success:
- 201 Created for a new enrollment.
- 200 OK if already enrolled; no duplicate is created.
- Both return the same classroom response structure as lookup.
Lookup and join errors
Unknown six-character code: 404 Not Found
{
  "detail": "We couldn't find a class with that code"
}
Other errors:
- 400: Missing or malformed code; errors appear under code.
- 401: Missing or invalid authentication token.
- 403: Authenticated user does not have the student role.
GET /api/classes/{id}/leaderboard/
Returns the class's enrolled students ranked by total quiz points.
Requires a student account and token authentication.

Success: 200 OK
[
  {
    "rank": 1,
    "display_name": "bharat",
    "username": "bharat",
    "points": 500,
    "is_current_user": true
  },
  {
    "rank": 1,
    "display_name": "alex",
    "username": "alex",
    "points": 500,
    "is_current_user": false
  },
  {
    "rank": 3,
    "display_name": "sam",
    "username": "sam",
    "points": 0,
    "is_current_user": false
  }
]
Rules:
- Includes enrolled users with the student role.
- Points are the sum of total_points from completed attempts across
  all lectures in this class. Incomplete attempts are excluded.
- Only the student's first attempt at each lecture counts, once it is
  completed. Replays add 0.
- Attempts at a lecture whose published_at is empty or still in the
  future add 0.
- Attempts from other classes are excluded.
- Students are ordered by points descending, then user ID ascending
  for consistent ordering within ties.
- Equal points share the same rank using competition ranking:
  1, 1, 3.
- Students with no completed attempts receive zero points.
- Zero-point students appear last and share the same rank.
- display_name and username are the public username from
  display_username. They are the same value.
- They are never an email address, a full name, or the word "Student".
- A legacy account whose stored username is still an email is shown
  as the part before @.
- is_current_user is true only for the requesting student's entry.
- The response is an unpaginated array.
Errors:
- 401: Missing or invalid authentication token.
- 404: Unknown class ID.
- 403: For an existing class, the requester does not have the
  student role or is not enrolled.
GET /api/classes/{id}/stats/
Returns one student's progress in one class. The Class Hub screen uses
it. Requires a student account and token authentication.

Success: 200 OK
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
- total_points is the sum of total_points from the student's first
  attempt at each lecture in this class, once that attempt is completed.
  Replays add 0. Attempts at a lecture whose published_at is empty or
  still in the future add 0. It matches the student's points in the
  leaderboard.
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
- 401: Missing or invalid authentication token.
- 404: Unknown class ID.
- 403: For an existing class, the requester does not have the
  student role or is not enrolled.
POST /api/classes/
Creates a new class owned by the logged-in professor.

Authentication: Required (professor only).

Request:
{
  "name": "Software Engineering"
}
Success: 201 Created
{
  "id": 1,
  "name": "Software Engineering",
  "access_code": "ABC123"
}
Rules:
- Class name is required and cannot be blank.
- The professor is automatically assigned as the class owner.
- A unique 6-character access code is generated automatically.
Errors:
- 400: Missing or blank class name.
- 403: User is not a professor.
- 401: Missing or invalid authentication.
GET /api/professor/classes/
Returns all classes owned by the logged-in professor.

Authentication: Required (professor only).

Success: 200 OK
[
  {
    "id": 1,
    "name": "Software Engineering",
    "access_code": "ABC123",
    "student_count": 25,
    "lecture_count": 8
  }
]
Rules:
- Returns only classes owned by the logged-in professor.
- Student count includes enrolled students.
- Lecture count includes all lectures in the class.
- Returns an empty array if the professor has no classes.
Errors:
- 401: Missing or invalid authentication.
- 403: User is not a professor.
Class Results
GET /api/classes/{id}/results/
Returns student results and per-question accuracy for a class.

Authentication: Required. Only the professor who owns the class can access the results.

Response: 200 OK
{
  "students": [
    {
      "student_id": 1,
      "name": "ada",
      "username": "ada",
      "total_points": 150,
      "quizzes_played": 3
    }
  ],
  "lectures": [
    {
      "lecture_id": 1,
      "title": "Introduction to Python",
      "questions": [
        {
          "question_id": 1,
          "prompt": "What is Python?",
          "answer_count": 10,
          "correct_count": 8,
          "accuracy_percent": 80.0
        }
      ]
    }
  ]
}
- name and username are the public username from display_username.
  They are never an email address.
- quizzes_played counts distinct lectures with completed attempts.
- Question accuracy is calculated from completed attempts.
- accuracy_percent is null when no answers exist.
- Students without completed quizzes have zero quizzes played.
Errors:
- 401: Authentication required.
- 403: User is not a professor or does not own the class.
- 404: Class not found.
Unpublish Lecture
POST /api/lectures/{id}/unpublish/
Unpublishes a lecture by setting its published_at field to null.

Authentication: Required. Only the professor who owns the lecture's class can unpublish it.

Request body: None.

Response: 200 OK
{
  "id": 1,
  "published_at": null
}
Unpublishing hides the quiz from students while preserving existing attempts and answers.

Errors:
- 401: Authentication required.
- 403: User is not a professor or does not own the lecture.
- 404: Lecture not found.
GET /api/classes/{id}/roster/
Returns all students enrolled in the specified classroom.

Authentication: Required (professor only).

Success: 200 OK
[
  {
    "name": "ada",
    "username": "ada",
    "joined_at": "2026-11-12T18:00:00Z"
  },
  {
    "name": "sam",
    "username": "sam",
    "joined_at": "2026-11-12T18:05:00Z"
  }
]
Rules:
- Only the professor who owns the classroom can access its roster.
- Returns each enrolled student's public username and join date.
- name and username are the public username from display_username.
  They are never an email address or a full name.
- Students are ordered by join date, earliest first.
- Returns an empty array if no students are enrolled.
Errors:
- 401: Missing or invalid authentication.
- 403: User is not a professor or does not own the classroom.
- 404: Unknown classroom ID.

## POST /api/classes/{id}/lectures/

Allows a professor to upload a lecture recording to a class they own.

Authentication: Required (professor and class owner).

Content-Type: multipart/form-data

Request fields:
- title: Required string (max 255 characters)
- recording: Required audio/video file
- Allowed extensions (case does not matter): .mp3, .m4a, .wav, .aac, .ogg, .flac, .mp4, .mov, .mkv, .webm, .avi
- Maximum file size: 2 GB by default. The server setting LECTURE_UPLOAD_MAX_BYTES sets the limit.
- If the file is too large, the error text is "File must be {N} MB or smaller." N is the limit in MB.
- The server checks the file signature (the first bytes of the file) at upload. It does not check the content type.
- The background worker reads the real audio and video streams with ffprobe (a tool that reports what a media file contains).

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
- New lectures are saved with status "pending" and are not visible to students (published_at is null).
- Status values are "pending", "processing", "ready", and "failed".
- After the upload is saved, processing starts in the background.
- If processing cannot start, the response is still 201 and status is "failed".
- The status endpoint then gives the error_message "Couldn't start processing, try again."

## GET /api/professor/classes/{id}/lectures/

Returns all lectures belonging to a professor's class, including unpublished lectures.

Authentication: Required (professor and class owner).

Success: 200 OK

Example response:

```json
[
  {
    "id": 2,
    "title": "Introduction to AI",
    "status": "published",
    "published_at": "2026-11-16T18:00:00Z"
  },
  {
    "id": 1,
    "title": "Machine Learning Basics",
    "status": "pending",
    "published_at": null
  }
]
```

Rules:
- Only the professor who owns the classroom can access its lectures.
- Includes published and unpublished lectures.
- Returns an empty array when the class has no lectures.
- A published lecture is labeled "published". Otherwise the label is the lecture's processing status: "pending", "processing", "ready", or "failed".
- Lectures made before uploads existed have no recording and are labeled "ready".

Errors:
- 401: Authentication required.
- 403: User is not the classroom owner.
- 404: Unknown classroom ID.

## GET /api/lectures/{id}/status/

Returns the current processing status of a lecture.

Authentication: Required (professor and class owner).

Success: 200 OK

```json
{
  "id": 1,
  "status": "processing",
  "progress_message": "Transcribing part 3 of 7",
  "error_message": "",
  "notice": ""
}
```

Possible statuses:

- pending: Lecture is waiting to be processed.
- processing: The lecture is being transcribed or questions are being generated.
- ready: The server generated the questions and saved them as unpublished drafts for the professor to review. Students see nothing until the professor publishes the lecture.
- failed: Processing failed.

For a failed lecture:

```json
{
  "id": 1,
  "status": "failed",
  "progress_message": "",
  "error_message": "Something went wrong. Try again.",
  "notice": ""
}
```

Rules:
- Only the professor who owns the lecture's classroom can access its status.
- The error message is empty unless the lecture status is failed.
- The progress message is empty unless the lecture status is processing.
- The notice is empty unless the lecture status is ready and the server has something to tell the professor.
- Every error message is one of the strings in the next list.

Possible error messages:
- "This file is empty. Try re-uploading it."
- "We couldn't read this file. Try re-uploading it."
- "This video has no audio."
- "Recording too short to make a quiz."
- "Recording is longer than {hours} hours. Upload a shorter one." ({hours} is the server limit, 4 by default.)
- "No speech was detected."
- "The transcript looks incomplete. Try again."
- "Server isn't set up for transcription."
- "The transcription key was rejected. Ask the site admin to check it."
- "Transcription credits ran out."
- "This recording is over the transcription cost limit."
- "Transcription service is busy. Try again later."
- "Processing took too long."
- "Processing was interrupted, retry."
- "Recording file not found."
- "We couldn't open the recording file."
- "The server ran out of space. Try again later."
- "Couldn't start processing, try again."
- "Couldn't start question generation, retry."
- "Server isn't set up for question generation."
- "The question generation key was rejected. Ask the site admin to check it."
- "Question generation credits ran out."
- "This lecture is over the question generation cost limit."
- "Question generation service is busy. Try again later."
- "Couldn't read the generated questions. Try again."
- "No course content was found in this transcript."
- "Only {count} usable questions were made. Try again." ({count} is below the floor, 10 by default.)
- "This quiz is published or has student activity, so its questions were not changed."
- "Something went wrong. Try again."

Every notice is one of the strings in the next list.

Possible notices:
- "Generated {count} questions (target {target}). Add more in review if needed."
- "Kept your {count} questions. No new questions were needed."

Errors:
- 401: Missing or invalid authentication.
- 403: User is not a professor or does not own the classroom.
- 404: Unknown lecture ID.

## POST /api/lectures/{id}/retry/

Restarts processing for a failed lecture.

Authentication: Required (professor and class owner).

Request: No body required.

Success: 202 Accepted

```json
{
  "id": 1,
  "status": "pending",
  "error_message": ""
}
```

Rules:
- Only failed lectures can be retried.
- The lecture status is reset to pending.
- The previous error message is cleared.
- A retry clears the notice.
- The lecture is submitted to the Celery processing pipeline.
- If the pipeline is unavailable, the failed status and previous error message are restored.
- A retry keeps the uploaded file.
- If a transcript for the same recording is already saved, the retry skips transcription and goes straight to question generation.
- A retry continues from the transcript parts that were already finished.
- A retry after failed question generation reuses the saved transcript and keeps questions the professor wrote or edited.

Errors:
- 400: Lecture is not failed or is already being retried.
- 401: Missing or invalid authentication.
- 403: User is not a professor or does not own the classroom.
- 404: Unknown lecture ID.
- 503: Processing pipeline is unavailable.

Dependency:
- Transcription is built in SCRUM-70. Question generation is built in SCRUM-71.

## Professor question review

Authentication: Required. Only the professor who owns the lecture's classroom can use these endpoints. A student, another professor, or a user with no role receives 403. The response does not include the questions.

These endpoints are how a professor reviews the draft questions, edits them, and publishes the quiz. Students never receive unpublished questions. GET /api/lectures/ and GET /api/lectures/{id}/quiz/ stay limited to published quizzes, and they still omit correct_index.

The generation record stored on a question is never returned by these endpoints, by the student quiz, or by the lecture list. A question the professor adds has a null generation record, so a later question-generation run keeps it. Editing a question does not change or remove the generation record already stored for it. The stored original text is what marks that edit.

Questions are ordered by position, then id. Positions start at 0, the same numbering question generation uses. After a delete they are 0, 1, 2, and so on, with no gaps.

### GET /api/lectures/{id}/questions/

Returns every question for the lecture, including the correct answer. Draft and published lectures both return 200.

Success: 200 OK

```json
[
  {
    "id": 1,
    "prompt": "What is Python?",
    "choices": ["Language", "Database", "Browser", "OS"],
    "correct_index": 0,
    "difficulty": "easy",
    "position": 0
  }
]
```

### POST /api/lectures/{id}/questions/

Adds one question to a ready, unpublished lecture. The server assigns position. A position in the request is ignored. The first question is position 0. Each later question is placed after the current last question. The new question's generation record is null.

Request:

```json
{
  "prompt": "What is Django?",
  "choices": ["Framework", "OS", "Browser", "Database"],
  "correct_index": 0,
  "difficulty": "easy"
}
```

Success: 201 Created. Returns the created question, including its position.

Choice rules:
- choices is exactly four strings.
- Each choice is trimmed. A choice that is empty after trimming is rejected.
- Two choices that match after trimming and case-folding are rejected. "Yes" and " yes " are duplicates.
- The stored choices are the trimmed strings.
- correct_index is an integer from 0 to 3.
- difficulty is "easy", "medium", or "hard".

### PATCH /api/lectures/{id}/questions/{question_id}/

Updates one question on a ready, unpublished lecture. Send only the fields that change. position cannot be changed here. The generation record is left as it was.

Success: 200 OK. Returns the updated question.

A question that already has a student answer cannot be replaced. Changing its prompt, choices, correct_index, or difficulty returns 400 and leaves the question, the answer, and the attempt score as they were. Sending the same values again is allowed.

### DELETE /api/lectures/{id}/questions/{question_id}/

Deletes one question from a ready, unpublished lecture.

Success: 204 No Content. The remaining questions keep their order and their positions become 0, 1, 2, with no gaps.

A question that already has a student answer is not deleted. The answer and the attempt score stay. The response is 400:

```json
{
  "detail": "This question has student answers and cannot be deleted."
}
```

### POST /api/lectures/{id}/publish/

Publishes the lecture quiz. No body.

Success: 200 OK

```json
{
  "id": 1,
  "published_at": "2026-11-16T18:00:00Z",
  "message": "Quiz published successfully."
}
```

Rules:
- The lecture status must be "ready". Pending, processing, and failed lectures are rejected, and published_at stays empty.
- The lecture must have at least one question.
- Every question must have exactly four unique non-blank choices, a correct_index from 0 to 3, and a difficulty of easy, medium, or hard.
- A lecture that already has published_at set cannot be published again. Unpublish it first with POST /api/lectures/{id}/unpublish/, then publish it again once it is ready.
- While the quiz is published, or while the lecture status is not "ready", questions cannot be added, edited, or deleted through these endpoints. GET still returns the questions. Unpublish a published quiz before editing it, and wait until status is "ready".
- Unpublishing does not delete attempts or answers.
- No response from these endpoints includes generation.

Errors:
- 400: The lecture is not ready, has no questions, has an invalid question, is already published, or the edit would change a published quiz or a question that has student answers. The message is in detail.
- 401: Missing or invalid authentication.
- 403: The user is not the professor who owns the class.
- 404: Unknown lecture, or a question that is not on that lecture.
