"""Настройки для pytest: быстро и без внешних сервисов."""

from .base import *

DEBUG = False

# Быстрый хешер: настоящий PBKDF2 сильно замедляет тесты
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Статику в тестах не собираем (collectstatic), WhiteNoise ищет файлы на лету
WHITENOISE_AUTOREFRESH = True

# Celery-задачи выполняются синхронно, Redis не нужен
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Лимиты запросов отключены, иначе тесты регистрации упираются в throttle
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {"auth": None, "reservations": None, "orders": None},
}

PAYMENT_PROVIDER = "fake"
PAYMENTS_FAKE_SECRET = "test-fake-secret"
STRIPE_SECRET_KEY = "sk_test_dummy"
STRIPE_WEBHOOK_SECRET = "whsec_test_dummy"
