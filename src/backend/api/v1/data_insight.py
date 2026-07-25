"""Data Insight 数据分析接口: POST /v1/data/analyze。

设计要点:
    - **不走编排层** —— 端点语义单一（"data intent"），直接调 Data Graph，
      避免双重 dispatch（编排层会再 ``call_data_agent`` 间接路由）。
      详见 ``docs/spec/TechSPEC.md`` §6.3 与 M7.6 plan Q1 决策。
    - **不依赖编排层** —— 注入 ``get_data_graph()(M1.3 懒加载 + @lru_cache)``。
    - **鉴权** —— ``Depends(get_current_user)`` 注入 user_id 字符串，
      失败自动抛 401（与 M2.3 ``security.verify_token`` 一致）。
    - **thread_id 隔离** —— ``f"{session_id}_data"`` 与 M6.1 编排层约定一致，
      同一 session_id 可同时走 /chat(编排层) 与 /data/analyze(本端点) 而不串扰。
    - **异常兜底** —— 所有 graph 调用失败 → 500 + 中文泛化提示，
      不向客户端泄露 LLM/SQL 原文错误（Data Graph 节点级 try/except 之后第二层保险）。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_data_graph
from backend.core.security import get_current_user
from backend.models.schemas import APIResponse, DataAnalyzeRequest, DataResponseData

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/analyze")
def analyze(
    body: DataAnalyzeRequest,
    graph=Depends(get_data_graph),
    user_id: str = Depends(get_current_user),  # noqa: ARG001 — 鉴权用,业务层不消费
) -> APIResponse[DataResponseData]:
    """执行数据分析并返回报告。

    流程: 鉴权 → graph.invoke({"query","messages"}) →
    提取 ``analysis_type`` / ``report`` / ``generated_sql`` → 包装为 ``DataResponseData``。

    Args:
        body:    含 ``query`` / ``session_id`` 的请求体。
        graph:   Data Agent 编译后的 StateGraph(M5.6 + M1.3 注入)。
        user_id: 来自 JWT 鉴权的用户标识;仅用于通过 Depends 触发鉴权,
                 业务流不消费。

    Returns:
        ``APIResponse[DataResponseData]``: data 含 analysis_type / report / sql_used。

    Raises:
        HTTPException: 401 鉴权失败(由 ``get_current_user`` 抛);
            500 Data Graph 内部调用失败(API 层兜底,不暴露原文)。
    """
    logger.info(
        "data_insight.analyze: session_id=%s user_id=%s query=%r",
        body.session_id,
        user_id,
        body.query[:50],
    )

    try:
        result = graph.invoke(
            {"query": body.query, "messages": []},
            config={"configurable": {"thread_id": f"{body.session_id}_data"}},
        )
    except Exception:
        logger.exception(
            "data_insight.analyze: graph.invoke 失败 session_id=%s",
            body.session_id,
        )
        raise HTTPException(
            status_code=500,
            detail="数据分析服务调用失败,请稍后重试",
        ) from None

    return APIResponse(
        data=DataResponseData(
            analysis_type=result.get("analysis_type", ""),
            report=result.get("report", ""),
            sql_used=result.get("generated_sql") or None,
        )
    )


__all__ = ["router"]
