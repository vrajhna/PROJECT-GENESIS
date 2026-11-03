# Genesis API on Railway (also works on any VPS/panel with Docker).
FROM python:3.12-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

# Railway injects PORT. GENESIS_DATA_DIR must be a mounted Volume (/data).
ENV GENESIS_DATA_DIR=/data
EXPOSE 8000
CMD ["sh", "-c", "python3 -m uvicorn app.api.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
