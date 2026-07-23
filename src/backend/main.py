"""FastAPI 应用入口。

本模块持有 :data:`app` 单例,挂载 v1 聚合路由(M7.2 接管子路由),
并暴露 ``GET /health`` 存活探针。

注意:本模块在导入时会间接触发 :mod:`backend.config` 的模块级单例
构造,因此要求 ``.env.local`` 存在且满足 TechSPEC §3 规范(M1.1 已保证)。
``/health`` 自身不读 ``settings``,不连任何外部服务。
"""
from __future__ import annotations

from fastapi import FastAPI

from backend.api.v1.router import router as v1_router

app = FastAPI(title="ECMultiAgents", version="0.1.0")
app.include_router(v1_router, prefix="/v1")


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """存活探针。M7 之前的所有 Agent 都可以依赖此接口做预热。"""
    return {"status": "ok"}
