# Два образа из одного файла:
#   docker build --target dev  .  — для разработки: dev-зависимости, код монтируется томом
#   docker build --target prod .  — для продакшена: только нужные пакеты, статика собрана

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Приложение не работает от root
RUN adduser --disabled-password --gecos "" app \
    && mkdir -p /app/media /app/staticfiles \
    && chown -R app:app /app

# --- Разработка ---------------------------------------------------------------
FROM base AS dev

# Зависимости отдельным слоем: при изменении кода они не переустанавливаются
COPY requirements/ requirements/
RUN pip install -r requirements/dev.txt

COPY --chown=app:app . .
USER app
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# --- Продакшен ----------------------------------------------------------------
FROM base AS prod

COPY requirements/ requirements/
RUN pip install -r requirements/base.txt

COPY --chown=app:app . .

# Статика собирается при сборке образа. Настоящие секреты здесь не нужны:
# collectstatic не ходит в БД, а значения ниже живут только на этом шаге
RUN DJANGO_SETTINGS_MODULE=config.settings.prod \
    DJANGO_SECRET_KEY=collectstatic-only \
    DJANGO_ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput

USER app
EXPOSE 8000

# ASGI-сервер: обычный WSGI (gunicorn) не умеет WebSocket.
# --proxy-headers: реальный IP клиента берётся из X-Forwarded-For от Caddy
CMD ["daphne", "--bind", "0.0.0.0", "--port", "8000", "--proxy-headers", "config.asgi:application"]
