"""Resilient search orchestration for LeadForge.

The provider-specific scraper changes over time.  This module isolates the
application from those changes and records every recovery decision so the UI
can explain what happened instead of exposing a raw Python exception.
"""

from dataclasses import dataclass, field
import inspect
from typing import Callable, List
from urllib.parse import quote_plus, urlparse

from tools import google_search


@dataclass
class SearchAttempt:
    """One observable step in the source-search recovery pipeline."""

    name: str
    outcome: str
    detail: str


@dataclass
class SearchRecoveryResult:
    """URLs found plus an audit trail that can be rendered in Streamlit."""

    url_items: List[dict] = field(default_factory=list)
    attempts: List[SearchAttempt] = field(default_factory=list)


def find_urls_with_recovery(
    search_function: Callable,
    query: str,
    sources: List[str],
    num_links: int,
    google_api_key: str,
) -> SearchRecoveryResult:
    """Search sources, adapting to stale modules and provider failures.

    Recovery order:
    1. Use the scraper's normal DuckDuckGo + grounded-search path.
    2. If Streamlit has an older scraper module cached, call its compatible
       signature instead of failing on a newly added keyword argument.
    3. If no URLs are returned, use Gemini's grounded citations directly for
       each selected source.
    """
    result = SearchRecoveryResult()
    supports_grounded_fallback = "google_api_key" in inspect.signature(
        search_function
    ).parameters

    try:
        arguments = {"num_links": num_links, "sources": sources}
        if supports_grounded_fallback:
            arguments["google_api_key"] = google_api_key
            label = "DuckDuckGo + Gemini source fallback"
        else:
            label = "DuckDuckGo compatibility mode"
            result.attempts.append(SearchAttempt(
                "Compatibility check",
                "recovered",
                "An older scraper module is still loaded. LeadForge skipped the "
                "new keyword argument and continued safely.",
            ))

        result.url_items = search_function(query, **arguments)
        if result.url_items:
            result.attempts.append(SearchAttempt(
                label, "success", f"Found {len(result.url_items)} source pages.",
            ))
            return result
        result.attempts.append(SearchAttempt(
            label, "empty", "The provider returned no matching source pages.",
        ))
    except Exception as exc:
        result.attempts.append(SearchAttempt(
            "Primary source search", "failed", _safe_error_message(exc),
        ))

    fallback_urls = _find_grounded_source_urls(
        query, sources, num_links, google_api_key,
    )
    if fallback_urls:
        result.url_items = fallback_urls
        result.attempts.append(SearchAttempt(
            "Gemini citation fallback",
            "recovered",
            f"Found {len(fallback_urls)} source pages from grounded citations.",
        ))
        return result

    result.attempts.append(SearchAttempt(
        "Gemini citation fallback",
        "empty",
        "No citations matched the selected source domains.",
    ))

    # External search engines can return bot-protection pages. A source-native
    # search page still gives the extraction stage a valid, relevant starting
    # URL without relying on DuckDuckGo, Bing, or an additional API key.
    native_urls = _native_source_search_pages(query, sources)
    if native_urls:
        result.url_items = native_urls
        result.attempts.append(SearchAttempt(
            "Source-native search fallback",
            "recovered",
            "External search was unavailable, so LeadForge opened the selected "
            "platform's own search page.",
        ))
    else:
        result.attempts.append(SearchAttempt(
            "Source-native search fallback",
            "empty",
            "No source-native search route is configured for the selected source.",
        ))
    return result


def _find_grounded_source_urls(
    query: str,
    sources: List[str],
    num_links: int,
    google_api_key: str,
) -> List[dict]:
    """Convert Gemini source citations into the scraper's URL-item schema."""
    domains = {"quora": "quora.com", "pinterest": "pinterest.com"}
    url_items = []
    seen_urls = set()

    for source in sources:
        domain = domains.get(source)
        if not domain:
            continue
        try:
            web_results = google_search(
                f"site:{domain} {query}", google_api_key, num_results=num_links,
            )
        except Exception:
            continue
        for web_result in web_results:
            url = web_result.get("link", "")
            if url and _matches_domain(url, domain) and url not in seen_urls:
                seen_urls.add(url)
                url_items.append({"url": url, "source": source})
    return url_items


def _matches_domain(url: str, domain: str) -> bool:
    host = urlparse(url).netloc.lower().split(":", 1)[0]
    return host == domain or host.endswith(f".{domain}")


def _native_source_search_pages(query: str, sources: List[str]) -> List[dict]:
    """Return platform search pages when external search providers are blocked."""
    encoded_query = quote_plus(query)
    search_pages = {
        "quora": f"https://www.quora.com/search?q={encoded_query}",
        "pinterest": f"https://www.pinterest.com/search/pins/?q={encoded_query}",
    }
    return [
        {"url": search_pages[source], "source": source}
        for source in sources
        if source in search_pages
    ]


def _safe_error_message(error: Exception) -> str:
    """Make technical failures readable without leaking credentials."""
    message = str(error).replace("\n", " ").strip()
    return message[:180] or error.__class__.__name__
