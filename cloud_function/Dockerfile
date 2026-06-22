# =================================================================================================
# Dockerfile (Relay Function)
# =================================================================================================
# What it does:
#   Packages the XBI Advisor Relay Function into a lightweight Docker image.
#
# Why it does it:
#   To serve as a public-facing, secure entry point for the application. It receives webhooks
#   (e.g., from Typeform), authenticates itself, and forwards the payload to the private Main App.
#
# How it does it:
#   - **Ultra-Lean**: Installs *only* the dependencies (`google-auth`, `fastapi`) and copies
#     *only* the `cloud_function` code. It explicitly excludes the main `xbi_advisor` package
#     to keep the image tiny and secure.
#   - **Split Approach**: Installs dependencies first (cached) using `uv sync`.
#   - **Multi-Stage**: Strips out build tools (`uv`, compilers).
#   - **Security**: Runs as a non-root `appuser`.
#
# How it ties into the bigger picture:
#   - **Inputs**: `cloud_function/` directory, `pyproject.toml` (for deps).
#   - **Outputs**: A container image pushed to GCR.
#   - **Where used**: Deployed by `deploy.sh` as the **Public Cloud Run Service**. It acts as the
#     gateway/proxy to the private backend.
# =================================================================================================

# ============================
# Stage 1: Builder
# ============================
FROM python:3.13-slim AS builder

# Python Optimizations:
# - PYTHONUNBUFFERED=1: Force stdout/stderr to be unbuffered. Logs appear instantly in Cloud Run.
# - UV_COMPILE_BYTECODE=1: Compile .py files to .pyc during install. Speeds up startup time.
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# Install uv from the official image (cleaner than curl)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Setup venv
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
RUN uv venv

# Install dependencies (Split Approach)
# We use `uv sync` with `--no-install-project` to install ONLY the dependencies from uv.lock.
# This allows Docker to cache this layer effectively (it won't re-run if code changes, only if deps change).
ARG INSTALL_EXTRAS=cloud_function
RUN uv sync --frozen --no-install-project --extra ${INSTALL_EXTRAS}

# Copy source code
COPY cloud_function ./cloud_function

# ============================
# Stage 2: Runtime
# ============================
FROM python:3.13-slim

# Runtime Optimizations
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Create a non-root user (Security Best Practice)
# Running as root allows an attacker full control if they escape the container.
# A limited user restricts the potential blast radius.
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --gid 1001 --no-create-home appuser

# Install minimal runtime deps if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv

# Copy application code (ONLY cloud_function directory)
COPY --chown=appuser:appgroup cloud_function ./cloud_function

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8080

# Start the application
ENTRYPOINT ["uvicorn", "cloud_function.main:app", "--host", "0.0.0.0", "--port", "8080"]
