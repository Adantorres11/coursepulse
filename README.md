# CoursePulse

CoursePulse is a study companion for the stretch after a lecture, when the material still feels familiar and is easy to lose. A professor publishes that lecture as a short quiz. Students join the class and play it before the next session.

Rereading notes makes an idea feel known. Recalling it is what makes it stick. Each question asks for something from that lecture, and the score depends on how hard the recall is: easy is 100 points, medium is 200, and hard is 300. A session is only a few questions, so it fits between classes, and the score is specific to that lecture.

## How it works

A professor opens a class and shares a six-character code. A student creates an account, enters the code, and joins. A lecture shows up in the Student Hub once it is published and has questions. The student answers one question at a time, and the quiz ends on a score.

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
├── backend/                              Django REST Framework API
│   ├── accounts/                         Registration, login, and roles
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── tests.py
│   │   └── migrations/
│   ├── classrooms/                       Classes, join codes, standings, and stats
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── stats.py
│   │   ├── urls.py
│   │   ├── tests.py
│   │   ├── test_access_codes.py
│   │   ├── test_leaderboard.py
│   │   ├── test_stats.py
│   │   └── migrations/
│   ├── quizzes/                          Lectures, questions, and attempts
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── tests.py
│   │   ├── test_attempts.py
│   │   ├── test_lectures.py
│   │   ├── test_quiz.py
│   │   ├── management/commands/seed_demo.py
│   │   └── migrations/
│   ├── config/                           Settings and URL routing
│   │   ├── settings.py
│   │   └── urls.py
│   ├── core/                             Health check
│   │   ├── views.py
│   │   └── urls.py
│   ├── Dockerfile
│   ├── manage.py
│   └── requirements.txt
├── frontend/                             React, Vite, TypeScript, and Tailwind
│   ├── public/assets/                    Logo
│   ├── src/
│   │   ├── components/
│   │   │   ├── LandingPage.tsx
│   │   │   ├── AuthPage.tsx
│   │   │   ├── JoinClassPage.tsx
│   │   │   ├── StudentHub.tsx
│   │   │   ├── QuizPage.tsx
│   │   │   └── quiz.tsx
│   │   ├── data/                         Sample lecture and quiz fixtures
│   │   ├── lib/                          API client
│   │   ├── types/api.ts
│   │   ├── App.tsx                       Routes
│   │   ├── main.tsx
│   │   └── index.css
│   ├── Dockerfile
│   ├── env.example
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
├── docs/
│   └── api-contract.md                   Request and response shapes
├── .github/
│   └── pull_request_template.md
├── .env.example                          Local environment template
├── .gitignore
├── docker-compose.yml                    Postgres, API, and frontend
└── README.md
```

Django app boilerplate (`admin.py`, `apps.py`, `__init__.py`) sits beside the modules above. Database migrations live in each `migrations/` directory.

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

## Without Docker

With `DB_HOST` unset, the API uses SQLite.

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
