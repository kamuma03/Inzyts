# Multi-stage Dockerfile for Inzyts Backend and Jupyter Services
# Usage:
#   Backend: docker build --target backend -t inzyts-backend .
#   Jupyter: docker build --target jupyter -t inzyts-jupyter .

# ==============================================================================
# Base stage - shared Python dependencies
# ==============================================================================
FROM python:3.11.9-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libpq-dev \
    libmagic1 \
    curl \
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

USER inzyts

# Expose port (Internal to Docker network, mapped in compose)
EXPOSE 8000

# Run the application
CMD ["uvicorn", "src.server.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ==============================================================================
# Jupyter target - Jupyter notebook server
# ==============================================================================
FROM jupyter/scipy-notebook:python-3.11 AS jupyter

# Install as jovyan (NB_UID) user to avoid running pip as root
USER ${NB_UID}

# Copy requirements and install
COPY --chown=${NB_UID}:${NB_GID} requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
