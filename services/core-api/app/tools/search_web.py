import httpx

from app.config import settings


class SearchWebTool:
    """Blueprint §8 tool: search_web. Search Agent's only MVP tool.

    Permission: network:read — outbound GET/POST to the allow-listed
    Tavily endpoint only (§9). With no SEARCH_API_KEY set in development,
    returns deterministic mock results so the agent pipeline is verifiable
    offline; production refuses to start without a key.
    """

    TAVILY_SEARCH_URL = "https://api.tavily.com/search"

    async def search(self, query: str) -> list[dict]:
        if not self._key_configured():
            return self._mock_results(query)
        return await self._tavily_search(query)

    @staticmethod
    def _key_configured() -> bool:
        key = settings.search_api_key.strip()
        return bool(key) and not key.lower().startswith("your")

    async def _tavily_search(self, query: str) -> list[dict]:
        async with httpx.AsyncClient(
            timeout=settings.search_timeout_seconds
        ) as client:
            response = await client.post(
                self.TAVILY_SEARCH_URL,
                headers={
                    "Authorization": f"Bearer {settings.search_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": query,
                    "max_results": settings.search_max_results,
                    "search_depth": "basic",
                },
            )
            response.raise_for_status()
            payload = response.json()

        results = []
        for item in payload.get("results", []):
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "score": float(item.get("score", 0.0)),
                }
            )
        return results

    @staticmethod
    def _mock_results(query: str) -> list[dict]:
        return [
            {
                "title": f"[MOCK SEARCH] Overview of {query}",
                "url": f"https://example.com/mock/search?q={query.replace(' ', '+')}&r=1",
                "content": (
                    f"This is a deterministic mock result for '{query}'. "
                    "Set SEARCH_API_KEY to enable real Tavily results."
                ),
                "score": 0.95,
            },
            {
                "title": f"[MOCK SEARCH] Deep dive: {query}",
                "url": f"https://example.org/mock/search?q={query.replace(' ', '+')}&r=2",
                "content": (
                    f"Second mock source discussing '{query}' with additional "
                    "context that a synthesis step can cite."
                ),
                "score": 0.81,
            },
            {
                "title": f"[MOCK SEARCH] Critiques and limitations of {query}",
                "url": f"https://example.net/mock/search?q={query.replace(' ', '+')}&r=3",
                "content": (
                    f"Third mock source covering counterpoints about '{query}' "
                    "so answers are not one-sided."
                ),
                "score": 0.67,
            },
        ]
