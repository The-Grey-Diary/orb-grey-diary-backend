FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY app/ ./app/

# Cloud Run sets PORT=8080 automatically
ENV PORT=8080
EXPOSE 8080

# exec form: proper SIGTERM handling on Cloud Run
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --log-level info
