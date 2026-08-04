"""Configuration and environment variable management.

Security features:
- API keys validated before use (format checks)
- Keys never logged or exposed in error messages
- Rate limiting support
- Streamlit Cloud secrets fallback
"""

import os
import re
import time
from functools import wraps

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Streamlit Cloud secrets fallback
try:
    import streamlit as st
    for key in ("GOOGLE_API_KEY", "COMPOSIO_API_KEY"):
        if key in st.secrets and not os.getenv(key):
            os.environ[key] = st.secrets[key]
except Exception:
    pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API Key Validation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _validate_api_key(key: str, name: str) -> bool:
    """Validate API key format (not empty, no whitespace, reasonable length)."""
    if not key or not key.strip():
        return False
    if len(key) < 10 or len(key) > 256:
        return False
    if re.search(r'\s', key):
        return False
    return True


def _mask_key(key: str) -> str:
    """Mask API key for safe logging: show first 4 and last 4 chars."""
    if not key or len(key) < 12:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


def get_api_keys() -> dict:
    """Load and validate API keys from environment variables."""
    keys = {
        "google": os.getenv("GOOGLE_API_KEY", "").strip(),
        "composio": os.getenv("COMPOSIO_API_KEY", "").strip(),
    }
    return keys


def get_validated_keys() -> tuple:
    """Return (keys_dict, list_of_missing_key_names)."""
    keys = get_api_keys()
    missing = []
    for name, value in keys.items():
        if name == "composio":
            continue  # optional
        if not _validate_api_key(value, name):
            missing.append(name.upper() + "_API_KEY")
    return keys, missing


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Rate Limiter
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class RateLimiter:
    """Simple in-memory rate limiter to prevent API abuse."""

    def __init__(self, max_calls: int = 10, window_seconds: int = 60):
        self.max_calls = max_calls
        self.window = window_seconds
        self.calls: list = []

    def check(self) -> bool:
        """Return True if the call is allowed."""
        now = time.time()
        self.calls = [t for t in self.calls if now - t < self.window]
        if len(self.calls) >= self.max_calls:
            return False
        self.calls.append(now)
        return True

    def remaining(self) -> int:
        now = time.time()
        self.calls = [t for t in self.calls if now - t < self.window]
        return max(0, self.max_calls - len(self.calls))

    def reset_in(self) -> float:
        if not self.calls:
            return 0
        return max(0, self.window - (time.time() - self.calls[0]))


# Global rate limiter: 10 searches per minute
search_limiter = RateLimiter(max_calls=10, window_seconds=60)


# Default search settings
DEFAULT_NUM_LINKS = 5
DEFAULT_SEARCH_LOCATION = "United States"
DEFAULT_SEARCH_LANG = "en"
DEFAULT_MODEL = "gemini-2.5-flash"

# Supported sources
AVAILABLE_SOURCES = {
    "web": {"label": "Live Web", "icon": "🌐", "description": "Grounded websites, papers, and PDFs"},
    "quora": {"label": "Quora", "icon": "🔶", "description": "Q&A discussions"},
    "pinterest": {"label": "Pinterest", "icon": "📌", "description": "Visual inspiration & templates"},
}

# Pipeline stages for Kanban board
PIPELINE_STAGES = ["Cold", "Warm", "Hot", "Contacted", "Converted"]
PIPELINE_COLORS = {
    "Cold": "#4a9eff",
    "Warm": "#ffab00",
    "Hot": "#ff5252",
    "Contacted": "#c6ff00",
    "Converted": "#00e676",
}
