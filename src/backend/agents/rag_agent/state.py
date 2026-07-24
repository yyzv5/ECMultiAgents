"""RAG Agent State — 定义 RagState TypedDict 用于 LangGraph StateGraph。

包含 13 个字段，其中 ``messages`` 使用 ``add_messages`` reducer 实现多轮对话追加合并。
"""

from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class RagState(TypedDict):
    """RAG Agent 的 LangGraph State。

    节点间通过此 TypedDict 传递数据。
    所有字段在首次访问前都保证存在（__init__ 时设定必需字段，
    其余由 NotRequired 标注，节点写入后即有值）。
    """

    # --- 入口字段（graph.__call__ 时传入）---
    query: str
    messages: Annotated[list[BaseMessage], add_messages]

    # --- Query 改写 ---
    rewritten_query: NotRequired[str]

    # --- 检索 ---
    retrieved_docs: NotRequired[list[dict]]
    reranked_docs: NotRequired[list[dict]]
    web_results: NotRequired[list[dict]]

    # --- 上下文 ---
    context: NotRequired[str]

    # --- 校验 & 路由 ---
    is_valid: NotRequired[bool]
    need_web: NotRequired[bool]

    # --- 输出 ---
    answer: NotRequired[str]
    sources: NotRequired[list[str]]
    rejected: NotRequired[bool]
    confidence: NotRequired[float]


__all__ = ["RagState"]
