# Maintenance service image.
# Pinned to an exact Python patch version, so a rebuild next month gives the same base.
FROM python:3.12.16-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Dependencies first: editing source code does not reinstall packages (layer cache).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Only the files the service needs to run (no COPY . ., no tests, no .env).
COPY app.py db.py logic.py store.py ./
COPY migrations ./migrations

# Run as an unprivileged user, not root.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# Wait for the database and apply pending migrations, then start the web server.
CMD ["sh", "-c", "python db.py && exec gunicorn --bind 0.0.0.0:${PORT} --workers 2 app:app"]
