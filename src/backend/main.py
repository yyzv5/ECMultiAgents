"""FastAPI 应用入口。

本模块持有 :data:`app` 单例,挂载 v1 聚合路由(M7.2 接管子路由),
并暴露 ``GET /health`` 存活探针。

注意:本模块在导入时会间接触发 :mod:`backend.config` 的模块级单例
构造,因此要求 ``.env.local`` 存在且满足 TechSPEC §3 规范(M1.1 已保证)。
``/health`` 自身不读 ``settings``,不连任何外部服务。
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.v1.router import router as v1_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """服务启动生命周期：预热 Milvus 检索模型（EMBEDDING + RERANKER）。

    两个模型加载完成（含 Milvus 连接 + Collection 加载）后，
    才认为后端服务正式启动。测试环境通过 ``MODEL_PREWARM=false`` 跳过。
    """
    from backend.config import settings

    if not settings.MODEL_PREWARM:
        logger.info("MODEL_PREWARM=false，跳过模型预热。")
        yield
        return

    logger.info("开始预热检索模型（EMBEDDING + RERANKER）...")
    from backend.core.milvus_client import get_milvus_client

    client = get_milvus_client()  # 连接 Milvus + 加载 Collection
    client.warmup()  # 加载两个 ML 模型并常驻内存
    logger.info("模型预热完成，后端服务正式启动。")
    yield


app = FastAPI(title="ECMultiAgents", version="0.1.0", lifespan=lifespan)

# CORS（M8 接入）—— 浏览器从 http://localhost:5173 调 http://127.0.0.1:8000
# 属于跨域，必须在应用层放宽。CORS 是基础设施层关注点（影响所有路由），
# 归 main.py 一处最直观；不引入新文件（YAGNI）。前端另配 Vite proxy /api 双保险。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix="/v1")


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """存活探针。M7 之前的所有 Agent 都可以依赖此接口做预热。"""
    return {"status": "ok"}
