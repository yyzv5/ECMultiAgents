"""Listing 上架助手接口: POST /v1/listing/audit + POST /v1/listing/audit/{task_id}/resume。

设计要点:
    - **直调子 Graph** —— Listing 是单意图端点,不经过编排层(M6.1),
      直接 ``Depends(get_listing_graph)`` 注入 Listing Graph(M5.4 + M1.3)。
      与 M7.4 ``/chat``(编排层)和 M7.6 ``/data/analyze``(单子 Graph)对比。
    - **鉴权** —— ``Depends(get_current_user)`` 注入 user_id 字符串,
      失败自动抛 401(与 M2.3 ``security.verify_token`` 一致)。
    - **task_id = thread_id** —— API 层在 ``audit`` 端点自己生成 UUID 当
      ``configurable.thread_id``;``resume`` 端点的 path 参数 ``{task_id}``
      直接作为 thread_id。LangGraph ``SqliteSaver`` 按 thread_id 索引,
      1 task 1 thread 互不干扰(Q1 决策)。
    - **GraphInterrupt 兜底** —— ``human_review`` 节点抛 ``interrupt()``
      触发 :class:`langgraph.errors.GraphInterrupt`,不是错误而是 HitL 预期行为:
      - ``audit`` 端点 → 200 + ``status="pending_human_review"``
      - ``resume`` 端点(modify 后再次中断)→ 200 + ``status="pending_human_review"``
      payload 从 ``GraphInterrupt.args[0][0].value`` 读出 task_id / issues。
    - **真实异常兜底** —— 其他 Exception → 500 + 中文泛化提示,
      与 M7.4 / M7.6 风格一致;``from None`` 切断异常链不暴露 LLM/SQL 原文。
    - **task_id 不存在 / 已完成** —— ``resume`` 端点兜底 ``KeyError`` /
      ``ValueError`` → 404 + 中文提示(Q4 决策)。

LangGraph 0.6.x 关键差异:
    - ``GraphInterrupt`` 在 ``langgraph.errors``(不是 ``langgraph.types``)。
    - ``Command`` 在 ``langgraph.types``,``graph.invoke(Command(resume=...))``
      是标准恢复形式(M5.4 ``human_review_node`` 配套使用)。
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from langgraph.errors import GraphInterrupt
from langgraph.types import Command

from backend.api.deps import get_listing_graph
from backend.core.security import get_current_user
from backend.models.schemas import (
    APIResponse,
    AuditIssue,
    ListingAuditRequest,
    ListingAuditResponseData,
    ResumeRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# =========================================================================
# 辅助函数
# =========================================================================


def _extract_interrupt_payload(exc: GraphInterrupt) -> dict:
    """从 GraphInterrupt 异常的 args[0][0].value 取出原始 payload。

    LangGraph 0.6.x 中,GraphInterrupt 的 args[0] 是一个由一个或多个
    :class:`langgraph.types.Interrupt` 组成的序列,每个 Interrupt 有
    ``value``(原始传给 interrupt() 的对象)和 ``id``。

    当 graph 在 ``human_review`` 节点抛 ``interrupt({"task_id","issues",...})``
    时,value 就是这个 dict。异常形态异常时返回空 dict 兜底。
    """
    try:
        interrupts = exc.args[0]
        if interrupts:
            first = interrupts[0]
            value = getattr(first, "value", None)
            if isinstance(value, dict):
                return value
    except (IndexError, AttributeError, TypeError):
        logger.warning("listing: GraphInterrupt payload 解析失败", exc_info=True)
    return {}


def _payload_to_issues(payload: dict) -> list[AuditIssue]:
    """把 payload 里的 issues list[dict] 转换成 Pydantic ``AuditIssue`` 列表。

    字段不完整时填空串,容错 LLM 返回的脏数据。
    """
    raw = payload.get("issues") or []
    if not isinstance(raw, list):
        return []
    issues: list[AuditIssue] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        issues.append(
            AuditIssue(
                field=str(item.get("field", "")),
                rule=str(item.get("rule", "")),
                detail=str(item.get("detail", "")),
                suggestion=str(item.get("suggestion", "")),
            )
        )
    return issues


# =========================================================================
# 端点
# =========================================================================


@router.post("/audit")
def audit(
    body: ListingAuditRequest,
    graph=Depends(get_listing_graph),
    user_id: str = Depends(get_current_user),  # noqa: ARG001 — 鉴权用,业务层不消费
) -> APIResponse[ListingAuditResponseData]:
    """启动 Listing 审核;可能跑完也可能触发 ``pending_human_review`` 中断。

    流程: 鉴权 → API 层生成 task_id(UUID)作为 thread_id →
    ``graph.invoke(initial_state, config={"configurable":{"thread_id":task_id}})`` →
    - 完整跑完 → ``status="approved"`` / ``"needs_revision"``
    - 触发中断 → ``status="pending_human_review"`` + payload.issues

    Args:
        body:    含 ``platform`` / ``title`` / ``image_urls`` / ``category`` /
                 ``variations`` / ``attributes`` 的请求体(M4.2)。
        graph:   Listing Agent 编译后的 StateGraph(M5.4 + M1.3 注入)。
        user_id: 来自 JWT 鉴权的用户标识;仅用于通过 Depends 触发鉴权。

    Returns:
        ``APIResponse[ListingAuditResponseData]``: data 含 status / task_id / issues。

    Raises:
        HTTPException: 401 鉴权失败;500 Listing Graph 调用失败。
    """
    # API 层自己生成 task_id,既当 thread_id,也当响应里的 task_id(Q1 决策)。
    task_id = str(uuid.uuid4())
    logger.info(
        "listing.audit: user_id=%s task_id=%s platform=%s",
        user_id, task_id, body.platform,
    )

    initial_state: dict = {
        "task_id": task_id,
        "platform": body.platform,
        "title": body.title,
        "image_urls": body.image_urls,
        "category": body.category,
        "variations": [v.model_dump() for v in body.variations],
        "attributes": body.attributes,
    }

    try:
        state = graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": task_id}},
        )
    except GraphInterrupt as exc:
        # human_review 中断 —— 取出 payload 中的 task_id / issues。
        payload = _extract_interrupt_payload(exc)
        payload_task_id = payload.get("task_id") or task_id
        logger.info(
            "listing.audit: GraphInterrupt task_id=%s issues=%d",
            payload_task_id, len(payload.get("issues") or []),
        )
        return APIResponse(
            data=ListingAuditResponseData(
                status="pending_human_review",
                task_id=payload_task_id,
                issues=_payload_to_issues(payload),
            )
        )
    except Exception:
        logger.exception(
            "listing.audit: graph.invoke 失败 task_id=%s", task_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Listing 审核服务调用失败,请稍后重试",
        ) from None

    # 完整跑完 —— 走 do_listing 路径或 auto_fix 后落地,passed 标志判定结果。
    passed = bool(state.get("passed"))
    issues_raw = state.get("all_issues") or []
    issues = [
        AuditIssue(
            field=str(i.get("field", "")),
            rule=str(i.get("rule", "")),
            detail=str(i.get("detail", "")),
            suggestion=str(i.get("suggestion", "")),
        )
        for i in issues_raw
        if isinstance(i, dict)
    ]
    return APIResponse(
        data=ListingAuditResponseData(
            status="approved" if passed else "needs_revision",
            task_id=state.get("task_id") or task_id,
            issues=issues,
        )
    )


@router.post("/audit/{task_id}/resume")
def resume(
    task_id: str,
    body: ResumeRequest,
    graph=Depends(get_listing_graph),
    user_id: str = Depends(get_current_user),  # noqa: ARG001 — 鉴权用,业务层不消费
) -> APIResponse[ListingAuditResponseData]:
    """用 ``Command(resume=...)`` 恢复指定 task_id 的 Listing 审核。

    流程: 鉴权 → ``graph.invoke(Command(resume={decision, feedback}),
    config={"configurable":{"thread_id":task_id}})`` →
    - 跑完 → status 映射:approve→approved,reject→rejected,modify→needs_revision
    - 再次中断(modify → auto_fix → 又出问题)→ ``pending_human_review``
    - task_id 不存在 / 已完成 → KeyError / ValueError → 404(Q4 决策)

    Args:
        task_id: path 参数,作为 LangGraph thread_id;必须与 audit 端点
                 生成的 UUID 一致才能定位到 checkpointer 中的中断快照。
        body:    ``ResumeRequest``: ``human_decision``(approve/modify/reject) +
                 可选 ``human_feedback``(M4.2 ``extra="forbid"``)。
        graph:   Listing Graph(M5.4 + M1.3 注入)。
        user_id: 来自 JWT 鉴权的用户标识。

    Returns:
        ``APIResponse[ListingAuditResponseData]``。

    Raises:
        HTTPException: 401 鉴权失败;404 task_id 缺失;500 Graph 调用失败。
    """
    feedback = body.human_feedback or ""
    logger.info(
        "listing.resume: user_id=%s task_id=%s decision=%s",
        user_id, task_id, body.human_decision,
    )

    try:
        state = graph.invoke(
            Command(
                resume={
                    "human_decision": body.human_decision,
                    "human_feedback": feedback,
                },
            ),
            config={"configurable": {"thread_id": task_id}},
        )
    except GraphInterrupt as exc:
        # modify → auto_fix → 再次触发人工审核。
        payload = _extract_interrupt_payload(exc)
        return APIResponse(
            data=ListingAuditResponseData(
                status="pending_human_review",
                task_id=payload.get("task_id") or task_id,
                issues=_payload_to_issues(payload),
            )
        )
    except (KeyError, ValueError):
        # task_id 不存在(checkpointer 找不到)或已完成(快照被消费)。
        logger.warning(
            "listing.resume: task_id=%s 不存在或已完成", task_id,
        )
        raise HTTPException(
            status_code=404,
            detail=f"task_id {task_id} 不存在或已完成",
        ) from None
    except Exception:
        logger.exception(
            "listing.resume: graph.invoke 失败 task_id=%s", task_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Listing 审核恢复服务调用失败,请稍后重试",
        ) from None

    # 恢复后跑完 —— 按 human_decision 映射 status(Q6 决策 + plan §验收标准)。
    decision = body.human_decision
    if decision == "approve":
        status = "approved"
    elif decision == "modify":
        # modify 后 auto_fix 落地 → passed=False;语义上是"已修订待复审"。
        status = "needs_revision"
    else:
        # reject 或任意非 approve/modify → END;语义上"已驳回"。
        status = "rejected"

    issues_raw = state.get("all_issues") or []
    issues = [
        AuditIssue(
            field=str(i.get("field", "")),
            rule=str(i.get("rule", "")),
            detail=str(i.get("detail", "")),
            suggestion=str(i.get("suggestion", "")),
        )
        for i in issues_raw
        if isinstance(i, dict)
    ]
    return APIResponse(
        data=ListingAuditResponseData(
            status=status,
            task_id=task_id,
            issues=issues,
        )
    )


__all__ = ["router"]