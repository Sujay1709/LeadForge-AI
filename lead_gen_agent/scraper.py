"""Multi-source web scraper for lead discovery and extraction.

Supports Quora and Pinterest as lead sources via Firecrawl.
"""

import requests
import hashlib
import time
from typing import List, Optional
from firecrawl import FirecrawlApp
from schemas import QuoraPageSchema
from config import DEFAULT_SEARCH_LOCATION, DEFAULT_SEARCH_LANG


def search_for_urls(
    company_description: str,
    firecrawl_api_key: str,
    num_links: int = 5,
    sources: Optional[List[str]] = None,
) -> List[dict]:
    """Search for relevant URLs across multiple platforms."""
    if sources is None:
        sources = ["quora"]

    all_results = []

    for source in sources:
        if source == "quora":
            urls = _search_quora(company_description, firecrawl_api_key, num_links)
            all_results.extend([{"url": u, "source": "quora"} for u in urls])
        elif source == "pinterest":
            urls = _search_pinterest(company_description, firecrawl_api_key, num_links)
            all_results.extend([{"url": u, "source": "pinterest"} for u in urls])

    return all_results


def _search_quora(
    company_description: str,
    firecrawl_api_key: str,
    num_links: int = 5,
) -> List[str]:
    """Search for relevant Quora URLs using Firecrawl REST API."""
    url = "https://api.firecrawl.dev/v1/search"
    payload = {
        "query": f"quora websites where people are looking for {company_description}",
        "limit": num_links,
        "lang": DEFAULT_SEARCH_LANG,
        "location": DEFAULT_SEARCH_LOCATION,
    }
    headers = {
        "Authorization": f"Bearer {firecrawl_api_key}",
        "Content-Type": "application/json",
    }

    response = requests.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()

    urls = []
    if data.get("success") and "data" in data:
        for result in data["data"]:
            result_url = result.get("url", "")
            if "quora.com" in result_url:
                urls.append(result_url)

    return urls


def _search_pinterest(
    company_description: str,
    firecrawl_api_key: str,
    num_links: int = 5,
) -> List[str]:
    """Search for relevant Pinterest URLs using Firecrawl REST API."""
    url = "https://api.firecrawl.dev/v1/search"
    payload = {
        "query": f"pinterest {company_description} inspiration ideas templates",
        "limit": num_links,
        "lang": DEFAULT_SEARCH_LANG,
        "location": DEFAULT_SEARCH_LOCATION,
    }
    headers = {
        "Authorization": f"Bearer {firecrawl_api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        urls = []
        if data.get("success") and "data" in data:
            for result in data["data"]:
                result_url = result.get("url", "")
                if "pinterest" in result_url:
                    urls.append(result_url)

        return urls
    except Exception as e:
        print(f"Pinterest search failed: {e}")
        return []


def extract_user_info_from_urls(
    url_items: list,
    firecrawl_api_key: str,
) -> List[dict]:
    """Extract user information from URLs using Firecrawl LLM extract."""
    firecrawl_app = FirecrawlApp(api_key=firecrawl_api_key)
    results = []

    for item in url_items:
        if isinstance(item, str):
            url = item
            source = "quora"
        else:
            url = item["url"]
            source = item.get("source", "quora")

        try:
            if source == "quora":
                response = firecrawl_app.extract(
                    [url],
                    prompt="Extract all user information from this Quora page. "
                           "For each user who posted a question or answer, extract their "
                           "username, bio, post type (question/answer), timestamp, "
                           "upvote count, and profile URL.",
                    schema=QuoraPageSchema.model_json_schema(),
                )
                user_info = _parse_extract_response(response)
            elif source == "pinterest":
                response = firecrawl_app.extract(
                    [url],
                    prompt="Extract information from this Pinterest page. "
                           "For each pin or user, extract the username/creator name, "
                           "description or bio, content type (pin/board/profile), "
                           "and any profile or pin URL.",
                    schema=QuoraPageSchema.model_json_schema(),
                )
                user_info = _parse_extract_response(response)
            else:
                continue

            if user_info:
                results.append({"website_url": url, "source": source, "user_info": user_info})

        except Exception as e:
            print(f"Extract failed for {url}: {e}")
            if source == "quora":
                fallback = _scrape_fallback(firecrawl_app, url)
                if fallback:
                    results.append({"website_url": url, "source": source, "user_info": fallback})

    return results


def _parse_extract_response(response) -> list:
    """Parse Firecrawl extract response across SDK versions."""
    if not response:
        return []

    if hasattr(response, "data"):
        data = response.data
    elif isinstance(response, dict):
        if not response.get("success", True):
            return []
        data = response.get("data", response)
    else:
        return []

    if isinstance(data, dict) and "user_interactions" in data:
        return data["user_interactions"]

    if isinstance(data, list):
        interactions = []
        for item in data:
            if isinstance(item, dict) and "user_interactions" in item:
                interactions.extend(item["user_interactions"])
        return interactions

    return []


def _scrape_fallback(firecrawl_app: FirecrawlApp, url: str) -> list:
    """Fallback: scrape page and extract profile links from markdown."""
    try:
        result = firecrawl_app.scrape(url, formats=["markdown"])

        markdown = ""
        if hasattr(result, "markdown"):
            markdown = result.markdown or ""
        elif isinstance(result, dict):
            markdown = result.get("markdown", "")

        if len(markdown) < 100:
            return []

        leads = []
        seen = set()
        for line in markdown.split("\n"):
            if "quora.com/profile/" in line:
                parts = line.split("quora.com/profile/")
                if len(parts) > 1:
                    username = parts[1].split(")")[0].split("?")[0].split("/")[0].strip()
                    if username and username not in seen:
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
"""Firecrawl-based Quora scraper for lead discovery and extraction."""

import requests
from typing import List
from firecrawl import FirecrawlApp
from schemas import QuoraPageSchema
from config import DEFAULT_SEARCH_LOCATION, DEFAULT_SEARCH_LANG


def search_for_urls(
    company_description: str,
    firecrawl_api_key: str,
    num_links: int = 5,
) -> List[str]:
    """Search for relevant Quora URLs using Firecrawl REST API.

    Uses raw REST calls (not the SDK) for maximum compatibility.

    Args:
        company_description: Concise description of what leads to search for.
        firecrawl_api_key: Firecrawl API key.
        num_links: Max number of URLs to return.

    Returns:
        List of Quora URLs matching the query.
    """
    url = "https://api.firecrawl.dev/v1/search"
    payload = {
        "query": f"quora websites where people are looking for {company_description}",
        "limit": num_links,
        "lang": DEFAULT_SEARCH_LANG,
        "location": DEFAULT_SEARCH_LOCATION,
    }
    headers = {
        "Authorization": f"Bearer {firecrawl_api_key}",
        "Content-Type": "application/json",
    }

    response = requests.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()

    urls = []
    if data.get("success") and "data" in data:
        for result in data["data"]:
            result_url = result.get("url", "")
            if "quora.com" in result_url:
                urls.append(result_url)

    return urls


def extract_user_info_from_urls(
    urls: List[str],
    firecrawl_api_key: str,
) -> List[dict]:
    """Extract user information from Quora URLs using Firecrawl LLM extract.

    Args:
        urls: List of Quora URLs to extract from.
        firecrawl_api_key: Firecrawl API key.

    Returns:
        List of dicts with 'website_url' and 'user_info' keys.
    """
    firecrawl_app = FirecrawlApp(api_key=firecrawl_api_key)
    results = []

    for url in urls:
        try:
            response = firecrawl_app.extract(
                [url],
                prompt="Extract all user information from this Quora page. "
                       "For each user who posted a question or answer, extract their "
                       "username, bio, post type (question/answer), timestamp, "
                       "upvote count, and profile URL.",
                schema=QuoraPageSchema.model_json_schema(),
            )

            # Handle multiple response shapes from different SDK versions
            user_info = _parse_extract_response(response)
            if user_info:
                results.append({"website_url": url, "user_info": user_info})

        except Exception as e:
            print(f"Extract failed for {url}: {e}")
            # Fallback: try scraping the page for profile links
            fallback = _scrape_fallback(firecrawl_app, url)
            if fallback:
                results.append({"website_url": url, "user_info": fallback})

    return results


def _parse_extract_response(response) -> list:
    """Parse Firecrawl extract response across SDK versions."""
    if not response:
        return []

    # Get the data payload
    if hasattr(response, "data"):
        data = response.data
    elif isinstance(response, dict):
        if not response.get("success", True):
            return []
        data = response.get("data", response)
    else:
        return []

    # data is dict with user_interactions
    if isinstance(data, dict) and "user_interactions" in data:
        return data["user_interactions"]

    # data is a list of dicts
    if isinstance(data, list):
        interactions = []
        for item in data:
            if isinstance(item, dict) and "user_interactions" in item:
                interactions.extend(item["user_interactions"])
        return interactions

    return []


def _scrape_fallback(firecrawl_app: FirecrawlApp, url: str) -> list:
    """Fallback: scrape page and extract profile links from markdown."""
    try:
        result = firecrawl_app.scrape(url, formats=["markdown"])

        markdown = ""
        if hasattr(result, "markdown"):
            markdown = result.markdown or ""
        elif isinstance(result, dict):
            markdown = result.get("markdown", "")

        if len(markdown) < 100:
            return []

        leads = []
        seen = set()
        for line in markdown.split("\n"):
            if "quora.com/profile/" in line:
                parts = line.split("quora.com/profile/")
                if len(parts) > 1:
                    username = parts[1].split(")")[0].split("?")[0].split("/")[0].strip()
                    if username and username not in seen:
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


def format_leads_to_flat_json(user_info_list: List[dict]) -> List[dict]:
    """Flatten nested extraction results into a flat list of lead records.

    Args:
        user_info_list: Output from extract_user_info_from_urls().

    Returns:
        List of flat dicts, one per user interaction.
    """
    flattened = []
    seen = set()

    for info in user_info_list:
        website_url = info.get("website_url", "")
        for interaction in info.get("user_info", []):
            username = interaction.get("username", "")
            key = (username.lower(), website_url)
            if key in seen:
                continue
            seen.add(key)

            flattened.append({
                "Website URL": website_url,
                "Username": username,
                "Bio": interaction.get("bio", ""),
                "Post Type": interaction.get("post_type", ""),
                "Timestamp": interaction.get("timestamp", ""),
                "Upvotes": interaction.get("upvotes", 0),
                "Profile URL": interaction.get("profile_url", ""),
            })

    return flattened
