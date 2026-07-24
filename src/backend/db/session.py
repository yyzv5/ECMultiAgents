"""SQLAlchemy 同步 engine 与 SessionLocal 工厂(M4.3)。

模块职责:
    - :data:`engine`  全局懒加载 SQLAlchemy ``Engine`` 单例。
    - :data:`SessionLocal`  同步 ``sessionmaker`` 工厂。
    - :func:`_build_engine_url`  按 ``settings.PG_*`` 五个字段
      拼接 ``postgresql+psycopg2`` URL(私有)。

设计要点:
    - engine 与 SessionLocal 都通过 ``@functools.lru_cache`` 懒构造,
      避免 import 时连 DB;FastAPI 启动后才首次实例化。
    - ``get_db()`` 不在本模块实现,由 :mod:`backend.api.deps` 接管
      (M1.3 阶段已埋 ``from backend.db.session import SessionLocal``)。
    - 连接字符串使用 ``urllib.parse.quote_plus`` 编码 password,
      防特殊字符(``@`` / ``:`` / ``/``)触发 URL 解析错误。
"""
from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import settings


@lru_cache(maxsize=1)
def _build_engine_url() -> str:
    """拼接 ``postgresql+psycopg2`` URL,所有字段从 settings 读。

    Returns:
        形如 ``postgresql+psycopg2://user:pass@host:port/db`` 的字符串。
    """
    user = settings.PG_USER
    password = quote_plus(settings.PG_PASSWORD.get_secret_value())
    host = settings.PG_HOST
    port = settings.PG_PORT
    database = settings.PG_DATABASE
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


@lru_cache(maxsize=1)
def engine() -> Engine:
    """全局 SQLAlchemy ``Engine`` 单例(懒加载)。

    配置:
        - ``pool_pre_ping=True``: 防 stale 连接(对 PG 必要)。
        - ``echo=False``: 不打 SQL 日志(可按需加 config 控制)。

    Returns:
        配置好的 :class:`sqlalchemy.engine.Engine`。
    """
    return create_engine(
        _build_engine_url(),
        pool_pre_ping=True,
        future=True,
    )


@lru_cache(maxsize=1)
def SessionLocal() -> sessionmaker[Session]:  # noqa: N802
    """``sessionmaker`` 工厂(懒加载)。

    ``expire_on_commit=False`` 避免 commit 后实例属性失效,
    与 FastAPI Depends 模式契合(请求结束后再关闭)。

    Returns:
        配置好的 :class:`sqlalchemy.orm.sessionmaker`。
    """
    return sessionmaker(
        bind=engine(),
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )


__all__ = ["engine", "SessionLocal", "_build_engine_url"]