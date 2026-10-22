FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Зависимости ставим отдельным слоем: при изменении кода они не переустанавливаются
ARG REQUIREMENTS=dev
COPY requirements/ requirements/
RUN pip install -r requirements/${REQUIREMENTS}.txt

COPY . .

# Приложение не работает от root
RUN adduser --disabled-password --gecos "" app && chown -R app:app /app
USER app

EXPOSE 8000

# ASGI-сервер: обычный WSGI (gunicorn) не умеет WebSocket
CMD ["daphne", "--bind", "0.0.0.0", "--port", "8000", "config.asgi:application"]
