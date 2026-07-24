"""用户 ORM 模型与 bcrypt 密码哈希工具。

模块职责:
    1. 定义 SQLAlchemy ``User`` ORM,映射到 ``users`` 表,供 M4.3 (SessionLocal)
       与 M7.3 (注册/登录 API) 复用。
    2. 提供 ``hash_password`` / ``verify_password`` 静态方法,
       所有密码写库前必须经 ``hash_password`` 哈希,
       校验时使用 ``verify_password``(不直接调用 ``bcrypt``)。

设计要点:
    - Base 使用 ``declarative_base()`` 在本模块内创建,不依赖 ``backend.db``。
      M4.4 引入更多 ORM 时再统一抽取到 ``backend.db.base.Base``(YAGNI)。
    - 哈希存储为 ``str``(UTF-8 解码后的 ``$2b$12$...``),
      便于 SQLAlchemy ``String`` 列直接持久化。
    - ``verify_password`` 在 ``bcrypt.checkpw`` 抛 ``ValueError``
      (哈希格式损坏 / 长度错) 时返回 ``False``,不向上抛异常。
      风格与 :mod:`backend.core.security` 的 ``verify_token`` 一致。
"""
from __future__ import annotations

from datetime import datetime

import bcrypt
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import declarative_base, mapped_column, Mapped


# 在 M4.1 阶段,Base 由本模块创建。M4.4 引入更多 ORM 时,统一迁移到
# ``backend.db.base.Base`` 并修改本模块的 import 语句。
Base = declarative_base()


class User(Base):
    """``users`` 表的 ORM 映射。

    字段:
        id:               自增主键。
        username:         用户名,唯一且建索引,非空。
        hashed_password:  bcrypt 哈希文本(``$2b$12$...``),非空。
        created_at:       记录创建时间(UTC),由 Python 侧默认值填充。
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    @staticmethod
    def hash_password(password: str) -> str:
        """对明文密码做 bcrypt 哈希,返回可入库的字符串。

        Args:
            password: 明文密码(任意 UTF-8 字符串)。

        Returns:
            ``$2b$12$<22-char-salt><31-char-hash>`` 形式的字符串。
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """校验明文密码与已存哈希是否匹配。

        任何异常(哈希格式损坏 / 长度错 / 非 UTF-8 等)均返回 ``False``,
        不向上抛异常。

        Args:
            plain_password:  用户输入的明文密码。
            hashed_password: 数据库中存储的 bcrypt 哈希字符串。

        Returns:
            密码匹配返回 ``True``,否则 ``False``。
        """
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8"),
            )
        except (ValueError, TypeError):
            return False

    def __repr__(self) -> str:
        return (
            f"<User id={self.id} username={self.username!r} "
            f"created_at={self.created_at!r}>"
        )


__all__ = ["User", "Base"]
