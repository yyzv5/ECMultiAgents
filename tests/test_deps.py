"""API 依赖注入层契约测试。

测试覆盖:
  1. ``from backend.api.deps import ...`` 在 M5/M6/M4.3 未落地时仍可成功。
  2. 五个依赖函数均存在,且 ``get_*_graph`` 已被 ``@lru_cache`` 装饰。
  3. ``get_db`` 是 generator-based Depends;在 M4.3 缺位时返回 None 占位。
  4. ``@lru_cache`` 单例语义:同一 getter 两次调用返回同一对象。
  5. TestClient(app) 仍能正常响应 ``/health``(deps 模块未污染 main 启动链路)。
"""
from __future__ import annotations

import inspect

from fastapi.testclient import TestClient

from backend import api
from backend.api import deps
from backend.api.deps import (
    get_data_graph,
    get_db,
    get_listing_graph,
    get_orchestrator,
    get_rag_graph,
)
from backend.main import app


def test_deps_module_imports_without_error() -> None:
    """M5/M6/M4.3 缺位时 import 仍须成功;函数对象全部存在。"""
    assert hasattr(deps, "get_db")
    assert hasattr(deps, "get_rag_graph")
    assert hasattr(deps, "get_listing_graph")
    assert hasattr(deps, "get_data_graph")
    assert hasattr(deps, "get_orchestrator")
    assert api.deps is deps  # 子包 alias 暴露


def test_get_db_is_generator_function() -> None:
    """get_db 必须是 generator-based Depends(yield 形态)。"""
    assert inspect.isgeneratorfunction(get_db)


def test_graph_getters_are_lru_cache_wrapped() -> None:
    """四个 get_*_graph 必须被 @functools.lru_cache 装饰(lru_cache 留有 __wrapped__)。"""
    for fn in (get_rag_graph, get_listing_graph, get_data_graph, get_orchestrator):
        assert hasattr(fn, "__wrapped__"), f"{fn.__name__} missing lru_cache wrapper"


def test_graph_getters_return_singleton() -> None:
    """同一 getter 两次调用必须返回同一对象(lru_cache 单例语义)。"""
    # 触发首次调用(M5/M6 缺位下应返回 None 占位)
    g1 = get_rag_graph()
    g2 = get_rag_graph()
    assert g1 is g2, "lru_cache failed: two calls returned distinct objects"

    l1 = get_listing_graph()
    l2 = get_listing_graph()
    assert l1 is l2

    d1 = get_data_graph()
    d2 = get_data_graph()
    assert d1 is d2

    o1 = get_orchestrator()
    o2 = get_orchestrator()
    assert o1 is o2


def test_get_db_yields_and_closes_on_m4_missing() -> None:
    """M4.3 未落地时,get_db() 必须 yield 一次并正常 StopIteration。

    占位模式下 yield None;FastAPI Depends 注册仍能成功,但消费方拿到 None。
    M4.3 落地后本测试改为断言真实 SessionLocal 行为。
    """
    gen = get_db()
    value = next(gen)
    assert value is None  # 占位: M4.3 缺位时 yield None
    # 关闭路径: 触发 StopIteration 即可,finally 块内 close() 不会在 None 上崩
    try:
        next(gen)
    except StopIteration:
        pass
    else:
        raise AssertionError("get_db() generator did not terminate")


def test_health_still_works_with_deps_module_loaded() -> None:
    """deps.py 被 import 后,/health 仍能正常返回(M1.2 契约不破)。"""
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
