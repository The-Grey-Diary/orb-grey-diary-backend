FROM python:3.12-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY app/ ./app/

# Cloud Run injects PORT env var (always 8080 unless changed)
ENV PORT=8080
EXPOSE 8080

# exec form handles SIGTERM correctly on Cloud Run
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --log-level info
