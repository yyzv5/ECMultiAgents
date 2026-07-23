"""LLM 工厂单元测试（不联网）。

测试覆盖:
  1. create_llm() 默认使用 DEFAULT_LLM
  2. deepseek 参数正确（model 名从 DEEPSEEK_MODEL 读取）
  3. minimax 参数正确（model 名从 MINIMAX_MODEL 读取）
  4. 未知 model 抛出 ValueError
  5. timeout / temperature 参数传递正确
"""
from __future__ import annotations

import pytest
from langchain_openai import ChatOpenAI

from backend.config import settings


def test_create_llm_defaults_to_deepseek() -> None:
    """不传 model 时使用 DEFAULT_LLM = 'deepseek'。"""
    from backend.core.llm_factory import create_llm

    llm = create_llm()
    assert isinstance(llm, ChatOpenAI)
    assert llm.model_name == settings.DEEPSEEK_MODEL  # type: ignore[union-attr]
    assert settings.DEEPSEEK_BASE_URL in str(llm.openai_api_base)  # type: ignore[union-attr]


def test_create_llm_deepseek_params() -> None:
    """deepseek 的 model/base_url/api_key 从 settings 读取。"""
    from backend.core.llm_factory import create_llm

    llm = create_llm("deepseek")
    assert llm.model_name == settings.DEEPSEEK_MODEL  # type: ignore[union-attr]
    assert llm.openai_api_base == settings.DEEPSEEK_BASE_URL  # type: ignore[union-attr]
    assert llm.openai_api_key.get_secret_value() == settings.DEEPSEEK_API_KEY.get_secret_value()  # type: ignore[union-attr]
    assert llm.temperature == 0.7  # type: ignore[union-attr]


def test_create_llm_minimax_params() -> None:
    """minimax 的 model/base_url/api_key 从 settings 读取。"""
    from backend.core.llm_factory import create_llm

    llm = create_llm("minimax")
    assert llm.model_name == settings.MINIMAX_MODEL  # type: ignore[union-attr]
    assert llm.openai_api_base == settings.MINIMAX_BASE_URL  # type: ignore[union-attr]
    assert llm.openai_api_key.get_secret_value() == settings.MINIMAX_API_KEY.get_secret_value()  # type: ignore[union-attr]
    assert llm.temperature == 0.7  # type: ignore[union-attr]


def test_create_llm_invalid_model_raises() -> None:
    """未知 model 名抛出 ValueError。"""
    from backend.core.llm_factory import create_llm

    with pytest.raises(ValueError, match="Unsupported model"):
        create_llm("invalid_model_name")


def test_create_llm_timeout() -> None:
    """timeout 从 LLM_TIMEOUT 读取。"""
    from backend.core.llm_factory import create_llm

    llm = create_llm("deepseek")
    assert llm.request_timeout == settings.LLM_TIMEOUT  # type: ignore[union-attr]


def test_create_llm_thinking_mode_default_disabled() -> None:
    """thinking_mode 默认 False，extra_body 不应含 thinking 键。"""
    from backend.core.llm_factory import create_llm

    llm = create_llm("deepseek")
    eb = getattr(llm, "extra_body", None) or {}
    assert "thinking" not in eb


def test_create_llm_thinking_mode_enabled() -> None:
    """thinking_mode=True 时 extra_body 含 thinking 键。"""
    from backend.core.llm_factory import create_llm

    llm = create_llm("deepseek", thinking_mode=True)
    eb = getattr(llm, "extra_body", None)
    assert eb is not None
    assert "thinking" in eb
