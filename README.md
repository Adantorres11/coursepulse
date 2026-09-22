# CoursePulse

An AI-powered study companion that keeps lecture concepts fresh between class and the exam.
Professors upload a lecture; students play a fast, gamified quiz built from it.
CoursePulse complements lectures. It does not replace them.

Course project for CS 3398 Software Engineering (Fall 2026), Team 009-03.

## Sprint 1 goal: the walking skeleton
Run `docker compose up`, open the React app, see the hardcoded quiz served by the Django API,
and play through all 5 questions with a score.

## Quick start
**Prerequisites:** Docker Desktop, Git.

1. **Clone the repo and move into it**
   ```bash
   git clone <repo-url> && cd coursepulse
   ```

2. **Create your local environment file**
   ```bash
   cp .env.example .env
   ```
   This holds your local DB credentials and secrets. It's gitignored, so it's yours alone and never gets committed.

3. **Build and start everything**
   ```bash
   docker compose up --build
   ```
   Spins up Postgres, the Django API, and the React frontend together, wired to talk to each other.

4. **Open it up**

   | Service  | URL                                |
   |----------|-------------------------------------|
   | Frontend | http://localhost:5173              |
   | API      | http://localhost:8000/api/health/  |
   | Postgres | localhost:5432 (see `.env`)        |

Stop with `Ctrl+C`. Wipe the database and start fresh with `docker compose down -v`.

## Repository layout
```
backend/    Python (Django + Django REST Framework) API
frontend/   React (Vite) + TypeScript + Tailwind CSS
docs/       Developer docs that live next to the code (API contract)
.github/    PR template and CI workflows
```
Project-level documentation (product overview, tech stack, architecture, sprint notes) lives in our Confluence team space.

## Tech stack
| Layer      | Tech                          |
|------------|--------------------------------|
| Frontend   | React (Vite) + TypeScript + Tailwind CSS |
| Backend    | Python (Django REST Framework) |
| Database   | PostgreSQL                     |

## Running without Docker (optional)
**Backend**

1. Create a virtual environment and install dependencies:
   ```bash
   cd backend
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Run migrations and start the server:
   ```bash
   python manage.py migrate && python manage.py runserver
   ```
   No `DB_HOST` set means it falls back to SQLite automatically, so no Postgres is needed for this path.

**Frontend**

```bash
cd frontend
npm install && npm run dev
```

## Tests
```bash
cd backend && python manage.py test
cd frontend && npm run build
```
