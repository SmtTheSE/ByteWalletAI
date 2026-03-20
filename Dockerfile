FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if any (none needed for now)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create models and data dirs
RUN mkdir -p models data

EXPOSE 8000

# Start the API server with Gunicorn for production stability
CMD ["gunicorn", "app.main:app", "--workers", "2", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "120"]
