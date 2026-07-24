"""Data Agent State — 定义 DataState TypedDict 用于 LangGraph StateGraph。

包含 10 个字段，其中 ``messages`` 使用 ``add_messages`` reducer 实现多轮对话追加合并。
与 RAG Agent 共用同一 reducer 模式（已由 M5.1 验证）。
"""

from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class DataState(TypedDict):
    """Data Agent 的 LangGraph State。

    节点间通过此 TypedDict 传递数据。
    所有字段在首次访问前都保证存在（__init__ 时设定必需字段，
    其余由 NotRequired 标注，节点写入后即有值）。
    """

    # --- 入口字段（graph.__call__ 时传入）---
    query: str
    messages: Annotated[list[BaseMessage], add_messages]

    # --- 分析类型与意图（classify_analysis_type / extract_intent 节点写入）---
    analysis_type: NotRequired[str]
    extracted_intent: NotRequired[str]

    # --- SQL 生成与执行（text_to_sql / execute_sql / fix_sql 节点写入）---
    generated_sql: NotRequired[str]
    sql_result: NotRequired[dict]
    sql_error: NotRequired[str]

    # --- 重试控制（execute_sql / fix_sql 节点管理）---
    retry_count: NotRequired[int]
    max_retries: NotRequired[int]

    # --- 最终输出（generate_report / predefined_report / error_response 节点写入）---
    report: NotRequired[str]


__all__ = ["DataState"]
