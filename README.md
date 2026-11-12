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

`.env.example` lists the five `CELERY_*` variables and what each one does.

### Planned lecture pipeline

This pipeline is planned. It is not built yet. These are the decisions for it:

1. Two tasks run in order: `transcribe_lecture(lecture_id)`, then `generate_questions(lecture_id)`.
2. Each task takes only a lecture id and reads and writes the database. You can retry either task alone.
3. The upload endpoint links the tasks after it saves the file, with the line below. A chain runs tasks one after another. `.si` stops the first task's return value from going to the second task.
4. The job logic lives in plain functions. The Celery tasks only call them. The trigger can later move to AWS (S3, Lambda, SQS) without a rewrite.
5. Whisper and the LLM sit behind small wrapper functions, so tests can replace them with fakes.
6. `generate_questions` saves all questions in one database transaction. A transaction either saves everything or saves nothing, so a lecture never has a partial question set.

```python
chain(transcribe_lecture.si(lecture.id), generate_questions.si(lecture.id)).delay()
```

The tickets are SCRUM-69 (upload), SCRUM-70 (transcription), SCRUM-71 (questions), and SCRUM-92 (pipeline tests).

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
