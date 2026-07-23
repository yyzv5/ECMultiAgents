"""Test fixtures for backend.config tests.

隔离真实 .env.local 与开发机环境，确保 config 测试只依赖注入的假值。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

import pytest


# 在任何测试模块 import 之前先清场 + 用最小假值覆盖。
# 目的：让 backend.config 的模块级单例在 collection 阶段就能加载到一组
# 满足 fail-fast 的假配置，避免触发 ValidationError 中断收集。
_PRE_COLLECTION_DEFAULTS = {
    "DEEPSEEK_BASE_URL": "https://test.deepseek.example/v1",
    "DEEPSEEK_API_KEY": "test-deepseek-key",
    "MINIMAX_BASE_URL": "https://test.minimax.example/v1",
    "MINIMAX_API_KEY": "test-minimax-key",
    "MILVUS_HOST": "127.0.0.1",
    "MILVUS_PORT": "19531",
    "MILVUS_COLLECTION": "knowledge_base",
    "MILVUS_HYBRID_TOP_K": "20",
    "MILVUS_DENSE_WEIGHT": "0.7",
    "MILVUS_SPARSE_WEIGHT": "0.3",
    "DEEPSEEK_MODEL": "deepseek-v4-flash",
    "MINIMAX_MODEL": "Minimax-M3",
    "RERANKER_TOP_K": "5",
    "CONFIDENCE_FALLBACK_THRESHOLD": "0.6",
    "CONFIDENCE_UNRELIABLE_THRESHOLD": "0.4",
    "PG_HOST": "127.0.0.1",
    "PG_PORT": "5433",
    "PG_USER": "test_pg_user",
    "PG_PASSWORD": "test-pg-password",
    "PG_DATABASE": "test_pg_db",
    "TAVILY_API_KEY": "test-tavily-key",
    "SECRET_KEY": "test-jwt-secret",
}

for _k in [
    "DEEPSEEK_BASE_URL", "DEEPSEEK_API_KEY",
    "MINIMAX_BASE_URL", "MINIMAX_API_KEY",
    "DEFAULT_LLM", "LLM_TIMEOUT",
    "MILVUS_HOST", "MILVUS_PORT", "MILVUS_COLLECTION",
    "MILVUS_HYBRID_TOP_K", "MILVUS_DENSE_WEIGHT", "MILVUS_SPARSE_WEIGHT",
    "DEEPSEEK_MODEL", "MINIMAX_MODEL",
    "RERANKER_TOP_K", "CONFIDENCE_FALLBACK_THRESHOLD", "CONFIDENCE_UNRELIABLE_THRESHOLD",
    "PG_HOST", "PG_PORT", "PG_USER", "PG_PASSWORD", "PG_DATABASE",
    "TAVILY_API_KEY",
    "SECRET_KEY", "JWT_ALGORITHM", "JWT_EXPIRE_MINUTES",
    "CHECKPOINT_DB_PATH",
    "COLLECTION_NAME",
    "JWT_SECRET_KEY", "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
    "VECTOR_TOP_K", "ANN_EF", "RERANK_TOP_K", "HIGH_CONFIDENCE_THRESHOLD",
]:
    os.environ.pop(_k, None)

for _k, _v in _PRE_COLLECTION_DEFAULTS.items():
    os.environ[_k] = _v

# 全部 TechSPEC §3 规范字段（含默认值）。测试通过临时 dotenv 文件注入，
# 与开发机真实的 .env.local 完全隔离。
CANONICAL_KEYS = [
    # LLM
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_API_KEY",
    "MINIMAX_BASE_URL",
    "MINIMAX_API_KEY",
    "DEFAULT_LLM",
    "LLM_TIMEOUT",
    "DEEPSEEK_MODEL",
    "MINIMAX_MODEL",
    # Milvus
    "MILVUS_HOST",
    "MILVUS_PORT",
    "MILVUS_COLLECTION",
    "MILVUS_HYBRID_TOP_K",
    "MILVUS_DENSE_WEIGHT",
    "MILVUS_SPARSE_WEIGHT",
    # Reranker / Confidence
    "RERANKER_TOP_K",
    "CONFIDENCE_FALLBACK_THRESHOLD",
    "CONFIDENCE_UNRELIABLE_THRESHOLD",
    # PostgreSQL
    "PG_HOST",
    "PG_PORT",
    "PG_USER",
    "PG_PASSWORD",
    "PG_DATABASE",
    # Tavily
    "TAVILY_API_KEY",
    # JWT
    "SECRET_KEY",
    "JWT_ALGORITHM",
    "JWT_EXPIRE_MINUTES",
    # Checkpoint
    "CHECKPOINT_DB_PATH",
]

# 历史键名清理：避免开发机 .env.local 残留污染测试。
LEGACY_KEYS = [
    "COLLECTION_NAME",
    "JWT_SECRET_KEY",
    "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
    "VECTOR_TOP_K",
    "ANN_EF",
    "RERANK_TOP_K",
    "HIGH_CONFIDENCE_THRESHOLD",
]

# 一套完整的假配置。明显带 test- 前缀，避免误判为真实凭据。
FAKE_VALUES = {
    "DEEPSEEK_BASE_URL": "https://test.deepseek.example/v1",
    "DEEPSEEK_API_KEY": "test-deepseek-key",
    "MINIMAX_BASE_URL": "https://test.minimax.example/v1",
    "MINIMAX_API_KEY": "test-minimax-key",
    "DEFAULT_LLM": "deepseek",
    "LLM_TIMEOUT": "30",
    "DEEPSEEK_MODEL": "deepseek-v4-flash",
    "MINIMAX_MODEL": "Minimax-M3",
    "MILVUS_HOST": "127.0.0.1",
    "MILVUS_PORT": "19531",
    "MILVUS_COLLECTION": "knowledge_base",
    "MILVUS_HYBRID_TOP_K": "20",
    "MILVUS_DENSE_WEIGHT": "0.7",
    "MILVUS_SPARSE_WEIGHT": "0.3",
    "RERANKER_TOP_K": "5",
    "CONFIDENCE_FALLBACK_THRESHOLD": "0.6",
    "CONFIDENCE_UNRELIABLE_THRESHOLD": "0.4",
    "PG_HOST": "127.0.0.1",
    "PG_PORT": "5433",
    "PG_USER": "test_pg_user",
    "PG_PASSWORD": "test-pg-password",
    "PG_DATABASE": "test_pg_db",
    "TAVILY_API_KEY": "test-tavily-key",
    "SECRET_KEY": "test-jwt-secret",
    "JWT_ALGORITHM": "HS256",
    "JWT_EXPIRE_MINUTES": "1440",
    "CHECKPOINT_DB_PATH": "data/checkpoints.db",
}


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """清空规范字段与历史别名，再用临时假值注入到进程环境。

    不读取、不复制、不打印项目根目录的 .env.local。

    在每个测试前：先清场，再 reload backend.config 模块，让模块级
    ``settings`` 单例在隔离环境下重新构造。
    """
    import importlib

    for key in CANONICAL_KEYS + LEGACY_KEYS:
        monkeypatch.delenv(key, raising=False)

    # 把全套假值注入进程环境
    for key, value in FAKE_VALUES.items():
        monkeypatch.setenv(key, value)

    env_file = tmp_path / "fake.env"
    env_file.write_text(
        "\n".join(f"{k}={v}" for k, v in FAKE_VALUES.items()) + "\n",
        encoding="utf-8",
    )

    import backend.config as _backend_config

    # 临时关闭 .env.local 文件读取，让 Settings 只看进程环境，
    # 避免开发机真实 .env.local 泄露到测试结果中
    original_env_file = _backend_config.Settings.model_config.get("env_file")
    _backend_config.Settings.model_config["env_file"] = None
    importlib.reload(_backend_config)

    yield

    # 还原 .env.local 配置，便于后续进程复用
    _backend_config.Settings.model_config["env_file"] = original_env_file
    monkeypatch.delenv("_TEST_ENV_FILE", raising=False)


@pytest.fixture
def fake_env_file(tmp_path: Path) -> Path:
    """返回临时 dotenv 路径，便于测试显式传入 _env_file。"""
    env_file = tmp_path / "explicit.env"
    env_file.write_text(
        "\n".join(f"{k}={v}" for k, v in FAKE_VALUES.items()) + "\n",
        encoding="utf-8",
    )
    return env_file


@pytest.fixture
def fake_env_overrides() -> dict[str, str]:
    """返回假值字典，供部分测试定制。"""
    return dict(FAKE_VALUES)
