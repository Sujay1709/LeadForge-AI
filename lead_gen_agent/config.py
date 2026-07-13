"""Configuration and environment variable management."""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not required on Streamlit Cloud

# Streamlit Cloud secrets fallback
try:
    import streamlit as st
    for key in ("GOOGLE_API_KEY", "FIRECRAWL_API_KEY", "COMPOSIO_API_KEY"):
        if key in st.secrets and not os.getenv(key):
            os.environ[key] = st.secrets[key]
except Exception:
    pass


def get_api_keys() -> dict:
    """Load API keys from environment variables."""
    return {
        "google": os.getenv("GOOGLE_API_KEY", ""),
        "firecrawl": os.getenv("FIRECRAWL_API_KEY", ""),
        "composio": os.getenv("COMPOSIO_API_KEY", ""),
    }


# Default search settings
DEFAULT_NUM_LINKS = 5
DEFAULT_SEARCH_LOCATION = "United States"
DEFAULT_SEARCH_LANG = "en"
DEFAULT_MODEL = "gemini-2.5-flash"
"""Configuration and environment variable management."""

import os
from dotenv import load_dotenv

load_dotenv()


def get_api_keys() -> dict:
    """Load API keys from environment variables."""
    return {
        "google": os.getenv("GOOGLE_API_KEY", ""),
        "firecrawl": os.getenv("FIRECRAWL_API_KEY", ""),
        "composio": os.getenv("COMPOSIO_API_KEY", ""),
    }


# Default search settings
DEFAULT_NUM_LINKS = 5
DEFAULT_SEARCH_LOCATION = "United States"
DEFAULT_SEARCH_LANG = "en"
DEFAULT_MODEL = "gemini-2.5-flash"
