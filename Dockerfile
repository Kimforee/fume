# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for static files and templates
RUN mkdir -p static templates

# Expose port (Cloud Run will set PORT env var)
ENV PORT=8080
EXPOSE 8080

# Run the application
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}

