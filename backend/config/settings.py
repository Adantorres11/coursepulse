"""Django settings for CoursePulse.

All environment-specific values come from environment variables (see .env.example).
"""
import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-secret-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]
CORS_ALLOWED_ORIGINS = [
    o
    for o in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "accounts",
    "core",
    "classrooms",
    "quizzes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# PostgreSQL when DB_HOST is set (Docker). SQLite fallback keeps local runs and CI tests simple.
if os.environ.get("DB_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "coursepulse"),
            "USER": os.environ.get("DB_USER", "coursepulse"),
            "PASSWORD": os.environ.get("DB_PASSWORD", "coursepulse"),
            "HOST": os.environ["DB_HOST"],
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Celery (background jobs). Redis carries the jobs and stores the results.
# Eager means tasks run inline with no Redis and no worker. That is the default
# outside Docker (DB_HOST not set), so tests and local runs work alone.
CELERY_TASK_ALWAYS_EAGER = (
    os.environ.get("CELERY_TASK_ALWAYS_EAGER", "0" if os.environ.get("DB_HOST") else "1") == "1"
)
CELERY_TASK_EAGER_PROPAGATES = CELERY_TASK_ALWAYS_EAGER
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "")
if not CELERY_BROKER_URL:
    if CELERY_TASK_ALWAYS_EAGER:
        CELERY_BROKER_URL = "memory://"
    else:
        raise ImproperlyConfigured("CELERY_BROKER_URL is not set. Copy it from .env.example into .env.")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE
# Acknowledge a job only after it finishes, and take one job at a time,
# so a job is delivered again if the worker dies while running it.
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_REJECT_ON_WORKER_LOST = True
# Seconds. Sized for a 4-hour lecture split into parts.
CELERY_TASK_TIME_LIMIT = int(os.environ.get("CELERY_TASK_TIME_LIMIT", "3000"))
CELERY_TASK_SOFT_TIME_LIMIT = int(os.environ.get("CELERY_TASK_SOFT_TIME_LIMIT", "2700"))
# Redis redelivers an unacknowledged job after this many seconds. Keep it above the hard limit.
CELERY_BROKER_TRANSPORT_OPTIONS = {"visibility_timeout": 7200, "socket_connect_timeout": 3}
CELERY_BROKER_CONNECTION_TIMEOUT = 3
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_PUBLISH_RETRY_POLICY = {
    "max_retries": 1,
    "interval_start": 0,
    "interval_step": 0.5,
    "interval_max": 1,
}
CELERY_WORKER_MAX_TASKS_PER_CHILD = 10
CELERY_WORKER_MAX_MEMORY_PER_CHILD = 500000  # KB
CELERY_RESULT_EXPIRES = 86400

CELERY_BEAT_SCHEDULE = {
    "reap-stuck-lectures": {
        "task": "quizzes.tasks.reap_stuck_lectures",
        "schedule": 300.0,
    },
}

# OpenAI (Whisper transcription and question generation).
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
if sys.argv[1:2] == ["test"]:
    # Tests must never spend real credits.
    OPENAI_API_KEY = ""
TRANSCRIPTION_MAX_COST_USD = float(os.environ.get("TRANSCRIPTION_MAX_COST_USD", "2.00"))
TRANSCRIPTION_MAX_SECONDS = int(os.environ.get("TRANSCRIPTION_MAX_SECONDS", "14400"))
QUESTION_MODEL = os.environ.get("QUESTION_MODEL", "gpt-6-luna")
QUESTION_MAX_COST_USD = float(os.environ.get("QUESTION_MAX_COST_USD", "0.25"))
QUESTION_WORDS_PER_QUESTION = int(os.environ.get("QUESTION_WORDS_PER_QUESTION", "300"))
QUESTION_MIN_COUNT = int(os.environ.get("QUESTION_MIN_COUNT", "20"))
QUESTION_MAX_COUNT = int(os.environ.get("QUESTION_MAX_COUNT", "40"))
QUESTION_FLOOR_COUNT = int(os.environ.get("QUESTION_FLOOR_COUNT", "10"))
QUESTION_TIMEOUT_SECONDS = int(os.environ.get("QUESTION_TIMEOUT_SECONDS", "180"))
LECTURE_UPLOAD_MAX_BYTES = int(os.environ.get("LECTURE_UPLOAD_MAX_BYTES", str(2 * 1024 ** 3)))

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
    ],
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
