"""LLM 工厂: 统一管理 LLM 实例的创建。

使用 :class:`langchain_openai.ChatOpenAI` 包装 DeepSeek 和 MiniMax 两个提供商。
所有 API 地址、密钥、模型名从 :mod:`backend.config` 读取，不硬编码。
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from backend.config import settings

_TEMPERATURE = 0.7

_MODEL_ATTR: dict[str, str] = {
    "deepseek": "DEEPSEEK_MODEL",
    "minimax": "MINIMAX_MODEL",
}

_URL_ATTR: dict[str, str] = {
    "deepseek": "DEEPSEEK_BASE_URL",
    "minimax": "MINIMAX_BASE_URL",
}

_KEY_ATTR: dict[str, str] = {
    "deepseek": "DEEPSEEK_API_KEY",
    "minimax": "MINIMAX_API_KEY",
}

# ``thinking_mode=True`` 时传递给 ChatOpenAI 的 ``extra_body``。
# 统一使用 OpenAI 兼容接口的思考模式参数。
_THINKING_EXTRA = {"thinking": {"type": "enabled"}}


def create_llm(
    model: str | None = None,
    thinking_mode: bool = False,
) -> ChatOpenAI:
    """创建并返回 ``ChatOpenAI`` 实例。

    Args:
        model: 提供商标识，``"deepseek"`` 或 ``"minimax"``。
               不传则使用 ``settings.DEFAULT_LLM``。
        thinking_mode: 是否启用「思考模式」。默认 ``False``。
                       ``True`` 时向 ``extra_body`` 传递 ``{"thinking": {"type": "enabled"}}``。
                       所有提供商共用统一的 OpenAI 兼容接口。

    Returns:
        配置好的 ``ChatOpenAI`` 实例。

    Raises:
        ValueError: 不支持的 ``model`` 值。
    """
    if model is None:
        model = settings.DEFAULT_LLM

    if model not in _MODEL_ATTR:
        msg = f"Unsupported model: '{model}'. Supported: {list(_MODEL_ATTR)}"
        raise ValueError(msg)

    model_name = getattr(settings, _MODEL_ATTR[model])
    base_url = getattr(settings, _URL_ATTR[model])
    api_key = getattr(settings, _KEY_ATTR[model]).get_secret_value()

    kwargs: dict = {
        "model": model_name,
        "openai_api_base": base_url,
        "openai_api_key": api_key,
        "temperature": _TEMPERATURE,
        "timeout": settings.LLM_TIMEOUT,
    }

    if thinking_mode:
        kwargs["extra_body"] = _THINKING_EXTRA

    return ChatOpenAI(**kwargs)
