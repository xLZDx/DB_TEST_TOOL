# DB Testing Tool – Docker image
# Build:  docker build -t db-testing-tool .
# Run:    docker run -p 8550:8550 -v db-testing-data:/data db-testing-tool

FROM python:3.11-slim

# System deps for oracledb / psycopg2 / pyodbc
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libpq-dev \
        unixodbc-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Install Python dependencies first (layer caching)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY run.py ./

# Data volume – credentials key file, SQLite DB, local KB all live here
VOLUME /data
ENV DB_TESTING_TOOL_DATA_DIR=/data

# Expose the app port
EXPOSE 8550

# Drop to non-root
RUN chown -R appuser:appuser /app
USER appuser

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8550", "--log-level", "info"]
