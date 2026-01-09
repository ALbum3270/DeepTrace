"""
Search Tool for DeepTrace V2.
Standardized wrapper around Tavily API for Supervisor and Worker agents.
"""

import asyncio
import os
from datetime import datetime
from typing import List, Annotated, Literal, Optional
from langchain_core.tools import tool, InjectedToolArg
from langchain_core.runnables import RunnableConfig
from tavily import AsyncTavilyClient

from src.core.models.credibility import evaluate_credibility
TAVILY_SEARCH_DESCRIPTION = (
    "A search engine optimized for comprehensive, accurate, and trusted results. "
    "Useful for when you need to answer questions about current events."
)


@tool
async def tavily_search_tool(
    queries: List[str],
    max_results: Annotated[int, InjectedToolArg] = 5,
    topic: Annotated[
        Literal["general", "news", "finance"], InjectedToolArg
    ] = "general",
    config: RunnableConfig = None,
) -> str:
    """Fetch search results from Tavily search API.

    Returns:
        Formatted string containing summarized search results.
    """
    # 1. Execute Search (with graceful fallback when API key is missing)
    results = await tavily_search_async(
        queries, max_results=max_results, topic=topic, config=config
    )

    # 2. Format Output (Simple text format for LLM consumption)
    output = []
    for i, res in enumerate(results):
        # res is a list of results for a single query
        # But tavily_search_async returns a list of *responses*, one per query.
        # Each response has 'results' key.
        query = queries[i] if i < len(queries) else "Unknown Query"
        output.append(f"### Results for query: '{query}'")

        # Sort by scoring (credibility + recency)
        sorted_items = sorted(res.get("results", []), key=score_result, reverse=True)
        for item in sorted_items:
            title = item.get("title", "No Title")
            url = item.get("url", "No URL")
            content = item.get("content", "") or item.get("raw_content", "")
            cred = evaluate_credibility(url)
            published = (
                item.get("published_date")
                or item.get("published_at")
                or item.get("date")
                or ""
            )
            if published:
                published = str(published)
            recency_days = "unknown"
            if published:
                try:
                    published_dt = datetime.fromisoformat(
                        published.replace("Z", "+00:00")
                    )
                    recency_days = max((datetime.now(published_dt.tzinfo) - published_dt).days, 0)
                except Exception:
                    recency_days = "unknown"
            # Truncate content slightly to avoid massive context for the *Worker* (Compressor will handle it)
            # But wait, Compressor needs RAW content to do its job.
            # So we should pass enough content.
            # ODR passes raw content to Summarizer model.
            # Here we are returning text to the Agent (Supervisor or Worker LLM).
            # The Worker LLM puts this into its history.
            output.append(
                f"- **{title}** ({url}) "
                f"[credibility={cred.score:.1f}, recency_days={recency_days}, published_date={published or 'unknown'}]: "
                f"{content[:2000]}..."
            )

    return "\n\n".join(output)


async def tavily_search_async(
    search_queries: List[str],
    max_results: int = 5,
    topic: str = "general",
    include_raw_content: bool = False,  # Default false to save bandwidth unless needed
    config: RunnableConfig = None,
):
    """Execute multiple Tavily search queries asynchronously."""

    api_key = get_tavily_api_key(config)
    if not api_key:
        raise ValueError("TAVILY_API_KEY is required. Please set the environment variable.")

    tavily_client = AsyncTavilyClient(api_key=api_key)

    tasks = [
        tavily_client.search(
            query,
            max_results=max_results,
            include_raw_content=include_raw_content,
            topic=topic,
        )
        for query in search_queries
    ]

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=30,
        )
    except asyncio.TimeoutError:
        raise TimeoutError("Tavily search timed out after 30 seconds")

    cleaned_results = []
    for query, res in zip(search_queries, results):
        if isinstance(res, Exception):
            raise res  # Propagate actual errors instead of hiding them
        else:
            cleaned_results.append(res)
    return cleaned_results


def get_tavily_api_key(config: RunnableConfig) -> Optional[str]:
    """Get Tavily API key from environment or config."""
    # Priority 1: Config (if injected)
    if config:
        configurable = config.get("configurable", {})
        if "tavily_api_key" in configurable:
            return configurable["tavily_api_key"]

    # Priority 2: Environment Variable
    return os.getenv("TAVILY_API_KEY")


def score_result(item: dict) -> float:
    """
    Source scoring: credibility + recency bonus.
    """
    url = item.get("url", "")
    cred = evaluate_credibility(url)
    published = (
        item.get("published_date")
        or item.get("published_at")
        or item.get("date")
        or ""
    )
    recency_bonus = 0.0
    if published:
        try:
            published_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            days = max((datetime.now(published_dt.tzinfo) - published_dt).days, 0)
            if days <= 365:
                recency_bonus = max(10 - days / 40, 0)  # up to +10 for fresh
        except Exception:
            pass
    return cred.score + recency_bonus
