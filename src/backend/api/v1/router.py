"""v1 聚合路由 stub。

M1.2 阶段仅暴露空 :class:`APIRouter`,M7.2 在本文件追加
``include_router`` 调用以挂载 ``auth``、``rag``、``listing``、``data_insight``。
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()
