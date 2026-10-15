FROM python:3.12-slim

WORKDIR /app

# Install system dependencies if necessary
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Default entrypoint command
CMD ["sh", "-c", "python -m app.services.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
