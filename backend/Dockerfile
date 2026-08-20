# ── Build stage ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System dependencies: FFmpeg + build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Runtime stage ─────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# FFmpeg in runtime image
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Create temp audio directory
RUN mkdir -p /tmp/grievance_audio

# Non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app /tmp/grievance_audio
USER appuser

# Expose API port
EXPOSE 8000

# Default: run API server
# Override CMD in docker-compose for the Celery worker
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
