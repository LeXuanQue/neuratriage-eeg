FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libfreetype6 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data/uploads data/reports out

EXPOSE 8501

# Liveness probe (used by docker-compose / orchestrators).
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8501/api/health',timeout=3).getcode()==200 else 1)"

WORKDIR /app/backend
# IMPORTANT: run a SINGLE worker. ModelManager, SessionManager and the in-memory
# rate limiter are per-process singletons, and live WebSocket detector state lives
# in RAM — multiple workers would not share them and SQLite would contend on
# writes. Scale vertically (bigger instance), not by worker/replica count.
CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8501", "--workers", "1", "--log-level", "info"]
