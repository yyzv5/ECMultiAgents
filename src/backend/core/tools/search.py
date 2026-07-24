"""Tavily 联网搜索 Tool。

封装 :class:`tavily.TavilyClient` 为 LangChain ``@tool``,供 RAG Agent
的 ``web_search`` 节点调用。

实现要点:
    - 用 ``tavily-python==0.7.26`` 原生 ``TavilyClient``,不依赖
      ``langchain-community.tools.tavily_search.TavilySearchResults``
      (该 API 在 langchain-community 0.3.25 起 deprecated)。
    - 客户端惰性构造: 模块 import 时不实例化,首次调用 ``web_search``
      时才读取 ``settings.TAVILY_API_KEY`` 构造客户端。
    - 异常时返回 ``"Search failed: <error>"`` 字符串(LangChain Tool
      惯例): Tool 不应向上抛异常,以字符串形式将错误传给 LLM。
"""
from __future__ import annotations

import logging

from langchain_core.tools import tool
from tavily import TavilyClient

from backend.config import settings

logger = logging.getLogger(__name__)

_client: TavilyClient | None = None


def _get_client() -> TavilyClient:
    """惰性构造并返回模块级单例 :class:`TavilyClient`。

    Returns:
        配置好 API key 的 ``TavilyClient`` 实例。
    """
    global _client
    if _client is None:
        _client = TavilyClient(api_key=settings.TAVILY_API_KEY.get_secret_value())
        logger.info("TavilyClient initialized.")
    return _client


@tool
def web_search(query: str, max_results: int = 5) -> list[dict[str, str]] | str:
    """联网搜索: 调用 Tavily 返回与 query 相关的结果列表。

    Args:
        query: 搜索关键词。
        max_results: 最大返回结果数,默认 5。

    Returns:
        成功时: ``[{"content": "...", "url": "..."}, ...]``,
        每条只保留 ``content`` 和 ``url`` 两个字段。
        失败时: ``"Search failed: <error>"`` 字符串(便于 LLM 识别错误)。
    """
    try:
        client = _get_client()
        resp = client.search(query=query, max_results=max_results)
    except Exception as exc:
        logger.warning("Tavily search failed for query=%r: %s", query, exc)
        return f"Search failed: {exc}"

    raw_results = resp.get("results", []) if isinstance(resp, dict) else []
    return [{"content": r["content"], "url": r["url"]} for r in raw_results]


__all__ = ["web_search"]