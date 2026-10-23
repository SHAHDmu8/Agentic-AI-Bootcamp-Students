# Module 5 MCP Tool Schema

## `read_data(key: str) -> dict`

Purpose:
- Lookup a country by ISO 3166-1 alpha-2 code.

Arguments:
- `key: str` — two-letter uppercase ISO code such as `JO`, `EG`, or `TR`.

Successful output:
- `{"ok": true, "status": "success", "source": "lookup", "data": {"key": "JO", "country": "Jordan", "capital": "Amman"}}`

Error cases:
- Non-string input -> `{"ok": false, "status": "error", "code": "invalid_type", "message": "'key' must be a string."}`
- Empty or invalid code -> `{"ok": false, "status": "error", "code": "invalid_iso_code", "message": "Invalid ISO code. Expected exactly two letters, for example 'JO'."}`
- Unknown code -> `{"ok": false, "status": "error", "code": "not_found", "status_code": 404}`

## `web_search(query: str) -> dict`

Purpose:
- Return one headline/snippet for a web search query.

Arguments:
- `query: str` — non-empty query like `Jordan news`.

Successful output:
- Live API path: `{"ok": true, "status": "success", "source": "live", "query": "Jordan news", "result": {"title": "...", "url": "https://...", "snippet": "..."}}`
- Mock fallback path: `{"ok": true, "status": "success", "source": "mock", "label": "deterministic mock result for offline testing", "query": "Jordan news", "result": {"title": "Jordan news snapshot (mock)", "url": "https://example.invalid/mock-jordan-news", "snippet": "..."}}`

Error cases:
- Non-string input -> `{"ok": false, "status": "error", "code": "invalid_type"}`
- Empty query -> `{"ok": false, "status": "error", "code": "empty_query"}`
- Timeout -> `{"ok": false, "status": "error", "code": "timeout"}`
- HTTP failure -> `{"ok": false, "status": "error", "code": "http_error", "status_code": 401}`
- No results -> `{"ok": false, "status": "error", "code": "no_results"}`

## Notes

- Secrets remain on the server side; the agent does not receive the API key.
- Mock search results are clearly labeled as mock and must never be represented as current live news.
- The MCP client discovers and invokes these tools through the stdio transport, not by direct Python imports.
