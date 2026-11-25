# Listening test API. The research package (study/) is baked in, so an image
# tag pins exactly which scenarios are being evaluated.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_ENV=production \
    DATA_DIR=/data \
    STUDY_DIR=/app/study

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt \
 && useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app \
 && mkdir /data && chown 10001:10001 /data

# The package first: it is 2.4 GB and changes far less often than the code.
COPY study ./study
COPY app ./app

USER 10001
EXPOSE 8000
VOLUME /data

# One worker on purpose: SQLite, the in-memory rate limiter and the lock that
# serializes the scenario queue all assume a single process. Threads cover the
# concurrency a listening test needs.
CMD ["gunicorn", "app.wsgi:app", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "32", \
     "--worker-tmp-dir", "/tmp", "--no-control-socket", "--timeout", "30", "--graceful-timeout", "10", \
     "--limit-request-line", "2048", "--limit-request-fields", "50", "--error-logfile", "-"]
