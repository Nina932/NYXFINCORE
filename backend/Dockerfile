FROM python:3.12-slim

# Metadata
LABEL maintainer="FinAI Team"
LABEL description="FinAI Financial Intelligence Backend"
LABEL version="1.0.0"

# Security: run as non-root
RUN groupadd -r finai && useradd -r -g finai finai

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Working directory
WORKDIR /app

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create required directories
RUN mkdir -p uploads exports logs static && \
    chown -R finai:finai /app

# Switch to non-root user
USER finai

# Environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

# Make startup script executable
RUN chmod +x start_production.sh

# Expose port
EXPOSE 8000

# Start with automated migrations
CMD ["./start_production.sh"]
