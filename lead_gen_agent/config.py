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
