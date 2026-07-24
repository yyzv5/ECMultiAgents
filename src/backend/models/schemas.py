"""Pydantic 请求/响应模型定义。

按 API 模块分组：Auth / Chat / Listing / Data。
所有响应模型通过 ``APIResponse[T]`` 泛型包装 ``code`` + ``data`` 结构。
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ── 泛型响应包装器 ──────────────────────────────────────────────


class APIResponse(BaseModel, Generic[T]):
    """泛型统一响应体。

    Attributes:
        code: 业务状态码，0 表示成功。
        data: 响应数据，类型由子类型参数决定。
    """

    code: int = Field(0, description="业务状态码，0 表示成功")
    data: T | None = Field(None, description="响应数据")


# ── Auth ────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    """POST /v1/auth/register 请求体。"""

    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class LoginRequest(BaseModel):
    """POST /v1/auth/login 请求体。"""

    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
    """登录成功返回的 JWT Token 信息。"""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token 类型")


# ── Chat ────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    """POST /v1/chat 请求体。"""

    query: str = Field(..., description="用户输入")
    session_id: str = Field(..., description="会话标识（UUID）")


class ChatResponseData(BaseModel):
    """POST /v1/chat 响应 data 部分。"""

    intent: str = Field(..., description="意图分类（rag / listing / data）")
    answer: str = Field(..., description="回答文本")
    sources: list[str] | None = Field(None, description="引用来源列表")
    confidence: float | None = Field(None, description="检索置信度", ge=0.0, le=1.0)
    rejected: bool = Field(False, description="是否拒绝回答")


# ── Listing ─────────────────────────────────────────────────────


class Variation(BaseModel):
    """商品变体属性键值对。

    不同商品变体的属性键不同（如 color / size），通过 ``extra`` 模式支持动态字段。
    """

    model_config = {"extra": "allow"}


class ListingAuditRequest(BaseModel):
    """POST /v1/listing/audit 请求体。"""

    platform: str = Field(
        ..., description="目标平台（Amazon / Shopee / AliExpress）"
    )
    title: str = Field(..., description="商品标题")
    image_urls: list[str] = Field(..., description="图片链接列表")
    variations: list[Variation] = Field(
        default_factory=list, description="变体信息列表"
    )
    category: str = Field(..., description="商品类目")
    attributes: dict[str, str] = Field(
        default_factory=dict, description="商品属性键值对"
    )


class AuditIssue(BaseModel):
    """审核问题描述。"""

    field: str = Field(..., description="问题字段名")
    rule: str = Field(..., description="违反的规则名")
    detail: str = Field(..., description="违规详情说明")
    suggestion: str = Field(..., description="修改建议")


class ListingAuditResponseData(BaseModel):
    """POST /v1/listing/audit 响应 data 部分。"""

    status: str = Field(..., description="审核状态")
    task_id: str = Field(..., description="审核任务 ID（UUID）")
    issues: list[AuditIssue] = Field(
        default_factory=list, description="审核问题列表"
    )


class ResumeRequest(BaseModel):
    """POST /v1/listing/audit/{task_id}/resume 请求体。"""

    model_config = {"extra": "forbid"}

    human_decision: str = Field(
        ..., description="人工决定（approve / reject / modify）"
    )
    human_feedback: str | None = Field(None, description="人工反馈说明")


# ── Data ────────────────────────────────────────────────────────


class DataAnalyzeRequest(BaseModel):
    """POST /v1/data/analyze 请求体。"""

    query: str = Field(..., description="用户分析需求")
    session_id: str = Field(..., description="会话标识（UUID）")


class DataResponseData(BaseModel):
    """POST /v1/data/analyze 响应 data 部分。"""

    analysis_type: str = Field(
        ...,
        description="分析类型（weekly_report / monthly_report / free_analysis）",
    )
    report: str = Field(..., description="分析报告文本")
    sql_used: str | None = Field(None, description="生成的 SQL 查询语句")


__all__ = [
    "APIResponse",
    "AuditIssue",
    "ChatRequest",
    "ChatResponseData",
    "DataAnalyzeRequest",
    "DataResponseData",
    "ListingAuditRequest",
    "ListingAuditResponseData",
    "LoginRequest",
    "RegisterRequest",
    "ResumeRequest",
    "TokenResponse",
    "Variation",
]
