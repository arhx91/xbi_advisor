"""
Configuration and path utilities for XBI Advisor.

Purpose:
    - Centralize all file path handling for local development and Cloud Run.
    - Ensure consistent use of /tmp for scratch space and GCS mount for persistent storage.
    - Allow overrides via .env or environment variables.

Usage:
    from xbi_advisor.modules.config import get_tmp_dir, get_final_output_dir
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env for local development (has no effect in Cloud Run if env vars are set)
load_dotenv()

# Default constants
DEFAULT_TMP_DIR = Path("/tmp/xbi_advisor")  # Scratch space in Cloud Run
DEFAULT_GCS_BUCKET_PATH = Path("/mnt/gcs")  # gcsfuse mount point in Cloud Run


def get_tmp_dir() -> Path:
    """
    Returns the temporary working directory for intermediate files.
    Creates it if it does not exist.
    Respects TMP_DIR env var if set.
    """
    tmp = Path(os.getenv("TMP_DIR", DEFAULT_TMP_DIR))
    tmp.mkdir(parents=True, exist_ok=True)
    return tmp


def get_final_output_dir() -> Path:
    """
    Returns the persistent output directory inside the GCS mount.
    Creates it if it does not exist.
    Respects GCS_BUCKET_PATH env var if set.
    """
    gcs_path = Path(os.getenv("GCS_BUCKET_PATH", DEFAULT_GCS_BUCKET_PATH)) / "reports"
    gcs_path.mkdir(parents=True, exist_ok=True)
    return gcs_path


def get_assets_dir() -> Path:
    """
    Returns the path to the static assets directory bundled with the app.
    """
    return Path("xbi_advisor/assets")
