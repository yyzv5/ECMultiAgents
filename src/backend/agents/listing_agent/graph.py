"""Listing Agent StateGraph — 11 个节点 + 并行审核 + 人机协同中断。

11 个节点:
    1. task_parse (入口)
    2-6. title_check / image_check / variation_check /
        category_check / compliance_check (并行审核)
    7. aggregate (汇总)
    8. decide (判断路由)
    9. auto_fix (自动修复)
    10. do_listing (占位上架)
    11. human_review (HitL 中断)

5 个审核节点通过 LangGraph ``Send`` API 并行调度;``human_review`` 节点
使用 :func:`langgraph.types.interrupt` 实现真正的人机协同中断,
恢复时通过 :class:`langgraph.types.Command` 提供 ``human_decision`` 与
``human_feedback``。

导出编译后的 ``graph`` 对象供 ``api/deps.py`` 的 ``get_listing_graph()``
使用。

M7.7 — Prompt 模板已统一抽出到 prompts/listing_prompts.py。
"""

import json
import logging
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.types import Send, interrupt

from backend.agents.listing_agent.state import ListingState
from backend.config import settings
from backend.core.llm_factory import create_llm
from backend.prompts.listing_prompts import (
    AUTO_FIX_PROMPT,
    CATEGORY_CHECK_PROMPT,
    COMPLIANCE_CHECK_PROMPT,
    IMAGE_CHECK_PROMPT,
    PLATFORM_RULES,
    TITLE_CHECK_PROMPT,
    VARIATION_CHECK_PROMPT,
)

logger = logging.getLogger(__name__)


# =========================================================================
# 辅助函数
# =========================================================================


_ISSUE_FIELDS = ("field", "rule", "detail", "suggestion")
"""AuditIssue 内层 dict 必须包含的字段,与 M4.2 Pydantic 模型对齐。"""


def _parse_audit_json(raw: str) -> list[dict[str, str]]:
    """解析 LLM 返回的 JSON 数组,容错 markdown 代码块与非法 JSON。

    返回 list[dict] —— 每个 dict 至少包含 ``_issue_fields`` 中的字段;
    解析失败或空响应时返回 ``[]``。
    """
    if not raw:
        return []

    text = raw.strip()

    # 1) 去掉 markdown 代码块包裹 ```json ... ```
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # 2) 找到第一个 [ 与最后一个 ],取中间的 JSON 数组
    lb = text.find("[")
    rb = text.rfind("]")
    if lb == -1 or rb == -1 or rb <= lb:
        logger.warning("_parse_audit_json: 未找到 JSON 数组边界,返回空 list")
        return []
    candidate = text[lb:rb + 1]

    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        logger.warning("_parse_audit_json: JSON 解析失败,返回空 list")
        return []

    if not isinstance(data, list):
        logger.warning("_parse_audit_json: 顶层不是 list,返回空 list")
        return []

    # 3) 过滤与规范化:每个元素必须是 dict,缺失字段填空串
    normalized: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        normalized.append({
            f: str(item.get(f, "")) for f in _ISSUE_FIELDS
        })
    return normalized


def _call_audit_llm(prompt: str) -> list[dict[str, str]]:
    """调用 LLM 执行审核 Prompt,返回标准化后的 issue 列表。

    LLM 调用失败时返回 ``[]`` 而非抛错,保证 graph 不会因单维度失败而中断。
    """
    try:
        llm = create_llm()
        response = llm.invoke(prompt)
        raw = (
            response.content
            if isinstance(response.content, str)
            else str(response.content)
        )
    except Exception:
        logger.exception("_call_audit_llm: LLM 调用失败,返回空 issues")
        return []
    return _parse_audit_json(raw)


def _call_fix_llm(prompt: str, fallback: str) -> str:
    """调用 LLM 生成修复后的标题;失败时回退到 ``fallback``。"""
    try:
        llm = create_llm()
        response = llm.invoke(prompt)
        text = (
            response.content.strip()
            if isinstance(response.content, str)
            else str(response.content).strip()
        )
        return text or fallback
    except Exception:
        logger.exception("_call_fix_llm: LLM 调用失败,回退原标题")
        return fallback


def _platform_rules_text(platform: str) -> str:
    """返回平台规则片段,未知平台返回通用兜底规则。"""
    return PLATFORM_RULES.get(
        platform,
        "通用规则: 标题合规、不使用违禁词、类目匹配、变体真实、图片可访问。",
    )


def _dict_to_str(obj: Any, max_len: int = 2000) -> str:
    """将 dict / list 转为 JSON 字符串供 Prompt 使用;过长时截断。"""
    try:
        text = json.dumps(obj, ensure_ascii=False)
    except (TypeError, ValueError):
        text = str(obj)
    if len(text) > max_len:
        text = text[:max_len] + "...(truncated)"
    return text


# =========================================================================
# 节点函数
# =========================================================================


def task_parse_node(state: ListingState) -> dict:
    """入口节点 —— 生成 UUID task_id 并初始化 audit_results 空 dict。"""
    task_id = str(uuid.uuid4())
    logger.info("task_parse: 生成 task_id=%s, platform=%s", task_id, state.get("platform"))
    return {"task_id": task_id, "audit_results": {}}


def title_check_node(state: ListingState) -> dict:
    """标题审核 —— LLM 校验字符限制/关键词禁忌/平台规范。"""
    platform = state.get("platform", "")
    title = state.get("title", "")
    category = state.get("category", "")
    attributes = state.get("attributes", {})
    prompt = TITLE_CHECK_PROMPT.format(
        platform_rules=_platform_rules_text(platform),
        title=title,
        category=category,
        attributes=_dict_to_str(attributes),
    )
    issues = _call_audit_llm(prompt)
    logger.info("title_check: %d issues", len(issues))
    return {"audit_results": {"title": issues}}


def image_check_node(state: ListingState) -> dict:
    """图片审核 —— LLM 校验图片数量/可访问性/合规。"""
    platform = state.get("platform", "")
    image_urls = state.get("image_urls", [])
    prompt = IMAGE_CHECK_PROMPT.format(
        platform_rules=_platform_rules_text(platform),
        image_count=len(image_urls),
        image_urls=_dict_to_str(image_urls),
    )
    issues = _call_audit_llm(prompt)
    logger.info("image_check: %d issues", len(issues))
    return {"audit_results": {"image": issues}}


def variation_check_node(state: ListingState) -> dict:
    """变体审核 —— LLM 校验变体完整性/属性合理性。"""
    platform = state.get("platform", "")
    variations = state.get("variations", [])
    prompt = VARIATION_CHECK_PROMPT.format(
        platform_rules=_platform_rules_text(platform),
        variation_count=len(variations),
        variations=_dict_to_str(variations),
    )
    issues = _call_audit_llm(prompt)
    logger.info("variation_check: %d issues", len(issues))
    return {"audit_results": {"variation": issues}}


def category_check_node(state: ListingState) -> dict:
    """类目审核 —— LLM 校验类目与商品匹配/平台类目树。"""
    platform = state.get("platform", "")
    title = state.get("title", "")
    category = state.get("category", "")
    attributes = state.get("attributes", {})
    prompt = CATEGORY_CHECK_PROMPT.format(
        platform_rules=_platform_rules_text(platform),
        title=title,
        category=category,
        attributes=_dict_to_str(attributes),
    )
    issues = _call_audit_llm(prompt)
    logger.info("category_check: %d issues", len(issues))
    return {"audit_results": {"category": issues}}


def compliance_check_node(state: ListingState) -> dict:
    """合规审核 —— LLM 校验违禁词/知识产权/当地法规。"""
    platform = state.get("platform", "")
    title = state.get("title", "")
    category = state.get("category", "")
    attributes = state.get("attributes", {})
    prompt = COMPLIANCE_CHECK_PROMPT.format(
        platform_rules=_platform_rules_text(platform),
        title=title,
        category=category,
        attributes=_dict_to_str(attributes),
    )
    issues = _call_audit_llm(prompt)
    logger.info("compliance_check: %d issues", len(issues))
    return {"audit_results": {"compliance": issues}}


def aggregate_node(state: ListingState) -> dict:
    """汇总节点 —— 把 5 个审核维度的结果扁平化为 ``all_issues``。"""
    audit_results = state.get("audit_results", {}) or {}
    all_issues: list[dict[str, str]] = []
    for dim_issues in audit_results.values():
        if isinstance(dim_issues, list):
            all_issues.extend(dim_issues)
    logger.info("aggregate: total %d issues across %d dims", len(all_issues), len(audit_results))
    return {"all_issues": all_issues}


def decide_node(state: ListingState) -> dict:
    """决策节点 —— 根据 ``all_issues`` 计算 ``passed`` / ``need_human_review``。

    简单规则:
        - 无问题 → passed=True
        - 含 compliance 维度问题 或 问题总数 > 3 → need_human_review=True
        - 其他 → passed=False, need_human_review=False(可自动修复)
    """
    issues = state.get("all_issues", []) or []
    passed = len(issues) == 0
    has_compliance = any(
        str(i.get("field", "")).startswith("compliance") for i in issues
    )
    need_human = has_compliance or len(issues) > 3
    logger.info(
        "decide: passed=%s, need_human=%s, issue_count=%d",
        passed, need_human, len(issues),
    )
    return {"passed": passed, "need_human_review": need_human}


def auto_fix_node(state: ListingState) -> dict:
    """自动修复节点 —— LLM 尝试修复可自动修复问题,写入 ``fixed_content.title``。"""
    title = state.get("title", "")
    issues = state.get("all_issues", []) or []
    human_note = state.get("human_feedback", "") or "无"
    prompt = AUTO_FIX_PROMPT.format(
        feedback=human_note,
        issues=_dict_to_str(issues),
        title=title,
    )
    fixed_title = _call_fix_llm(prompt, fallback=title)
    logger.info("auto_fix: title=%r -> fixed=%r", title, fixed_title)
    return {"fixed_content": {"title": fixed_title}}


def do_listing_node(state: ListingState) -> dict:
    """占位上架节点 —— 模拟上架,生产环境由 M7.5 接入真实 Listing API。

    优先使用 ``fixed_content.title`` 替换原始 ``title`` 作为最终上架标题。
    """
    fixed = state.get("fixed_content") or {}
    final_title = fixed.get("title") or state.get("title", "")
    logger.info(
        "do_listing: task_id=%s, final_title=%r",
        state.get("task_id"), final_title,
    )
    return {"fixed_content": {**(state.get("fixed_content") or {}), "title": final_title}}


def human_review_node(state: ListingState) -> dict:
    """人机协同中断节点 —— 调用 :func:`interrupt` 暂停 graph。

    恢复时接收 ``Command(resume={"human_decision": ..., "human_feedback": ...})``,
    决策值会被写入 state 供 ``route_after_human_review`` 使用。
    """
    issues = state.get("all_issues", []) or []
    interrupt_payload = {
        "task_id": state.get("task_id"),
        "issues": issues,
        "message": "需要人工审核",
    }
    feedback = interrupt(interrupt_payload)
    if not isinstance(feedback, dict):
        logger.warning("human_review: 恢复反馈非 dict, 视为 reject")
        feedback = {"human_decision": "reject", "human_feedback": ""}

    decision = str(feedback.get("human_decision", "reject"))
    note = str(feedback.get("human_feedback", "") or "")
    logger.info("human_review: decision=%s, feedback=%r", decision, note)
    return {"human_decision": decision, "human_feedback": note}


# =========================================================================
# 条件路由函数
# =========================================================================


def fan_out_audits(state: ListingState) -> list[Send]:
    """``task_parse`` 后扇出 5 个并行审核节点。

    使用 LangGraph :class:`Send` API,5 个 Send 各自独立调用 LLM,
    最终汇聚到 ``aggregate``。
    """
    return [
        Send("title_check", dict(state)),
        Send("image_check", dict(state)),
        Send("variation_check", dict(state)),
        Send("category_check", dict(state)),
        Send("compliance_check", dict(state)),
    ]


def route_after_decide(state: ListingState) -> str:
    """``decide`` 后路由。

    - passed → ``do_listing``
    - need_human_review → ``human_review``
    - 其他(可自动修复)→ ``auto_fix``
    """
    if state.get("passed"):
        return "do_listing"
    if state.get("need_human_review"):
        return "human_review"
    return "auto_fix"


def route_after_human_review(state: ListingState) -> str:
    """``human_review`` 恢复后路由。

    - approve → ``do_listing``
    - modify → ``auto_fix``
    - reject → :data:`END`
    """
    decision = state.get("human_decision")
    if decision == "approve":
        return "do_listing"
    if decision == "modify":
        return "auto_fix"
    return END


# =========================================================================
# Checkpointer
# =========================================================================


def _create_checkpointer() -> SqliteSaver:
    """创建 SQLite 持久化的 MemorySaver。

    ``human_review`` 节点触发 :func:`interrupt` 时 LangGraph 需要 checkpointer
    保存中断状态以便恢复,**必须**绑定。
    """
    db_path = Path(settings.CHECKPOINT_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    return SqliteSaver(conn)


# =========================================================================
# Graph 构建与编译
# =========================================================================


def _build_graph() -> StateGraph:
    """构建 Listing Agent 的 StateGraph(不编译)。"""
    builder = StateGraph(ListingState)

    # 注册 11 个节点
    builder.add_node("task_parse", task_parse_node)
    builder.add_node("title_check", title_check_node)
    builder.add_node("image_check", image_check_node)
    builder.add_node("variation_check", variation_check_node)
    builder.add_node("category_check", category_check_node)
    builder.add_node("compliance_check", compliance_check_node)
    builder.add_node("aggregate", aggregate_node)
    builder.add_node("decide", decide_node)
    builder.add_node("auto_fix", auto_fix_node)
    builder.add_node("do_listing", do_listing_node)
    builder.add_node("human_review", human_review_node)

    # START -> task_parse
    builder.set_entry_point("task_parse")

    # task_parse -> (并行 5 路 Send)
    builder.add_conditional_edges(
        "task_parse",
        fan_out_audits,
        [
            "title_check",
            "image_check",
            "variation_check",
            "category_check",
            "compliance_check",
        ],
    )

    # 5 个审核节点 -> aggregate
    for audit_name in (
        "title_check",
        "image_check",
        "variation_check",
        "category_check",
        "compliance_check",
    ):
        builder.add_edge(audit_name, "aggregate")

    # aggregate -> decide
    builder.add_edge("aggregate", "decide")

    # decide -> (passed -> do_listing | need_human -> human_review | auto_fix)
    builder.add_conditional_edges(
        "decide",
        route_after_decide,
        ["do_listing", "human_review", "auto_fix"],
    )

    # auto_fix -> do_listing
    builder.add_edge("auto_fix", "do_listing")

    # human_review -> (approve -> do_listing | modify -> auto_fix | reject -> END)
    builder.add_conditional_edges(
        "human_review",
        route_after_human_review,
        ["do_listing", "auto_fix", END],
    )

    # do_listing -> END
    builder.add_edge("do_listing", END)

    return builder


# 模块级:编译 graph 对象(供 deps.py import)
try:
    _checkpointer = _create_checkpointer()
    _builder = _build_graph()
    graph = _builder.compile(checkpointer=_checkpointer)
    logger.info(
        "Listing Agent StateGraph 编译成功,checkpointer 绑定: %s",
        settings.CHECKPOINT_DB_PATH,
    )
except Exception:
    logger.exception("Listing Agent StateGraph 编译失败")
    raise


__all__ = ["graph"]