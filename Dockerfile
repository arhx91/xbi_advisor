# =================================================================================================
# Dockerfile (Main Application)
# =================================================================================================
# What it does:
#   Packages the main XBI Advisor application (FastAPI) into a production-ready Docker image.
#
# Why it does it:
#   To create a consistent, reliable, and performant environment for running the heavy analysis
#   logic on Google Cloud Run. It handles complex dependencies (Cairo, PyTorch) and ensures
#   fast startup times.
#
# How it does it:
#   - **Split Approach**: Installs dependencies first (using `uv sync`) so that changing source
#     code doesn't invalidate the dependency cache.
#   - **Lean CPU Build**: Relies on `pyproject.toml` configuration to install only the CPU versions
#     of PyTorch, saving ~1.5GB of space (no NVIDIA drivers).
#   - **Turbo Model Download**: Uses `hf_transfer` and `huggingface-cli` to download the
#     `sentence-transformers` model at max speed during the build phase.
#   - **Multi-Stage**: Uses a `builder` stage for tools and compilation, and a clean `runtime` stage.
#   - **Security**: Runs as a non-root `appuser`.
#
# How it ties into the bigger picture:
#   - **Inputs**: `pyproject.toml`, `uv.lock`, `xbi_advisor/` source code.
#   - **Outputs**: A container image pushed to Google Container Registry (GCR).
#   - **Where used**: Deployed by `deploy.sh` as the **Private Cloud Run Service**. It receives
#     authenticated requests from the Relay Function (or other internal services) to generate reports.
# =================================================================================================

# ============================
# Stage 1: Builder
# ============================
FROM python:3.13-slim AS builder

# Python Optimizations:
# - PYTHONUNBUFFERED=1: Force stdout/stderr to be unbuffered. Logs appear instantly in Cloud Run.
# - UV_COMPILE_BYTECODE=1: Compile .py files to .pyc during install. Speeds up startup time.
# - HF_HUB_ENABLE_HF_TRANSFER=1: Enable Rust-based high-speed download for models.
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    HF_HUB_ENABLE_HF_TRANSFER=1

WORKDIR /app

# Install system deps (including Cairo dev libraries + fonts for Unicode support)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    pkg-config \
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf-2.0-dev \
    libffi-dev \
    shared-mime-info \
    fonts-dejavu-core \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Install uv from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Setup venv
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
RUN uv venv

# 1. Install project dependencies (Split Approach for Caching)
# We use `uv sync` to install dependencies from the lockfile without installing the project itself.
# This keeps the dependency layer cached effectively.
# Note: PyTorch CPU version is enforced via pyproject.toml and uv.lock.
ARG INSTALL_EXTRAS=main
RUN uv sync --frozen --no-install-project --extra ${INSTALL_EXTRAS}

# 2. Install huggingface tools
# These are build-time dependencies needed to download the model efficiently.
RUN uv pip install --python "$UV_PROJECT_ENVIRONMENT" "huggingface_hub[cli,hf_transfer]"

# 3. Pre-cache model
# We download the model into a temporary directory using the high-speed CLI.
ENV HF_HOME=/tmp/hf_cache
RUN /app/.venv/bin/huggingface-cli download sentence-transformers/all-MiniLM-L6-v2 --cache-dir $HF_HOME

# 4. Copy source and install project (Uncached layer, but fast)
COPY xbi_advisor ./xbi_advisor
COPY README.md .
# Install the package itself without dependencies (deps are already there)
RUN uv pip install --python "$UV_PROJECT_ENVIRONMENT" --no-deps .


# ============================
# Stage 2: Runtime
# ============================
FROM python:3.13-slim

# Runtime Optimizations
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    HF_HUB_ENABLE_HF_TRANSFER=1 \
    PATH="/app/.venv/bin:$PATH" \
    HF_HOME=/app/.cache/huggingface \
    PYTHONPATH=/app

WORKDIR /app

# Create non-root user (Security Best Practice)
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --gid 1001 --no-create-home appuser

# Install minimal runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libcairo2 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-dejavu-core \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Refresh font cache
RUN fc-cache -fv

# Copy venv from builder
COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv

# Copy pre-cached model
COPY --from=builder --chown=appuser:appgroup /tmp/hf_cache /app/.cache/huggingface

# Copy source code
COPY --chown=appuser:appgroup xbi_advisor ./xbi_advisor
COPY --chown=appuser:appgroup README.md .

# Set GCS bucket env
ENV LAST_ID_BUCKET="xbi-advisor-bucket"

# Switch to non-root user
USER appuser

# Expose FastAPI port
EXPOSE 8080

# Start the FastAPI app
ENTRYPOINT ["uvicorn", "xbi_advisor.xbi_advisor_app:app", "--host", "0.0.0.0", "--port", "8080"]
