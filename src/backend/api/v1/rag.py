"""Chat 统一对话接口: POST /v1/chat。

设计要点:
    - **注入编排层** —— 端点接受任意 query,由编排层(M6.1)先做意图识别
      再路由到 RAG / Data 子 Agent。这是与 M7.6 ``/data/analyze`` 的根本
      区别:``/data/analyze`` 语义单一(直调 Data Graph),``/chat`` 语义开放
      (需先 classify_intent → 分流)。详见 ``docs/spec/TechSPEC.md`` §6.3。
    - **不直调子 Agent** —— ``Depends(get_orchestrator)`` 注入父图,
      子 Agent 调用被封装在编排层 ``call_rag_agent`` / ``call_data_agent`` 中。
    - **鉴权** —— ``Depends(get_current_user)`` 注入 user_id 字符串,
      失败自动抛 401(与 M2.3 ``security.verify_token`` 一致)。
    - **统一响应** —— ``agent_result`` 字段映射按 intent 区分:
        - ``rag``:``answer`` / ``sources`` / ``confidence`` / ``rejected``
        - ``data``:``report`` → ``answer``(Data Agent 无独立 report 字段,
          合并到 answer 简化前端展示)。
    - **异常兜底** —— 编排 Graph ``invoke()`` 本身抛异常(非子 Agent 异常,
      子 Agent 已被编排层 try/except 包装)→ 500 + 中文泛化提示,
      不向客户端泄露 LLM/SQL 原文错误。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_orchestrator
from backend.core.security import get_current_user
from backend.models.schemas import APIResponse, ChatRequest, ChatResponseData

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat")
def chat(
    body: ChatRequest,
    graph=Depends(get_orchestrator),
    user_id: str = Depends(get_current_user),  # noqa: ARG001 — 鉴权用,业务层不消费
) -> APIResponse[ChatResponseData]:
    """统一对话接口: 编排层意图识别 → RAG / Data 子 Agent → 格式化返回。

    流程: 鉴权 → graph.invoke({"query","session_id"}) →
    从 ``agent_result`` 读取 ``intent`` 按分支映射到 ``ChatResponseData``。

    Args:
        body:    含 ``query`` / ``session_id`` 的请求体。
        graph:   编排层父图(M6.1 + M1.3 注入);其内部已完成
                 ``classify_intent`` → ``call_*_agent`` → ``format_result`` 链路。
        user_id: 来自 JWT 鉴权的用户标识;仅用于通过 Depends 触发鉴权,
                 业务流不消费。

    Returns:
        ``APIResponse[ChatResponseData]``: data 含 intent / answer / sources /
        confidence / rejected。

    Raises:
        HTTPException: 401 鉴权失败(由 ``get_current_user`` 抛);
            500 编排 Graph 内部调用失败(API 层兜底,不暴露原文)。
    """
    logger.info(
        "rag.chat: session_id=%s user_id=%s query=%r",
        body.session_id,
        user_id,
        body.query[:50],
    )

    try:
        result = graph.invoke(
            {"query": body.query, "session_id": body.session_id, "messages": []},
        )
    except Exception:
        logger.exception(
            "rag.chat: graph.invoke 失败 session_id=%s",
            body.session_id,
        )
        raise HTTPException(
            status_code=500,
            detail="对话服务调用失败,请稍后重试",
        ) from None

    agent_result = result.get("agent_result") or {}
    intent = agent_result.get("intent", "rag")

    if intent == "data":
        # Data 路径:report → answer;其余字段对齐 ChatResponseData 缺省值。
        return APIResponse(
            data=ChatResponseData(
                intent="data",
                answer=agent_result.get("report", ""),
                sources=None,
                confidence=None,
                rejected=False,
            )
        )

    # rag 路径(默认):answer / sources / confidence / rejected 全量映射。
    # sources 空列表统一为 None(对齐 M7.6 ``or None`` 语义)。
    return APIResponse(
        data=ChatResponseData(
            intent="rag",
            answer=agent_result.get("answer", ""),
            sources=agent_result.get("sources") or None,
            confidence=agent_result.get("confidence"),
            rejected=agent_result.get("rejected", False),
        )
    )


__all__ = ["router"]
