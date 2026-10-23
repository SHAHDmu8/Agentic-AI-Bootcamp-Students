"""Module 5 MCP server.

This server exposes two tools over MCP:
- read_data(key): ISO country lookup like JO -> Jordan / Amman
- web_search(query): search result text or a clearly labeled deterministic mock result

Secrets remain server-side; validation is enforced before returning results.
"""

from __future__ import annotations

import os
import re
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("jhf-tools")

COUNTRIES = {
    "JO": {"country": "Jordan", "capital": "Amman"},
    "EG": {"country": "Egypt", "capital": "Cairo"},
    "TR": {"country": "Turkey", "capital": "Ankara"},
    "US": {"country": "United States", "capital": "Washington, D.C."},
}

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY") or os.getenv("SEARCH_API_KEY")
USE_MOCK_SEARCH = BRAVE_API_KEY is None
SEARCH_TIMEOUT_SECONDS = 12.0


def _error(message: str, *, code: str = "error", status_code: int | None = None, source: str = "server") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "status": "error",
        "code": code,
        "message": message,
        "source": source,
    }
    if status_code is not None:
        payload["status_code"] = status_code
    return payload


@mcp.tool()
def read_data(key: str) -> dict[str, Any]:
    """Look up a country by ISO 3166-1 alpha-2 code such as 'JO'. Returns the country and capital.

    Args:
        key: ISO country code like JO, EG, TR.
    """
    if not isinstance(key, str):
        return _error("'key' must be a string.", code="invalid_type")

    normalized = key.strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", normalized):
        return _error("Invalid ISO code. Expected exactly two letters, for example 'JO'.", code="invalid_iso_code")

    record = COUNTRIES.get(normalized)
    if record is None:
        return _error(f"No country data found for ISO code '{normalized}'.", code="not_found", status_code=404)

    return {
        "ok": True,
        "status": "success",
        "source": "lookup",
        "data": {
            "key": normalized,
            "country": record["country"],
            "capital": record["capital"],
        },
    }


@mcp.tool()
def web_search(query: str) -> dict[str, Any]:
    """Search for a query and return a single result object with a title and snippet.

    Args:
        query: The query to search, such as 'Jordan news'.
    """
    if not isinstance(query, str):
        return _error("'query' must be a string.", code="invalid_type")

    cleaned = query.strip()
    if not cleaned:
        return _error("Search query cannot be empty.", code="empty_query")

    if USE_MOCK_SEARCH:
        headline = (
            "Jordan news snapshot (mock): Jordan continues to receive sustained regional and economic attention "
            "as a stable center for diplomacy and commerce."
        )
        url = "https://example.invalid/mock-jordan-news"
        return {
            "ok": True,
            "status": "success",
            "source": "mock",
            "label": "deterministic mock result for offline testing",
            "query": cleaned,
            "result": {
                "title": "Jordan news snapshot (mock)",
                "url": url,
                "snippet": headline,
            },
        }

    try:
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": BRAVE_API_KEY,
        }
        params = {"q": cleaned, "count": 3}
        with httpx.Client(timeout=SEARCH_TIMEOUT_SECONDS) as client:
            response = client.get(url, headers=headers, params=params)
            response.raise_for_status()
            payload = response.json()

        results = payload.get("web", {}).get("results", []) if isinstance(payload, dict) else []
        if not results:
            return _error(f"No live search results found for '{cleaned}'.", code="no_results")

        first = results[0]
        return {
            "ok": True,
            "status": "success",
            "source": "live",
            "query": cleaned,
            "result": {
                "title": first.get("title") or "Untitled result",
                "url": first.get("url") or "",
                "snippet": first.get("description") or first.get("snippet") or "",
            },
        }
    except httpx.TimeoutException:
        return _error("Live search timed out after 12 seconds.", code="timeout")
    except httpx.HTTPStatusError as exc:
        return _error(f"Live search HTTP error: {exc.response.status_code}.", code="http_error", status_code=exc.response.status_code)
    except Exception as exc:  # pragma: no cover - defensive path for unexpected API conditions
        return _error(f"Live search failed: {exc}.", code="search_failed")


if __name__ == "__main__":
    mcp.run()
