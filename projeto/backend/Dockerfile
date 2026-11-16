FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

# Mesmos valores de server_settings.py (DEFAULT_PORT) e do docker-compose.yml.
ARG APP_PORT=5000
ARG APP_UID=1000
ARG APP_GID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    GUNICORN_PORT=${APP_PORT}

WORKDIR /app

RUN groupadd -g ${APP_GID} appgroup && \
    useradd -l -u ${APP_UID} -g appgroup -s /usr/sbin/nologin -M appuser

COPY requirements.txt .
RUN pip install -r requirements.txt

# Código pertence ao root: o usuário da aplicação só lê.
COPY . .

USER appuser

EXPOSE ${APP_PORT}

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "healthcheck.py"]

CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
