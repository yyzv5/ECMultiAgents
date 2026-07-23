"""Application configuration center.

唯一配置入口：`src/backend/config.py`。
字段以 `docs/spec/TechSPEC.md §3` 为唯一规范名，按
"进程环境变量 > .env.local > 代码默认值" 加载。

不在模块导入时打印配置，不主动创建目录，不连接任何外部服务。
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """强类型应用配置。"""

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- LLM ----
    DEEPSEEK_BASE_URL: str
    DEEPSEEK_API_KEY: SecretStr
    MINIMAX_BASE_URL: str
    MINIMAX_API_KEY: SecretStr
    DEFAULT_LLM: str = "deepseek"
    LLM_TIMEOUT: int = 30

    # ---- Milvus ----
    MILVUS_HOST: str
    MILVUS_PORT: int
    MILVUS_COLLECTION: str = "knowledge_base"
    MILVUS_HYBRID_TOP_K: int = 20
    MILVUS_DENSE_WEIGHT: float = 0.7
    MILVUS_SPARSE_WEIGHT: float = 0.3

    # ---- Reranker / Confidence ----
    RERANKER_TOP_K: int = 5
    CONFIDENCE_FALLBACK_THRESHOLD: float = 0.6
    CONFIDENCE_UNRELIABLE_THRESHOLD: float = 0.4

    # ---- PostgreSQL ----
    PG_HOST: str
    PG_PORT: int
    PG_USER: str
    PG_PASSWORD: SecretStr
    PG_DATABASE: str

    # ---- Tavily ----
    TAVILY_API_KEY: SecretStr

    # ---- JWT ----
    SECRET_KEY: SecretStr
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    # ---- Checkpoint ----
    CHECKPOINT_DB_PATH: str = "data/checkpoints.db"

    # ---- 跨字段校验 ----
    @model_validator(mode="after")
    def _validate_cross_field(self) -> "Settings":
        errors: list[str] = []

        # 权重 ∈ [0, 1]
        for name in ("MILVUS_DENSE_WEIGHT", "MILVUS_SPARSE_WEIGHT"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                errors.append(f"{name}={value} 必须在 [0, 1] 区间")

        # 权重之和为 1（容差 1e-6，避免浮点精度问题）
        if abs(self.MILVUS_DENSE_WEIGHT + self.MILVUS_SPARSE_WEIGHT - 1.0) > 1e-6:
            errors.append(
                f"MILVUS_DENSE_WEIGHT + MILVUS_SPARSE_WEIGHT 必须等于 1.0 "
                f"(实际 {self.MILVUS_DENSE_WEIGHT + self.MILVUS_SPARSE_WEIGHT})"
            )

        # 不确定阈值顺序
        if self.CONFIDENCE_UNRELIABLE_THRESHOLD > self.CONFIDENCE_FALLBACK_THRESHOLD:
            errors.append(
                "CONFIDENCE_UNRELIABLE_THRESHOLD 必须 <= CONFIDENCE_FALLBACK_THRESHOLD"
            )

        # 精排数不能大于粗召回数
        if self.RERANKER_TOP_K > self.MILVUS_HYBRID_TOP_K:
            errors.append(
                f"RERANKER_TOP_K({self.RERANKER_TOP_K}) 必须 <= "
                f"MILVUS_HYBRID_TOP_K({self.MILVUS_HYBRID_TOP_K})"
            )

        # 端口/超时/过期/Top-K 都为正数
        positives: list[tuple[str, int]] = [
            ("MILVUS_PORT", self.MILVUS_PORT),
            ("PG_PORT", self.PG_PORT),
            ("LLM_TIMEOUT", self.LLM_TIMEOUT),
            ("JWT_EXPIRE_MINUTES", self.JWT_EXPIRE_MINUTES),
            ("MILVUS_HYBRID_TOP_K", self.MILVUS_HYBRID_TOP_K),
            ("RERANKER_TOP_K", self.RERANKER_TOP_K),
        ]
        for name, value in positives:
            if value <= 0:
                errors.append(f"{name}={value} 必须为正数")

        if errors:
            raise ValueError("; ".join(errors))

        return self


def _build_settings() -> Settings:
    """构造模块级单例。

    放在函数里便于在测试中通过 ``importlib.reload`` 或替换
    ``_TEST_ENV_FILE`` 后重新构造，而不会触发额外的副作用。
    """
    return Settings()


settings: Settings = _build_settings()


__all__ = ["Settings", "settings"]
