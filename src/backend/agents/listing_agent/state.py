"""Listing Agent State — 定义 ListingState TypedDict 用于 LangGraph StateGraph。

包含 13 个字段:
- 4 个 required（入口输入）: platform / title / image_urls / category
- 9 个 NotRequired: variations / attributes / task_id / audit_results /
  all_issues / passed / need_human_review / human_feedback / human_decision /
  fixed_content / error

Listing Agent 是单次审核任务，不引入 messages 字段与 add_messages reducer。
``audit_results`` 使用嵌套 dict(key=维度名, value=list[dict]),与 M4.2 中
Pydantic ``AuditIssue`` 形状对齐但以 dict 形式存放,避免 TypedDict 复杂泛型。
"""

from typing import NotRequired, TypedDict


class ListingState(TypedDict):
    """Listing Agent 的 LangGraph State。

    节点间通过此 TypedDict 传递数据。
    所有字段在首次访问前都保证存在（``__init__`` 时设定必需字段,
    其余由 ``NotRequired`` 标注,节点写入后即有值）。
    """

    # --- 入口字段（graph.__call__ 时传入）---
    platform: str
    title: str
    image_urls: list[str]
    category: str

    # --- 入口可选字段（默认空）---
    variations: NotRequired[list[dict]]
    attributes: NotRequired[dict]

    # --- 任务标识（task_parse 节点写入）---
    task_id: NotRequired[str]

    # --- 审核结果 ---
    audit_results: NotRequired[dict]
    all_issues: NotRequired[list[dict]]

    # --- 决策标志 ---
    passed: NotRequired[bool]
    need_human_review: NotRequired[bool]

    # --- 人机协同 ---
    human_feedback: NotRequired[str]
    human_decision: NotRequired[str]

    # --- 自动修复与错误兜底 ---
    fixed_content: NotRequired[dict]
    error: NotRequired[str]


__all__ = ["ListingState"]