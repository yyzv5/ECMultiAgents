"""Auth 公开端点: 注册 / 登录。

两个端点均不要求 Bearer token（区别于其他 v1 业务端点）：
    - ``POST /v1/auth/register`` — 用户名查重 → 哈希密码 → 落库 → 签发 JWT。
    - ``POST /v1/auth/login``    — 查用户 → 校验密码 → 签发 JWT。

设计要点:
    - 复用既有基础设施，本模块不重复造轮子:
        * Pydantic 模型 —— :mod:`backend.models.schemas`
        * JWT 签发       —— :func:`backend.core.security.create_access_token`
        * 密码哈希/校验  —— :meth:`backend.models.user.User.hash_password` /
          :meth:`backend.models.user.User.verify_password`
        * DB session 注入 —— :func:`backend.api.deps.get_db`
    - 登录失败信息保持模糊（401 不区分用户名或密码错误），
      与 :func:`backend.core.security.verify_token` 的设计一致，避免账号枚举。
    - 空字段在 API 函数内做显式判断（400），不依赖 Pydantic 层，
      便于返回中文可读提示。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.core.security import create_access_token
from backend.models.schemas import (
    APIResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from backend.models.user import User

router = APIRouter()


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    db: Session | None = Depends(get_db),
) -> APIResponse[TokenResponse]:
    """注册新用户并签发 JWT。

    流程: 校验非空 → 用户名查重 → 哈希密码 → 落库 → 签发 token。

    Args:
        body: 含 ``username`` / ``password`` 的注册请求体。
        db:   请求级数据库 session（由 :func:`get_db` 注入）。

    Returns:
        ``APIResponse[TokenResponse]``，data 含 access_token。

    Raises:
        HTTPException: 400 空字段；409 用户名已存在。
    """
    if not body.username or not body.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名和密码不能为空",
        )

    existing = db.query(User).filter(User.username == body.username).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在",
        )

    user = User(
        username=body.username,
        hashed_password=User.hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(str(user.id))
    return APIResponse(data=TokenResponse(access_token=token))


@router.post("/login")
def login(
    body: LoginRequest,
    db: Session | None = Depends(get_db),
) -> APIResponse[TokenResponse]:
    """校验凭据并签发 JWT。

    流程: 查用户 → 校验密码 → 签发 token。任何失败均返回模糊的 401，
    不区分是用户名不存在还是密码不匹配（防账号枚举）。

    Args:
        body: 含 ``username`` / ``password`` 的登录请求体。
        db:   请求级数据库 session（由 :func:`get_db` 注入）。

    Returns:
        ``APIResponse[TokenResponse]``，data 含 access_token。

    Raises:
        HTTPException: 401 用户名或密码错误。
    """
    user = db.query(User).filter(User.username == body.username).first()
    if user is None or not User.verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    token = create_access_token(str(user.id))
    return APIResponse(data=TokenResponse(access_token=token))


__all__ = ["router"]
