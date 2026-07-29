# Neu AI self-hosted bot worker.
# Phase 1: mock mode (no browser) — proves the self-hosted seam end to end.
# Phase 2 will add Playwright + Chromium here for the real Google Meet bot.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY worker.py .

EXPOSE 8080
CMD ["uvicorn", "worker:app", "--host", "0.0.0.0", "--port", "8080"]
