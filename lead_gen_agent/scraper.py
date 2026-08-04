"""Multi-source web scraper for lead discovery and extraction.

Uses DuckDuckGo for free URL search (no API key needed),
BeautifulSoup for page scraping, and Google Gemini for
intelligent lead extraction from page content.

Supports Quora and Pinterest as lead sources.
"""

import re
import json
import hashlib
import time
import requests
from typing import List, Optional
from bs4 import BeautifulSoup
from config import DEFAULT_SEARCH_LOCATION, DEFAULT_SEARCH_LANG

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

try:
    from google import genai
except ImportError:
    genai = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# URL Search (DuckDuckGo — Free, No API Key)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def search_for_urls(
    company_description: str,
    api_key: str = "",
    num_links: int = 5,
    sources: Optional[List[str]] = None,
) -> List[dict]:
    """Search for relevant URLs across multiple platforms using DuckDuckGo.

    Args:
        company_description: Concise description of what leads to search for.
        api_key: Unused (kept for backward compatibility). DDG needs no key.
        num_links: Max number of URLs to return per source.
        sources: List of sources to search. Defaults to ["quora"].

    Returns:
        List of dicts with 'url' and 'source' keys.
    """
    if sources is None:
        sources = ["quora"]

    if DDGS is None:
        raise ImportError(
            "duckduckgo-search package is required. "
            "Install it with: pip install duckduckgo-search"
        )

    all_results = []

    for source in sources:
        if source == "quora":
            urls = _search_quora(company_description, num_links)
            all_results.extend([{"url": u, "source": "quora"} for u in urls])
        elif source == "pinterest":
            urls = _search_pinterest(company_description, num_links)
            all_results.extend([{"url": u, "source": "pinterest"} for u in urls])

    return all_results


def _search_quora(company_description: str, num_links: int = 5) -> List[str]:
    """Search DuckDuckGo for Quora URLs matching the lead description."""
    query = f"site:quora.com {company_description}"
    return _ddg_search(query, num_links, domain_filter="quora.com")


def _search_pinterest(company_description: str, num_links: int = 5) -> List[str]:
    """Search DuckDuckGo for Pinterest URLs matching the lead description."""
    query = f"site:pinterest.com {company_description} ideas templates"
    return _ddg_search(query, num_links, domain_filter="pinterest")


def _ddg_search(query: str, max_results: int, domain_filter: str) -> List[str]:
    """Run a DuckDuckGo text search and filter URLs by domain."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results * 2))

        urls = []
        for r in results:
            url = r.get("href", "") or r.get("link", "")
            if url and domain_filter in url:
                urls.append(url)
                if len(urls) >= max_results:
                    break
        return urls
    except Exception as e:
        print(f"DuckDuckGo search failed: {e}")
        return []


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Page Scraping (BeautifulSoup — Free)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _scrape_page_text(url: str, max_chars: int = 8000) -> str:
    """Scrape a URL and return cleaned text content."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15, allow_redirects=True)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove scripts, styles, nav, footer
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)

        # Collapse whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean = "\n".join(lines)

        return clean[:max_chars]
    except Exception as e:
        print(f"Scrape failed for {url}: {e}")
        return ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Lead Extraction (Gemini — Free Tier)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_QUORA_EXTRACT_PROMPT = """Analyze this Quora page content and extract user information.

For EACH user who posted a question or answer, extract:
- username: their display name or username
- bio: any bio/credential text shown (empty string if none)
- post_type: "question" or "answer"
- timestamp: when they posted (empty string if not visible)
- upvotes: number of upvotes (0 if not visible)
- profile_url: their Quora profile URL if visible (empty string if not)

Return a JSON object with this exact structure:
{
  "user_interactions": [
    {
      "username": "...",
      "bio": "...",
      "post_type": "...",
      "timestamp": "...",
      "upvotes": 0,
      "profile_url": "..."
    }
  ]
}

If no users can be extracted, return: {"user_interactions": []}

PAGE CONTENT:
"""

_PINTEREST_EXTRACT_PROMPT = """Analyze this Pinterest page content and extract user/creator information.

For EACH user or creator found, extract:
- username: their display name or username
- bio: any description or bio text (empty string if none)
- post_type: "pin", "board", or "profile"
- timestamp: any date shown (empty string if not visible)
- upvotes: saves/likes count (0 if not visible)
- profile_url: their Pinterest profile URL if visible (empty string if not)

Return a JSON object with this exact structure:
{
  "user_interactions": [
    {
      "username": "...",
      "bio": "...",
      "post_type": "...",
      "timestamp": "...",
      "upvotes": 0,
      "profile_url": "..."
    }
  ]
}

If no users can be extracted, return: {"user_interactions": []}

PAGE CONTENT:
"""


def extract_user_info_from_urls(
    url_items: list,
    api_key: str = "",
    google_api_key: str = "",
) -> List[dict]:
    """Extract user information from URLs using BeautifulSoup + Gemini.

    Args:
        url_items: List of dicts with 'url' and 'source' keys, or list of strings.
        api_key: Unused (backward compatibility). No paid API needed.
        google_api_key: Google/Gemini API key for LLM extraction.

    Returns:
        List of dicts with 'website_url', 'source', and 'user_info' keys.
    """
    results = []

    for item in url_items:
        if isinstance(item, str):
            url = item
            source = "quora"
        else:
            url = item["url"]
            source = item.get("source", "quora")

        # Step 1: Scrape the page
        page_text = _scrape_page_text(url)
        if not page_text or len(page_text) < 50:
            # Try regex fallback for Quora
            if source == "quora":
                fallback = _regex_extract_quora(url)
                if fallback:
                    results.append({"website_url": url, "source": source, "user_info": fallback})
            continue

        # Step 2: Extract with Gemini (or regex fallback)
        try:
            user_info = _extract_with_gemini(page_text, source, google_api_key)
            if user_info:
                results.append({"website_url": url, "source": source, "user_info": user_info})
            elif source == "quora":
                fallback = _regex_extract_from_text(page_text, url)
                if fallback:
                    results.append({"website_url": url, "source": source, "user_info": fallback})
        except Exception as e:
            print(f"Extraction failed for {url}: {e}")
            if source == "quora":
                fallback = _regex_extract_from_text(page_text, url)
                if fallback:
                    results.append({"website_url": url, "source": source, "user_info": fallback})

        # Small delay between requests
        time.sleep(0.5)

    return results


def _extract_with_gemini(page_text: str, source: str, google_api_key: str) -> list:
    """Use Gemini to extract structured lead data from page text."""
    if not genai or not google_api_key:
        return []

    prompt = _QUORA_EXTRACT_PROMPT if source == "quora" else _PINTEREST_EXTRACT_PROMPT
    full_prompt = prompt + page_text

    try:
        client = genai.Client(api_key=google_api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=full_prompt,
        )

        text = response.text.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        data = json.loads(text)
        return data.get("user_interactions", [])
    except json.JSONDecodeError:
        # Try to find JSON in the response
        try:
            match = re.search(r'\{[\s\S]*"user_interactions"[\s\S]*\}', text)
            if match:
                data = json.loads(match.group())
                return data.get("user_interactions", [])
        except Exception:
            pass
        return []
    except Exception as e:
        print(f"Gemini extraction failed: {e}")
        return []


def _regex_extract_from_text(page_text: str, url: str) -> list:
    """Fallback: extract Quora usernames from scraped text using regex patterns."""
    leads = []
    seen = set()

    # Look for profile URLs in text
    for match in re.finditer(r'quora\.com/profile/([A-Za-z0-9_-]+)', page_text):
        username = match.group(1)
        if username not in seen:
            seen.add(username)
            leads.append({
                "username": username.replace("-", " "),
                "bio": "",
                "post_type": "answer",
                "timestamp": "",
                "upvotes": 0,
                "profile_url": f"https://www.quora.com/profile/{username}",
            })

    return leads


def _regex_extract_quora(url: str) -> list:
    """Fallback: scrape URL directly and find profile links."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        if resp.status_code != 200:
            return []

        leads = []
        seen = set()
        for match in re.finditer(r'quora\.com/profile/([A-Za-z0-9_-]+)', resp.text):
            username = match.group(1)
            if username not in seen:
                seen.add(username)
                leads.append({
                    "username": username.replace("-", " "),
                    "bio": "",
                    "post_type": "answer",
                    "timestamp": "",
                    "upvotes": 0,
                    "profile_url": f"https://www.quora.com/profile/{username}",
                })
        return leads
    except Exception:
        return []


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Flattening
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def format_leads_to_flat_json(user_info_list: List[dict]) -> List[dict]:
    """Flatten nested extraction results into a flat list of lead records."""
    flattened = []
    seen = set()

    for info in user_info_list:
        website_url = info.get("website_url", "")
        source = info.get("source", "quora")
        for interaction in info.get("user_info", []):
            username = interaction.get("username", "")
            key = (username.lower(), website_url)
            if key in seen:
                continue
            seen.add(key)

            flattened.append({
                "Source": source.capitalize(),
                "Website URL": website_url,
                "Username": username,
                "Bio": interaction.get("bio", ""),
                "Post Type": interaction.get("post_type", ""),
                "Timestamp": interaction.get("timestamp", ""),
                "Upvotes": interaction.get("upvotes", 0),
                "Profile URL": interaction.get("profile_url", ""),
            })

    return flattened
