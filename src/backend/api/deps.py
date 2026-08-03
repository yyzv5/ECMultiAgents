"""API 层依赖注入(``api/deps.py``)。

本模块集中暴露 FastAPI ``Depends`` 所需的工厂函数,实现见
``docs/spec/TechSPEC.md`` §8(依赖注入)与 ``state/project_status.md`` M1.3。

请求级:
    - ``get_db`` — 创建/关闭 SQLAlchemy 数据库 session;请求结束后自动关闭。

全局单例(懒加载,``@functools.lru_cache`` 装饰):
    - ``get_rag_graph`` — RAG Agent 编译后的 StateGraph(M5.2)。
    - ``get_listing_graph`` — 上架助手 Agent 编译后的 StateGraph(M5.4)。
    - ``get_data_graph`` — 数据智能 Agent 编译后的 StateGraph(M5.6)。
    - ``get_orchestrator`` — 编排层(父图)编译后的 StateGraph(M6.1)。

M5/M6 与 M4.3 未落地时的占位语义
---------------------------------

M1.3 仅要求模块可被 import;M5/M6 真实 graph 模块与 M4.3 的
``backend.db.session.SessionLocal`` 当前均不存在。本模块对它们使用
``try/except ImportError`` 包裹预导入:模块缺位时绑定到 ``None``,
对应 getter 在 ``@lru_cache`` 首次调用时返回 ``None`` 占位。 M5/M6/M4.3
落地后 import 路径自动生效,无需修改本文件。

``get_db`` 是 generator-based Depends(``yield`` + ``finally``),M4.3 缺位时
``yield None``;FastAPI Depends 注册链仍可成功,只有真正发起请求时消费方
才会拿到 None。M4.3 接入后 ``SessionLocal`` 存在,自动进入真实 session 分支。
"""


from collections.abc import Generator
from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session


# ---------- M5/M6 模块预导入(try/except ImportError 占位) ----------

try:
    from backend.agents.rag_agent.graph import graph as _rag_graph_source
except ImportError:
    # M5.2 ``src/backend/agents/rag_agent/graph.py`` 尚未落地。
    _rag_graph_source: Any = None

try:
    from backend.agents.listing_agent.graph import graph as _listing_graph_source
except ImportError:
    # M5.4 ``src/backend/agents/listing_agent/graph.py`` 尚未落地。
    _listing_graph_source: Any = None

try:
    from backend.agents.data_agent.graph import graph as _data_graph_source
except ImportError:
    # M5.6 ``src/backend/agents/data_agent/graph.py`` 尚未落地。
    _data_graph_source: Any = None

try:
    from backend.core.orchestrator import graph as _orchestrator_source
except ImportError:
    # M6.1 ``src/backend/core/orchestrator.py`` 尚未落地。
    _orchestrator_source: Any = None


# ---------- 请求级: 数据库会话(get_db) ----------

def get_db() -> Generator[Session | None, None, None]:
    """FastAPI ``Depends`` 工厂: 每次请求一个新 session,请求结束后关闭。

    连接字符串将由 M4.3 的 :func:`backend.db.session._build_engine_url`
    拼接;本函数只负责 ``SessionLocal()`` 的创建与 ``close()``。

    注意 (L06): ``SessionLocal()`` 返回 ``sessionmaker`` 实例(callable),
    必须**二次调用** ``SessionLocal()()`` 才能得到 ``Session``。
    SQLAlchemy ``sessionmaker`` 的设计是"工厂的工厂"。

    Yields:
        ``Session`` 实例(M4.3 落地后);M4.3 缺位时 ``yield None`` 占位。
    """
    try:
        from backend.db.session import SessionLocal
    except ImportError:
        # M4.3 ``src/backend/db/session.py`` 尚未落地;占位 yield None。
        SessionLocal = None  # type: ignore[assignment]

    if SessionLocal is None:
        yield None
        return

    db = SessionLocal()()
    try:
        yield db
    finally:
        db.close()


# ---------- 全局单例: Agent Graphs ----------

@lru_cache(maxsize=1)
def get_rag_graph() -> Any:
    """懒加载 + 全局缓存 RAG Agent StateGraph(M5.2)。"""
    return _rag_graph_source


@lru_cache(maxsize=1)
def get_listing_graph() -> Any:
    """懒加载 + 全局缓存 上架助手 StateGraph(M5.4)。"""
    return _listing_graph_source


@lru_cache(maxsize=1)
def get_data_graph() -> Any:
    """懒加载 + 全局缓存 数据智能 StateGraph(M5.6)。"""
    return _data_graph_source


@lru_cache(maxsize=1)
def get_orchestrator() -> Any:
    """懒加载 + 全局缓存 编排层(父图)(M6.1)。"""
    return _orchestrator_source


__all__ = [
    "get_db",
    "get_rag_graph",
    "get_listing_graph",
    "get_data_graph",
    "get_orchestrator",
]
