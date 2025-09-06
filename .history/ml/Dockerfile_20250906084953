# ml/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create artifacts directory
RUN mkdir -p /app/artifacts

# Create non-root user
RUN useradd -m -u 1001 ml_user
RUN chown -R ml_user:ml_user /app
USER ml_user

CMD ["python", "train.py"]
