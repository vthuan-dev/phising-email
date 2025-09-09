# agent/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY agent/ .

# Copy generate_sample_logs.py from scripts directory
COPY scripts/generate_sample_logs.py /app/

# Create log directory
RUN mkdir -p /var/log

# Create non-root user
RUN useradd -m -u 1001 agent
RUN chown -R agent:agent /app /var/log
USER agent

CMD ["python", "email_agent.py"]
