"""
peer_learning/settings.py
Hybrid Database Architecture: MySQL (relational) + MongoDB (documents) + Redis (cache/presence)
Production-ready: Whitenoise static files, structured logging, Redis password support.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── PyMySQL compatibility shim ─────────────────────────────────────────────────
# On Windows (requirements.windows.txt), PyMySQL replaces mysqlclient.
# This call makes PyMySQL masquerade as MySQLdb so Django's mysql backend
# works with no other changes. In Docker/Linux with mysqlclient installed,
# this block is a harmless no-op.
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass  # mysqlclient is installed — nothing to do

BASE_DIR = Path(__file__).resolve().parent.parent

# ──────────────────────────────────────────────────────
# CORE
# ──────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-in-production-!!!")
DEBUG = os.environ.get("DEBUG", "True") == "True"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0").split(",")

# Trust X-Forwarded-Proto from Nginx (enables request.is_secure())
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Project apps
    "apps.accounts",
    "apps.channels",
    "apps.discussions",
    "apps.core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Whitenoise: serve static files efficiently in production
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Custom: updates Redis presence on every authenticated request
    "apps.core.middleware.UserPresenceMiddleware",
]

ROOT_URLCONF = "peer_learning.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.sidebar_context",
            ],
        },
    },
]

WSGI_APPLICATION = "peer_learning.wsgi.application"

# ──────────────────────────────────────────────────────
# DATABASE — MySQL (primary relational store)
# ──────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("MYSQL_DB", "peer_learning"),
        "USER": os.environ.get("MYSQL_USER", "root"),
        "PASSWORD": os.environ.get("MYSQL_PASSWORD", ""),
        "HOST": os.environ.get("MYSQL_HOST", "localhost"),
        "PORT": os.environ.get("MYSQL_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        # Keep connections alive across Gunicorn requests (reduces overhead)
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }
}

# ──────────────────────────────────────────────────────
# MONGODB — Document store for threads & messages
# ──────────────────────────────────────────────────────
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.environ.get("MONGO_DB", "peer_learning")

# ──────────────────────────────────────────────────────
# REDIS — Cache + Session + Presence tracking
# ──────────────────────────────────────────────────────
REDIS_HOST     = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT     = int(os.environ.get("REDIS_PORT", 6379))
REDIS_DB_INDEX = int(os.environ.get("REDIS_DB", 0))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", None)

# Build Redis URL — include password if set
if REDIS_PASSWORD:
    REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_INDEX}"
else:
    REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_INDEX}"

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "RETRY_ON_TIMEOUT": True,
            "MAX_CONNECTIONS": 20,
            "PASSWORD": REDIS_PASSWORD,
        },
        "KEY_PREFIX": "pl",
    }
}

SESSION_ENGINE    = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
SESSION_COOKIE_AGE = 86400   # 24 hours
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# ──────────────────────────────────────────────────────
# AUTH
# ──────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ──────────────────────────────────────────────────────
# STATIC & MEDIA
# ──────────────────────────────────────────────────────
STATIC_URL  = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Whitenoise: serve compressed, cache-busted static files without Nginx
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL  = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ──────────────────────────────────────────────────────
# INTERNATIONALISATION
# ──────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE     = "UTC"
USE_I18N      = True
USE_TZ        = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ──────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} [{levelname}] {name}: {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "[{levelname}] {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "utils": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}

# ──────────────────────────────────────────────────────
# PRESENCE THRESHOLDS (seconds)
# ──────────────────────────────────────────────────────
PRESENCE_ACTIVE_THRESHOLD = 300    # 5 min  → green
PRESENCE_AWAY_THRESHOLD   = 1800   # 30 min → yellow, then grey
