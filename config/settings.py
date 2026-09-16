import secrets
import sys
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

if "pytest" in sys.modules:
    SECRET_KEY = env("SECRET_KEY", default=secrets.token_urlsafe(50))
else:
    SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
INSPIRE_THROTTLE_SECONDS = env.float("INSPIRE_THROTTLE_SECONDS", default=1.0)
INSPIRE_TIMEOUT_SECONDS = env.float("INSPIRE_TIMEOUT_SECONDS", default=30.0)
INSPIRE_PAGE_SIZE = env.int("INSPIRE_PAGE_SIZE", default=250)
INSPIRE_MAX_RETRIES = env.int("INSPIRE_MAX_RETRIES", default=3)
INSPIRE_BACKOFF_BASE = env.float("INSPIRE_BACKOFF_BASE", default=1.0)
# One batch is one fetched page by default; a write batch does not have to match the
# page size, but there is no reason for it to differ unless observed otherwise.
INGEST_BATCH_SIZE = env.int("INGEST_BATCH_SIZE", default=INSPIRE_PAGE_SIZE)
# Bounds both the response size and the work the database does per search request.
SEARCH_RESULT_LIMIT = env.int("SEARCH_RESULT_LIMIT", default=20)
SEARCH_AUTHOR_SAMPLE_SIZE = env.int("SEARCH_AUTHOR_SAMPLE_SIZE", default=5)
# Bounded by pgvector's hnsw.ef_search default of 40; raising this alone has no effect.
HYBRID_CANDIDATE_DEPTH = env.int("HYBRID_CANDIDATE_DEPTH", default=40)
# Measured on this corpus: k=60 demoted both arm top picks below three mid-list
# agreements on the paraphrase query; k=5 kept both top picks in fused positions 1-2.
RRF_K = env.int("RRF_K", default=5)
# Bounds the abstract excerpt returned by the search API; a presentation constant, not
# a stored value.
ABSTRACT_SNIPPET_CHARS = env.int("ABSTRACT_SNIPPET_CHARS", default=280)
# The embedding layer is selected by import path so that swapping the local model for a
# hosted API touches one implementation module and no caller (AGENTS.md §3). The default
# is deliberately the REAL provider: defaulting to the fake would let an operator who
# never touched this setting fill a corpus with meaningless vectors in silence.
EMBEDDING_PROVIDER = env(
    "EMBEDDING_PROVIDER", default="apps.embedding.local.LocalEmbeddingProvider"
)
EMBEDDING_MODEL = env("EMBEDDING_MODEL", default="all-MiniLM-L6-v2")
# The schema contract. HS-010 builds its VectorField and ANN index from this number, and
# a system check fails when it disagrees with the configured provider's declared
# dimension. Once HS-010 runs makemigrations the migration becomes the real contract:
# changing this afterwards does not alter the column (AGENTS.md §6).
EMBEDDING_DIMENSION = env.int("EMBEDDING_DIMENSION", default=384)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.papers.apps.PapersConfig",
    "apps.ingestion.apps.IngestionConfig",
    "apps.search.apps.SearchConfig",
    "apps.embedding.apps.EmbeddingConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", default="hepsearch"),
        "USER": env("POSTGRES_USER", default="hepsearch"),
        "PASSWORD": env("POSTGRES_PASSWORD", default="hepsearch"),
        "HOST": env("POSTGRES_HOST", default="localhost"),
        "PORT": env("POSTGRES_PORT", default="5433"),
        "OPTIONS": {"connect_timeout": 2},
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
