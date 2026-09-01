# Multi-stage build for RecoverAI FastAPI Backend
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system dependencies needed for building packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirement specifications
COPY backend/requirements.txt .

# Create virtualenv and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Final minimal runner stage
FROM python:3.11-slim AS runner

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Copy backend application source code
COPY backend/app /app/backend/app

# Non-root user safety
RUN useradd -m -u 1000 recoverai && \
    chown -R recoverai:recoverai /app
USER recoverai

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
