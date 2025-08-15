# =============================================================================
# StashAI Server - Docker Configuration
# =============================================================================

FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and data directory
RUN useradd -m -u 1000 stash && \
    mkdir -p /app /app/data && \
    chown -R stash:stash /app

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY --chown=stash:stash requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=stash:stash . .

# Switch to non-root user
USER stash

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9998/health || exit 1

# Expose port
EXPOSE 9998

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9998"]