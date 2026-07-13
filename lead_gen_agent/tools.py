"""External search tools for enriching lead generation.

Provides Google Search (via Custom Search JSON API) and Wikipedia lookup
to give the AI better context about industries and topics before
searching Quora for leads.
"""

import requests
import urllib.parse
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

        # Parse the grounded response
        results = []
        text = response.text or ""
        lines = text.strip().split("\n")
        current = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Look for URLs in the text
            if "http" in line:
                # Extract URL
                words = line.split()
                for word in words:
                    if word.startswith("http"):
                        url = word.strip("()[]<>,\"'")
                        current["link"] = url
                        break
            if current.get("link") and not current.get("title"):
                current["title"] = line.lstrip("0123456789.-) ").strip()
                current["snippet"] = ""
            elif current.get("link") and current.get("title") and not current.get("snippet"):
                current["snippet"] = line
                results.append(current)
                current = {}

        # If parsing didn't work cleanly, return raw text as one result
        if not results and text:
            results = [{"title": "Google Search Results", "link": "", "snippet": text[:500]}]

        return results[:num_results]

    except Exception as e:
        print(f"Gemini grounded search failed: {e}")
        return []


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
        "summary_context": summary_context,
    }
