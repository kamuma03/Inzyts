# Dockerfile for Inzyts Backend
# Usage: docker build --target backend -t inzyts-backend .

# ==============================================================================
# Builder stage - compile dependencies into an isolated virtualenv
# ==============================================================================
# The build toolchain (gcc, python3-dev, *-dev headers) lives ONLY here and is
# discarded; the runtime image below copies just the populated venv. This keeps
# the compiler/headers out of the shipped image (smaller, smaller attack surface).
FROM python:3.11.9-slim AS builder

WORKDIR /app

# Build-time system deps: compilers + dev headers needed to build wheels
# (psycopg → libpq-dev, cffi/WeasyPrint → libffi-dev).
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libpq-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Isolated venv so the whole dependency tree can be copied in one layer.
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ==============================================================================
# Base stage - slim runtime with only the shared libraries (no compilers)
# ==============================================================================
FROM python:3.11.9-slim AS base

WORKDIR /app

# Runtime-only system libs (the -dev/compiler packages are intentionally absent).
# WeasyPrint needs libpango/libgdk-pixbuf/libcairo for PDF generation; psycopg
# needs libpq5; cffi needs libffi8. iptables is used by docker-entrypoint.sh
# when INZYTS_NETWORK_ISOLATION=strict (harmless when off).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libmagic1 \
    libffi8 \
    curl \
    gosu \
    iptables \
    dnsutils \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Bring in the pre-built dependency venv from the builder.
ENV VIRTUAL_ENV=/opt/venv
COPY --from=builder /opt/venv /opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Create a non-root user for the application
RUN useradd --no-create-home --shell /bin/false inzyts

# ==============================================================================
# Backend target - FastAPI server
# ==============================================================================
FROM base AS backend

# Copy the rest of the application (see .dockerignore for what's excluded —
# notably .env, .git, tests, and frontend never enter the image).
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
