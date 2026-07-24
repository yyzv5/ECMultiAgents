"""v1 聚合路由。

使用 try/except ImportError 模式预导入 4 个子模块
（auth / rag / listing / data_insight），子模块创建后自动生效。
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()

try:
    from backend.api.v1.auth import router as _auth_router
    router.include_router(_auth_router, prefix="/auth", tags=["auth"])
except ImportError:
    pass

try:
    from backend.api.v1.rag import router as _rag_router
    router.include_router(_rag_router, prefix="", tags=["chat"])
except ImportError:
    pass

try:
    from backend.api.v1.listing import router as _listing_router
    router.include_router(_listing_router, prefix="/listing", tags=["listing"])
except ImportError:
    pass

try:
    from backend.api.v1.data_insight import router as _data_router
    router.include_router(_data_router, prefix="/data", tags=["data"])
except ImportError:
    pass
