"""JWT 鉴权工具: 签发 / 校验 / FastAPI Depends。

所有配置从 :mod:`backend.config` 读取，不硬编码密钥和算法。

异常处理策略:
    - 所有 ``jose`` 原生异常在内部捕获，统一收敛为
      :class:`fastapi.HTTPException(401)`,避免 API 层重复 try/except。
    - 区分过期 (``Token expired``) 与其他无效 (``Invalid token``),
      便于前端识别。
"""
from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import HTTPException, Request, status
from jose import ExpiredSignatureError, JWTError, jwt

from backend.config import settings

logger = logging.getLogger(__name__)

_BEARER_PREFIX = "Bearer "


def create_access_token(user_id: str) -> str:
    """签发 JWT access token。

    Payload 仅含 ``sub``(user_id) 和 ``exp``(过期 unix 时间戳)。

    Args:
        user_id: 用户唯一标识，将写入 token 的 ``sub`` 字段。

    Returns:
        编码后的 JWT 字符串。
    """
    expire_at = int(time.time()) + settings.JWT_EXPIRE_MINUTES * 60
    payload: dict[str, Any] = {"sub": user_id, "exp": expire_at}
    return jwt.encode(
        payload,
        settings.SECRET_KEY.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )


def verify_token(token: str) -> str:
    """校验 JWT 并返回 ``user_id``。

    Args:
        token: 编码后的 JWT 字符串。

    Returns:
        解码后的 ``sub`` 字段（即 user_id）。

    Raises:
        HTTPException: 401 + ``detail="Token expired"`` 表示过期；
            401 + ``detail="Invalid token"`` 表示其他无效（签名错、
            格式错、缺 ``sub`` 等）。
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
        )
    except ExpiredSignatureError as exc:
        logger.warning("JWT expired: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except JWTError as exc:
        logger.warning("JWT invalid: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id = payload.get("sub")
    if not user_id or not isinstance(user_id, str):
        logger.warning("JWT payload missing 'sub' or wrong type: %r", user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_id


def get_current_user(request: Request) -> str:
    """FastAPI ``Depends``: 从 ``Authorization: Bearer <token>`` 提取并校验 token。

    Args:
        request: FastAPI 请求对象（由 Depends 注入）。

    Returns:
        校验通过后的 user_id 字符串。

    Raises:
        HTTPException: 401, ``detail="Invalid token"`` 当 header 缺失、
            非 Bearer 前缀、token 为空、或 token 校验失败。
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith(_BEARER_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header[len(_BEARER_PREFIX):].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return verify_token(token)


__all__ = ["create_access_token", "verify_token", "get_current_user"]
