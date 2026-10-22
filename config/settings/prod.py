"""Продакшен-настройки. Все секреты обязательны и берутся из окружения."""

from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = False

# Имитация оплаты в продакшене позволила бы получать заказы бесплатно
PAYMENT_PROVIDER = env("PAYMENT_PROVIDER", default="stripe")
if PAYMENT_PROVIDER == "fake":
    raise ImproperlyConfigured("PAYMENT_PROVIDER=fake запрещён в продакшене")

# Без значений по умолчанию: если переменная не задана, приложение не запустится
SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# HTTPS за reverse-proxy (Caddy, Railway, Render)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 30)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# Preload — долгосрочное обязательство для домена, включается осознанно через env
SECURE_HSTS_PRELOAD = env.bool("DJANGO_SECURE_HSTS_PRELOAD", default=False)
SECURE_CONTENT_TYPE_NOSNIFF = True

if not SECURE_HSTS_PRELOAD:
    SILENCED_SYSTEM_CHECKS = ["security.W021"]

# Общий кэш для всех процессов: счётчики лимитов запросов (throttling) и попыток
# входа должны быть одни на всё приложение, а не свои в памяти каждого процесса
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("CACHE_URL", default=REDIS_URL.rsplit("/", 1)[0] + "/1"),
    }
}

# Приложение работает за одним reverse-proxy (Caddy). DRF берёт IP клиента
# из X-Forwarded-For с учётом этого числа. Без настройки IP можно подделать
# заголовком и обойти лимит на попытки входа.
REST_FRAMEWORK = {**REST_FRAMEWORK, "NUM_PROXIES": env.int("NUM_PROXIES", default=1)}

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

EMAIL_CONFIG = env.email_url("EMAIL_URL", default="consolemail://")
vars().update(EMAIL_CONFIG)

LOGGING["root"]["level"] = env("LOG_LEVEL", default="INFO")
