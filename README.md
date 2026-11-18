# CoursePulse

CoursePulse is a study companion for the stretch after a lecture, when the material still feels familiar and is easy to lose. A professor publishes that lecture as a short quiz. Students join the class and play it before the next session.

Rereading notes makes an idea feel known. Recalling it is what makes it stick. Each question asks for something from that lecture, and the score depends on how hard the recall is: easy is 100 points, medium is 200, and hard is 300. A session is only a few questions, so it fits between class meetings, and the score is specific to that lecture.

Those points are also a competition. Finished quizzes add up, and students in a class are ranked against each other. Moving up that ranking is a reason to play again, alongside remembering the lecture.

## How it works

A professor opens a class and shares a six-character code. A student creates an account, enters the code, and joins. A lecture shows up in the Student Hub once it is published and has questions. The student answers one question at a time. The quiz ends on a score, and that score counts toward the student's place in the class.

| Screen | What you do there |
| --- | --- |
| Landing | See what CoursePulse is, then sign up or log in |
| Sign up / Log in | Create an account as a student or a professor |
| Join class | Enter the six-character class code |
| Student Hub | Choose a published lecture |
| Quiz | Answer the questions and see the score |

The repository includes a demo class and one published lecture, Agile and Scrum, with five questions. The seed command below loads it. Running the command again updates those questions in place.

## Repository

```
.
├── backend/                 Django REST Framework API
│   ├── accounts/            Registration, login, and roles
│   ├── classrooms/          Classes, join codes, standings, and stats
│   ├── quizzes/             Lectures, questions, attempts, and the demo seed
│   ├── config/              Settings, URL routing, and the Celery app
│   ├── core/                Health check and the sample background task
│   ├── Dockerfile
│   ├── manage.py
│   └── requirements.txt
├── frontend/                React, Vite, TypeScript, and Tailwind
│   ├── public/assets/       Logo
│   ├── src/
│   │   ├── components/      Landing, auth, join class, student hub, and quiz
│   │   ├── data/            Sample lecture and quiz fixtures
│   │   ├── lib/             API client
│   │   ├── types/
│   │   ├── App.tsx          Routes
│   │   └── main.tsx
│   ├── Dockerfile
│   ├── package.json
│   └── vite.config.ts
├── docs/
│   └── api-contract.md      Request and response shapes
├── .env.example             Local environment template
├── docker-compose.yml       Postgres, Redis, API, worker, and frontend
└── README.md
```

## Run

Docker and Git.

```bash
git clone <repo-url>
cd coursepulse
cp .env.example .env
docker compose up --build
```

| Service | URL |
| --- | --- |
| Frontend | http://localhost:5173 |
| API | http://localhost:8000/api/health/ |

Load the demo lecture once the API is up:

```bash
docker compose exec backend python manage.py seed_demo
```

Stop with Ctrl+C. Reset the database with `docker compose down -v`.

Local database credentials live in `.env`, which is not committed.

## Background jobs

Celery runs slow work in a separate worker process, so the API does not wait for it. Redis is the queue between the API and the worker. A queue is a list of jobs that wait for a worker. `docker compose up --build` starts the `redis` and `worker` services with the rest of the stack.

To run the sample task, start the stack and run this command. It sends the task `core.tasks.ping` to the queue, waits for the worker, and prints `pong`.

```bash
docker compose exec backend python manage.py shell -c "from core.tasks import ping; print(ping.delay().get(timeout=10))"
```

To watch the worker, run this command in a second terminal:

```bash
docker compose logs -f worker
```

The log shows three lines for each run of the sample task. The first says `Task core.tasks.ping[<id>] received`. The second says `core.tasks.ping[<id>]: ping task ran`. The third says `Task core.tasks.ping[<id>] succeeded in ...s: 'pong'`. The worker also prints a warning that it runs as root. The warning is harmless inside the container.

The worker does not reload code. After you change a task, run `docker compose restart worker`.

`.env.example` lists the six `CELERY_*` variables and what each one does.

### Lecture pipeline

A lecture goes through two tasks in order: `transcribe_lecture(lecture_id)`, then `generate_questions(lecture_id)` (SCRUM-71). Each task takes only a lecture id and reads and writes the database. You can retry either task alone.

How it runs:

1. The upload endpoint saves the file. After the save commits, it queues `transcribe_lecture(lecture_id)`.
2. The worker checks the file with ffprobe and turns it into small mono audio with ffmpeg.
3. The worker splits audio longer than 10 minutes into 10-minute parts.
4. The worker sends each part to Whisper, joins the parts, and saves the transcript.
5. The worker then queues `generate_questions(lecture_id)`.
6. The question task works in two stages. Stage 1 reads each section of the transcript and lists the course concepts in it. Stage 2 writes questions for each section, and it sees the whole concept list. The code then checks every question and drops the bad ones. It may ask the model again once, run one round of replacement questions, and run one pass for gotcha questions (questions that test a common mistake). The task saves 20 to 40 draft questions in one transaction. Then the status becomes `ready`. A draft stays hidden: `published_at` stays null until the professor publishes the lecture. If only 10 to 19 questions survive, the task saves them and sets a `notice` that tells the professor. If fewer than 10 survive, the lecture fails.

The worker refuses recordings shorter than 10 seconds.

The upload view queues the job with this line:

```python
transaction.on_commit(lambda: start_lecture_processing(lecture.id))
```

`on_commit` runs the function only after the database transaction saves. Without it, the worker could start before the lecture row exists.

The job logic lives in plain functions. The Celery tasks only call them. The trigger can later move to AWS (S3, Lambda, SQS) without a rewrite. Whisper and the LLM sit behind small wrapper functions, so tests can replace them with fakes. `generate_questions` saves all questions in one database transaction. A transaction either saves everything or saves nothing, so a lecture never has a partial question set.

The tickets are SCRUM-69 (upload), SCRUM-70 (transcription), SCRUM-71 (questions), and SCRUM-92 (pipeline tests).

#### Setup

Put your own key in `.env` as `OPENAI_API_KEY=...`. Never commit it. `CELERY_BROKER_URL` is now required in `.env`. If your `.env` is older, copy that line from `.env.example`, or Compose stops with an error. Then run:

```bash
docker compose up --build
```

The services now include `worker` (runs the tasks) and `beat` (runs the stuck lecture check every 5 minutes).

#### Cost

Whisper costs $0.006 per audio minute. A 75-minute lecture costs about $0.45. A 2-hour lecture costs about $0.72. Silence at the start and end is not sent. `TRANSCRIPTION_MAX_COST_USD` (default $2.00) refuses longer recordings. The worker log shows the minutes and the estimated cost for each lecture.

Question generation uses `QUESTION_MODEL` (default gpt-6-luna). Lecture 4 (about 9,000 words, about 30 questions) costs about 2 to 3 cents, and about 5 cents when replies must be re-asked. `QUESTION_MAX_COST_USD` (default $0.25) stops a lecture that would cost more. The worker log shows tokens and cost per lecture.

#### Progress and errors

`GET /api/lectures/{id}/status/` returns `status`, `progress_message`, and `error_message`.

#### Retry

To retry a failed lecture, call `POST /api/lectures/{id}/retry/`. The retry keeps the file and reuses finished parts. If the transcript is already saved, it skips Whisper. Questions the professor wrote or edited by hand are kept on a retry.

#### Logs

To watch the worker, run `docker compose logs -f worker`. Each line has `lecture=`, `task=`, and `attempt=`.

#### Settings

Set these in `.env`. `.env.example` has the defaults.

| Setting | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | empty | Your own OpenAI key. Set it only in `.env`. |
| `TRANSCRIPTION_MAX_COST_USD` | `2.00` | The app refuses a lecture that costs more than this many US dollars. |
| `TRANSCRIPTION_MAX_SECONDS` | `14400` | The app refuses audio longer than this many seconds (4 hours). |
| `LECTURE_UPLOAD_MAX_BYTES` | `2147483648` | Largest upload in bytes (2 GB). |
| `CELERY_WORKER_CONCURRENCY` | `2` | How many jobs one worker runs at the same time. |
| `CELERY_TASK_TIME_LIMIT` | `3000` | Hard limit in seconds. The worker stops a task that runs longer. |
| `CELERY_TASK_SOFT_TIME_LIMIT` | `2700` | Soft limit in seconds. The task gets an error it can catch to clean up. |
| `QUESTION_MODEL` | `gpt-6-luna` | The model that writes the questions. |
| `QUESTION_MAX_COST_USD` | `0.25` | The app stops a lecture that would cost more than this many US dollars. |
| `QUESTION_WORDS_PER_QUESTION` | `300` | The app aims for one question for every this many transcript words. |
| `QUESTION_MIN_COUNT` | `20` | The lowest target number of questions for a lecture. |
| `QUESTION_MAX_COUNT` | `40` | The highest target number of questions for a lecture. |
| `QUESTION_FLOOR_COUNT` | `10` | A lecture with fewer usable questions than this fails. |
| `QUESTION_TIMEOUT_SECONDS` | `180` | How long one model call may run before the app gives up. |

## Without Docker

With `DB_HOST` unset, the API uses SQLite. Tasks also run eagerly, which means inline in the same process, so you need no Redis and no worker. Run the real pipeline through Docker, so it uses Postgres. SQLite locks the whole database file when the web server and the worker write at the same time.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

```bash
cd frontend
npm install && npm run dev
```

## Tests

```bash
cd backend && python manage.py test
cd frontend && npm run build
```

The tests run tasks inline and need no Redis.
