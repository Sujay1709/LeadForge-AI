"""External search tools for enriching lead generation.

Provides Google Search (via Custom Search JSON API) and Wikipedia lookup
to give the AI better context about industries and topics before
searching Quora for leads.
"""

import requests
import urllib.parse
import re
import xml.etree.ElementTree as ET
from typing import List, Optional


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Google Custom Search
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def google_search(
    query: str,
    google_api_key: str,
    cx: str = "",
    num_results: int = 5,
) -> List[dict]:
    """Search Google using the Custom Search JSON API.

    Works with ANY Google API key (same key used for Gemini).
    If no Custom Search Engine ID (cx) is provided, falls back to
    the free SerpAPI-style scraping via Google's public search.

    Args:
        query: Search query string.
        google_api_key: Google API key (same as Gemini key).
        cx: Custom Search Engine ID (optional — get one free at
            https://programmablesearchengine.google.com).
        num_results: Number of results to return (max 10).

    Returns:
        List of dicts with keys: title, link, snippet.
    """
    # Strategy 1: Google Custom Search API (if cx provided)
    if cx:
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": google_api_key,
                "cx": cx,
                "q": query,
                "num": min(num_results, 10),
            }
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            results = []
            for item in data.get("items", []):
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                })
            return results
        except Exception as e:
            print(f"Google Custom Search failed: {e}")

    # Strategy 2: Free Google search via Gemini grounding (no cx needed)
    # Use google-genai with google_search tool for grounded results
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=google_api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"Search the web for: {query}\n\nReturn the top {num_results} results as a numbered list with title, URL, and a one-line description for each.",
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )

        # Grounded responses expose source URLs as structured citation metadata.
        # Prefer this over asking the model to print URLs in prose: models may
        # omit URLs even when the search tool found valid sources.
        results = _grounding_results(response, num_results)
        if results:
            return results

        # Compatibility fallback for SDK responses that do not expose grounding
        # metadata. This also supports models that include direct links in text.
        text = response.text or ""
        return _urls_from_text(text, num_results)

    except Exception as e:
        print(f"Gemini grounded search failed: {e}")
        return []


def _get_value(value, key: str, default=None):
    """Read a field from either a google-genai model object or a dict."""
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _grounding_results(response, num_results: int) -> List[dict]:
    """Extract title and URL pairs from Gemini Google Search citations."""
    results = []
    seen_urls = set()

    for candidate in _get_value(response, "candidates", []) or []:
        metadata = _get_value(candidate, "grounding_metadata")
        chunks = _get_value(metadata, "grounding_chunks", []) or []
        for chunk in chunks:
            web = _get_value(chunk, "web")
            url = _get_value(web, "uri", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            results.append({
                "title": _get_value(web, "title", "Web result"),
                "link": url,
                "snippet": "",
            })
            if len(results) >= num_results:
                return results
    return results


def _urls_from_text(text: str, num_results: int) -> List[dict]:
    """Last-resort URL parser for non-standard grounded responses."""
    results = []
    seen_urls = set()
    for match in re.finditer(r"https?://[^\s\]\)>\",]+", text):
        url = match.group(0).rstrip(".,;:")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        line_start = text.rfind("\n", 0, match.start()) + 1
        title = text[line_start:match.start()].strip(" -0123456789.)[]") or "Web result"
        results.append({"title": title, "link": url, "snippet": ""})
        if len(results) >= num_results:
            break
    return results


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Wikipedia Search
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def wikipedia_search(
    query: str,
    num_results: int = 3,
) -> List[dict]:
    """Search Wikipedia for relevant articles. No API key needed.

    Uses the Wikipedia REST API to find articles and extract summaries.

    Args:
        query: Search query string.
        num_results: Number of articles to return.

    Returns:
        List of dicts with keys: title, summary, url.
    """
    results = []

    try:
        # Step 1: Search for matching articles
        search_url = "https://en.wikipedia.org/w/api.php"
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": num_results,
            "format": "json",
            "utf8": 1,
        }
        resp = requests.get(search_url, params=search_params, timeout=10)
        resp.raise_for_status()
        search_data = resp.json()

        titles = [
            item["title"]
            for item in search_data.get("query", {}).get("search", [])
        ]

        if not titles:
            return []

        # Step 2: Get summaries for each article
        for title in titles:
            try:
                summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title)}"
                resp = requests.get(summary_url, timeout=10, headers={"User-Agent": "LeadForgeAI/1.0"})
                resp.raise_for_status()
                data = resp.json()

                results.append({
                    "title": data.get("title", title),
                    "summary": data.get("extract", "")[:400],
                    "url": data.get("content_urls", {}).get("desktop", {}).get("page", f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}"),
                })
            except Exception:
                results.append({
                    "title": title,
                    "summary": "",
                    "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}",
                })

    except Exception as e:
        print(f"Wikipedia search failed: {e}")

    return results


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Academic Paper Search (arXiv)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_PAPER_QUERY_TERMS = ("paper", "papers", "research", "arxiv", "publication", "publications")


def is_paper_query(query: str) -> bool:
    """Return whether a query is likely asking for academic material."""
    normalized = query.lower()
    return any(term in normalized for term in _PAPER_QUERY_TERMS)


def arxiv_search(query: str, num_results: int = 5) -> List[dict]:
    """Return live arXiv records, including direct PDF download links.

    arXiv is a primary research repository. Unlike a search-engine snippet,
    each returned record has a stable abstract URL and a downloadable PDF URL.
    """
    try:
        topic_words = [
            word for word in re.findall(r"[A-Za-z0-9+-]+", query.lower())
            if word not in _PAPER_QUERY_TERMS
            and word not in {"recent", "latest", "download", "downloadable", "find", "list"}
        ]
        search_expression = " AND ".join(f"all:{word}" for word in topic_words[:5])
        if not search_expression:
            search_expression = "all:artificial intelligence"
        response = requests.get(
            "https://export.arxiv.org/api/query",
            params={
                "search_query": search_expression,
                "start": 0,
                "max_results": min(num_results, 10),
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            },
            headers={"User-Agent": "LeadForgeAI/1.0 (research discovery)"},
            timeout=15,
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
        atom = {"atom": "http://www.w3.org/2005/Atom"}
        results = []
        for entry in root.findall("atom:entry", atom):
            abstract_url = (entry.findtext("atom:id", default="", namespaces=atom) or "").strip()
            if not abstract_url:
                continue
            paper_id = abstract_url.rstrip("/").split("/")[-1]
            results.append({
                "title": " ".join((entry.findtext("atom:title", default="", namespaces=atom) or "").split()),
                "link": abstract_url.replace("http://", "https://"),
                "download_url": f"https://arxiv.org/pdf/{paper_id}.pdf",
                "snippet": " ".join((entry.findtext("atom:summary", default="", namespaces=atom) or "").split())[:400],
                "source": "arXiv",
                "result_type": "Research paper",
            })
        return results
    except (requests.RequestException, ET.ParseError) as exc:
        print(f"arXiv search failed: {exc}")
        return []


def discover_live_web_results(
    query: str,
    google_api_key: str,
    num_results: int = 5,
    grounded_results: Optional[List[dict]] = None,
) -> List[dict]:
    """Combine grounded websites with primary-source papers for the UI.

    Results are only included when they have a real HTTP(S) URL, preventing
    model summaries from being shown as if they were clickable web pages.
    """
    results = []
    seen_urls = set()

    source_results = grounded_results
    if source_results is None:
        source_results = google_search(query, google_api_key, num_results=num_results)

    for result in source_results:
        url = result.get("link", "")
        if not url.startswith(("https://", "http://")) or url in seen_urls:
            continue
        seen_urls.add(url)
        results.append({
            "title": result.get("title") or "Web result",
            "link": url,
            "download_url": url if url.lower().split("?", 1)[0].endswith(".pdf") else "",
            "snippet": result.get("snippet", ""),
            "source": "Grounded web",
            "result_type": "PDF" if url.lower().split("?", 1)[0].endswith(".pdf") else "Website",
        })

    if is_paper_query(query):
        for paper in arxiv_search(query, num_results=num_results):
            if paper["link"] not in seen_urls:
                seen_urls.add(paper["link"])
                results.append(paper)
    return results


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Combined Research Tool
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def research_topic(
    query: str,
    google_api_key: str,
    google_cx: str = "",
    num_google: int = 5,
    num_wiki: int = 2,
) -> dict:
    """Run both Google Search and Wikipedia to build context about a topic.

    This gives the AI richer context about the industry/problem space
    before it searches Quora for leads.

    Args:
        query: The search query / topic to research.
        google_api_key: Google API key.
        google_cx: Google Custom Search Engine ID (optional).
        num_google: Number of Google results.
        num_wiki: Number of Wikipedia articles.

    Returns:
        Dict with keys: google_results, wiki_results, summary_context.
    """
    google_results = google_search(query, google_api_key, google_cx, num_google)
    wiki_results = wikipedia_search(query, num_wiki)
    live_results = discover_live_web_results(
        query, google_api_key, num_google, grounded_results=google_results,
    )

    # Build a text summary for the AI to use as context
    context_parts = []

    if google_results:
        context_parts.append("## Web Search Results")
        for i, r in enumerate(google_results, 1):
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            if title or snippet:
                context_parts.append(f"{i}. **{title}**: {snippet}")

    if wiki_results:
        context_parts.append("\n## Wikipedia Context")
        for r in wiki_results:
            title = r.get("title", "")
            summary = r.get("summary", "")
            if title and summary:
                context_parts.append(f"**{title}**: {summary}")

    summary_context = "\n".join(context_parts) if context_parts else ""

    return {
        "google_results": google_results,
        "wiki_results": wiki_results,
        "live_results": live_results,
        "summary_context": summary_context,
    }
