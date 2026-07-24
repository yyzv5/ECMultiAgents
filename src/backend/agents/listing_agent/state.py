"""Listing Agent State — 定义 ListingState TypedDict 用于 LangGraph StateGraph。

包含 15 个字段:
- 4 个 required（入口输入）: platform / title / image_urls / category
- 11 个 NotRequired: variations / attributes / task_id / audit_results /
  all_issues / passed / need_human_review / human_feedback / human_decision /
  fixed_content / error

Listing Agent 是单次审核任务，不引入 messages 字段与 add_messages reducer。
``audit_results`` 使用嵌套 dict(key=维度名, value=list[dict]),内层 dict 字段
与 M4.2 Pydantic AuditIssue 完全对齐。

``audit_results`` 通过 :class:`Annotated` 包装自定义 reducer
:func:`_merge_audit_dicts`,使 5 个并行审核节点（LangGraph ``Send`` API
扇出）可以各自写入不同子键（``title``/``image``/``variation``/``category``/
``compliance``）后由 LangGraph 自动 shallow-merge,无需在 ``aggregate`` 节点
二次重读。StateGraph 编译时会校验 reducer 行为,本模块 M5.4 落地。
"""

from typing import Annotated, Any, NotRequired, TypedDict


def _merge_audit_dicts(
    existing: dict[str, list[dict]] | None,
    update: dict[str, list[dict]] | None,
) -> dict[str, list[dict]]:
    """``audit_results`` 自定义 reducer:shallow-merge 嵌套 dict。

    LangGraph ``Send`` API 并行调度 5 个审核节点时,每个节点返回
    ``{"audit_results": {<自身维度>: [...]}}``;本 reducer 保证不同
    维度子键的写入按 dict.update 语义合并,避免 LastValue channel
    「single value per step」冲突。

    任一参数为 ``None`` 时视为 ``{}``。
    """
    base: dict[str, list[dict]] = dict(existing or {})
    if update:
        base.update(update)
    return base


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
    audit_results: NotRequired[Annotated[dict[str, list[dict]], _merge_audit_dicts]]
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