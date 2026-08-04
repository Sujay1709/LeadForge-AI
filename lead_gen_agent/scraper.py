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
from urllib.parse import parse_qs, unquote, urlparse, urlsplit
from typing import List, Optional
from bs4 import BeautifulSoup
from config import DEFAULT_SEARCH_LOCATION, DEFAULT_SEARCH_LANG
from tools import google_search

try:
    from duckduckgo_search import DDGS
except ImportError:
    try:
        # ``ddgs`` is the maintained successor to duckduckgo-search.
        from ddgs import DDGS
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
    google_api_key: str = "",
) -> List[dict]:
    """Search for relevant URLs across multiple platforms using DuckDuckGo.

    Args:
        company_description: Concise description of what leads to search for.
        api_key: Unused (kept for backward compatibility).
        num_links: Max number of URLs to return per source.
        sources: List of sources to search. Defaults to ["quora"].
        google_api_key: Optional Gemini key used as a grounded-search fallback.

    Returns:
        List of dicts with 'url' and 'source' keys.
    """
    if sources is None:
        sources = ["quora"]

    all_results = []

    for source in sources:
        urls = []
        ddg_error = None
        if DDGS is not None:
            try:
                if source == "quora":
                    urls = _search_quora(company_description, num_links)
                elif source == "pinterest":
                    urls = _search_pinterest(company_description, num_links)
            except RuntimeError as exc:
                ddg_error = exc

        # DuckDuckGo can legitimately return no results for an indexed source.
        # Gemini grounding gives us a second, independently indexed provider.
        if not urls and google_api_key:
            urls = _grounded_source_search(
                company_description, source, num_links, google_api_key,
            )

        if ddg_error and not urls:
            raise ddg_error
        all_results.extend({"url": url, "source": source} for url in urls)

    return all_results


def _search_quora(company_description: str, num_links: int = 5) -> List[str]:
    """Search DuckDuckGo for Quora URLs matching the lead description."""
    return _search_source_with_query_variants(
        company_description, num_links, "quora.com",
    )


def _search_pinterest(company_description: str, num_links: int = 5) -> List[str]:
    """Search DuckDuckGo for Pinterest URLs matching the lead description."""
    return _search_source_with_query_variants(
        f"{company_description} ideas templates", num_links, "pinterest.com",
    )


def _search_source_with_query_variants(
    description: str, num_links: int, domain: str,
) -> List[str]:
    """Retry a strict site query with a broader, source-aware query.

    A strict multi-word site query can legitimately have no index matches. The
    second query preserves the source domain but removes exact-phrase pressure,
    increasing recall without returning pages from unrelated websites.
    """
    words = description.split()
    broader_description = " ".join(words[1:]) if len(words) > 1 else description
    queries = [
        f"site:{domain} {description}",
        f"site:{domain} {broader_description}",
    ]
    urls = []
    seen_urls = set()
    for query in queries:
        for url in _ddg_search(query, num_links, domain):
            if url not in seen_urls:
                seen_urls.add(url)
                urls.append(url)
                if len(urls) >= num_links:
                    return urls
    return urls


def _grounded_source_search(
    company_description: str,
    source: str,
    num_links: int,
    google_api_key: str,
) -> List[str]:
    """Use Gemini Google Search citations when DuckDuckGo finds no source URLs."""
    domains = {"quora": "quora.com", "pinterest": "pinterest.com"}
    domain = domains.get(source)
    if not domain:
        return []

    results = google_search(
        query=f"site:{domain} {company_description}",
        google_api_key=google_api_key,
        num_results=num_links,
    )
    urls = []
    seen_urls = set()
    for result in results:
        url = result.get("link", "")
        if url and _url_matches_domain(url, domain) and url not in seen_urls:
            seen_urls.add(url)
            urls.append(url)
    return urls


def _url_matches_domain(url: str, domain: str) -> bool:
    """Accept an exact domain or one of its subdomains, but not lookalikes."""
    host = urlparse(url).netloc.lower().split(":", 1)[0]
    return host == domain or host.endswith(f".{domain}")


def _ddg_search(query: str, max_results: int, domain_filter: str) -> List[str]:
    """Run DuckDuckGo search with library and HTML-result fallbacks.

    The maintained DDGS package can still be unavailable or temporarily
    blocked.  DuckDuckGo's lightweight HTML response is an independent
    fallback that needs only ``requests`` and BeautifulSoup, both already used
    elsewhere in the project.
    """
    errors = []
    urls = []
    if DDGS is not None:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results * 2))
            urls = _filter_source_urls(results, domain_filter, max_results)
            if urls:
                return urls
        except Exception as exc:
            errors.append(f"DDGS library: {exc}")

    try:
        html_urls = _ddg_html_search(query, max_results, domain_filter)
        if html_urls:
            return html_urls
    except Exception as exc:
        errors.append(f"DuckDuckGo HTML: {exc}")

    if errors:
        raise RuntimeError(
            "DuckDuckGo could not complete either search method. "
            + " | ".join(errors)
        )
    return []


def _filter_source_urls(results: list, domain: str, max_results: int) -> List[str]:
    """Keep valid, unique URLs that belong to the selected source domain."""
    urls = []
    seen_urls = set()
    for result in results:
        url = result.get("href", "") or result.get("link", "")
        if url and _url_matches_domain(url, domain) and url not in seen_urls:
            seen_urls.add(url)
            urls.append(url)
            if len(urls) >= max_results:
                break
    return urls


def _ddg_html_search(query: str, max_results: int, domain: str) -> List[str]:
    """Search DuckDuckGo's HTML endpoint when the DDGS package is unavailable."""
    response = requests.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers=_HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    if response.status_code == 202 or "anomaly-modal" in response.text.lower():
        raise RuntimeError(
            "DuckDuckGo returned a bot-protection page instead of search results."
        )
    soup = BeautifulSoup(response.text, "html.parser")
    candidates = []
    for link in soup.select("a.result__a"):
        href = link.get("href", "")
        url = _unwrap_ddg_redirect(href)
        candidates.append({"href": url})
    return _filter_source_urls(candidates, domain, max_results)


def _unwrap_ddg_redirect(url: str) -> str:
    """Extract the destination URL from DuckDuckGo redirect links."""
    parsed = urlsplit(url)
    redirect_url = parse_qs(parsed.query).get("uddg", [""])[0]
    return unquote(redirect_url) if redirect_url else url


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
