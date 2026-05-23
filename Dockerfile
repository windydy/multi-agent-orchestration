FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Final image ──
FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /install /usr/local

# Copy application code
COPY src/ src/
COPY config/ config/
COPY web/dist/ web/dist/

# Create directories for runtime data
RUN mkdir -p checkpoints memory logs

# Non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
