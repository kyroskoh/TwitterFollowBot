# Multi-stage build for X Follow Bot v2.0
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create and set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY pyproject.toml ./
COPY src/ ./src/

# Install Python dependencies
RUN pip install -e .

# Production stage
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/app/.venv/bin:$PATH"

# Create non-root user
RUN groupadd -r xbot && useradd -r -g xbot xbot

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy application from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/x-follow-bot /usr/local/bin/x-follow-bot
COPY --from=builder /app/src /app/src

# Create directories for data and logs
RUN mkdir -p /app/data /app/logs /app/config && \
    chown -R xbot:xbot /app

# Copy configuration template
COPY config.yaml.example /app/config/config.yaml.example

# Switch to non-root user
USER xbot

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD x-follow-bot bot status || exit 1

# Expose port for web interface (if enabled)
EXPOSE 8000

# Default command
CMD ["x-follow-bot", "--help"]