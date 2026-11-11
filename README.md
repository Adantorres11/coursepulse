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
│   ├── config/              Settings and URL routing
│   ├── core/                Health check
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
├── docker-compose.yml       Postgres, API, and frontend
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
