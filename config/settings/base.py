"""Базовые настройки, общие для всех окружений (dev, test, prod)."""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
if (BASE_DIR / ".env").exists():
    environ.Env.read_env(BASE_DIR / ".env")

# Ключ по умолчанию только для dev/test; prod.py требует задать свой
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="django-insecure-dev-only-key-never-use-in-production-0123456789",
)
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# --- Приложения ---------------------------------------------------------------

DJANGO_APPS = [
    # daphne первым: тогда runserver запускает ASGI-сервер с поддержкой WebSocket
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "channels",
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "drf_spectacular",
]

LOCAL_APPS = [
    "apps.users",
    "apps.menu",
    "apps.tables",
    "apps.reservations",
    "apps.orders",
    "apps.payments",
    "apps.kitchen",
    "apps.notifications",
    "apps.analytics",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "config.middleware.HealthCheckMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

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
                "apps.orders.context_processors.cart",
            ],
        },
    },
]

# --- База данных --------------------------------------------------------------

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://restaurant:restaurant@localhost:5432/restaurant",
    ),
}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Пользователи -------------------------------------------------------------

AUTH_USER_MODEL = "users.User"

# Админка не по стандартному /admin/: меньше автоматических попыток подобрать пароль
ADMIN_URL = env("DJANGO_ADMIN_URL", default="admin/")

# Защита формы входа персонала от перебора паролей: попыток с одного IP
LOGIN_ATTEMPTS_LIMIT = env.int("LOGIN_ATTEMPTS_LIMIT", default=10)
LOGIN_LOCKOUT_SECONDS = 15 * 60

LOGIN_URL = "kitchen:login"
LOGIN_REDIRECT_URL = "kitchen:board"
LOGOUT_REDIRECT_URL = "kitchen:login"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Локализация --------------------------------------------------------------

LANGUAGE_CODE = "ru"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

# --- Статика и медиа ----------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- Django REST Framework ----------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    # Закрыто по умолчанию: публичные эндпоинты явно указывают AllowAny
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "auth": "10/minute",
        "reservations": "20/hour",
        "orders": "30/hour",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "UPDATE_LAST_LOGIN": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Restaurant System API",
    "DESCRIPTION": "Меню, бронирование столиков, заказы и кухня в реальном времени",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    # У нескольких моделей поле называется status: даём наборам значений понятные имена
    "ENUM_NAME_OVERRIDES": {
        "OrderStatusEnum": "apps.orders.models.Order.Status",
        "ReservationStatusEnum": "apps.reservations.models.Reservation.Status",
        "ReservationVisitStatusEnum": "apps.reservations.api.serializers.VISIT_STATUS_CHOICES",
    },
}

# --- Celery -------------------------------------------------------------------

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

# --- Channels (WebSocket) ----------------------------------------------------

# Слой каналов пересылает события между процессами: заказ изменился в одном
# воркере — сообщение получают все открытые экраны кухни. "memory" подходит
# только для одного процесса (локальный запуск без Redis).
if env("CHANNEL_LAYER", default="redis") == "memory":
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        },
    }

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TIME_LIMIT = 5 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 4 * 60
# Задача подтверждается после выполнения: если воркер упал посередине, её возьмёт другой.
# Поэтому периодические задачи сделаны идемпотентными.
CELERY_TASK_ACKS_LATE = True

CELERY_BEAT_SCHEDULE = {
    "cancel-unpaid-orders": {
        "task": "apps.orders.tasks.cancel_unpaid_orders",
        "schedule": 60.0,
    },
    "send-reservation-reminders": {
        "task": "apps.reservations.tasks.send_reservation_reminders",
        "schedule": 5 * 60.0,
    },
}

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Чайхана Bahor <noreply@bahor.local>")

# --- Интеграции ---------------------------------------------------------------

# Публичный адрес сайта: из него собираются ссылки в QR-кодах столов и возврат после оплаты
SITE_URL = env("SITE_URL", default="http://localhost:8000")

# Онлайн-оплата: "fake" — локальная имитация, "stripe" — Stripe Checkout
PAYMENT_PROVIDER = env("PAYMENT_PROVIDER", default="fake")
PAYMENTS_FAKE_SECRET = env("PAYMENTS_FAKE_SECRET", default="dev-only-fake-payments-secret")
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")

TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_CHAT_ID = env("TELEGRAM_CHAT_ID", default="")

# --- Логирование --------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "apps": {
            "handlers": ["console"],
            "level": env("LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
    },
}
