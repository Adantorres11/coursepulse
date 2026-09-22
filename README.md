# CoursePulse

An AI-powered study companion that keeps lecture concepts fresh between class and the exam.
Professors upload a lecture; students play a fast, gamified quiz built from it.
CoursePulse complements lectures. It does not replace them.

Course project for CS 3398 Software Engineering (Fall 2026), Team 009-03.

## Sprint 1 goal: the walking skeleton
Run `docker compose up`, open the React app, see the hardcoded quiz served by the Django API,
and play through all 5 questions with a score.

## Quick start
Prerequisites: Docker Desktop, Git.

```bash
git clone <repo-url> && cd coursepulse
cp .env.example .env
docker compose up --build
```

| Service  | URL                                   |
|----------|---------------------------------------|
| Frontend | http://localhost:5173                 |
| API      | http://localhost:8000/api/health/     |
| Postgres | localhost:5432 (see `.env`)           |

Stop with `Ctrl+C`, reset the database with `docker compose down -v`.

## Repository layout
```
backend/    Django + Django REST Framework API
frontend/   React (Vite) + Tailwind CSS
docs/       Developer docs that live next to the code (API contract)
.github/    PR template and CI workflows
```
Project-level documentation (product overview, tech stack, architecture, sprint notes) lives in our Confluence team space.

## Tech stack
React (Vite) + Tailwind, Django REST Framework, PostgreSQL.

## Team workflow
1. Pick a Jira ticket and move it to **In Progress**.
2. Branch from `main` using `type/name/SCRUM-XX/short-description`, for example `feat/adan/SCRUM-18/docker-compose`.
   The ticket key in the branch name is what links your code to Jira.
3. Commit small and often. Include the ticket key in commit messages, e.g. `SCRUM-18 add postgres healthcheck`.
4. Open a Pull Request using the template and move the ticket to **In Review**.
5. A teammate reviews it (at least 1 approval). Never commit directly to `main`.
6. Squash-merge, then move the ticket to **Done**.

**AI usage:** allowed, but you must disclose it in the PR and be able to explain every line without notes.

## Running without Docker (optional)
```bash
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate && python manage.py runserver   # uses SQLite when DB_HOST is unset
cd ../frontend && npm install && npm run dev
```

## Tests
```bash
cd backend && python manage.py test
cd frontend && npm run build
```
