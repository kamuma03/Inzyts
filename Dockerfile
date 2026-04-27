# Dockerfile for Inzyts Backend
# Usage: docker build --target backend -t inzyts-backend .

# ==============================================================================
# Base stage - shared Python dependencies
# ==============================================================================
FROM python:3.11.9-slim AS base

WORKDIR /app

# Install system dependencies
# WeasyPrint requires libpango, libgdk-pixbuf, and libffi for PDF generation.
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libpq-dev \
    libmagic1 \
    curl \
    gosu \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user for the application
RUN useradd --no-create-home --shell /bin/false inzyts

# ==============================================================================
# Backend target - FastAPI server
# ==============================================================================
FROM base AS backend

# Copy the rest of the application
COPY . .

# Ensure data directories exist and are owned by the app user with restricted permissions
RUN mkdir -p data/uploads logs output .local .cache \
    && chown -R inzyts:inzyts data logs output .local .cache \
    && chmod 750 data/uploads

# Entrypoint fixes bind-mount ownership then drops to inzyts via gosu
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]

# Expose port (Internal to Docker network, mapped in compose)
EXPOSE 8000

# Run the application
CMD ["uvicorn", "src.server.main:app", "--host", "0.0.0.0", "--port", "8000"]
