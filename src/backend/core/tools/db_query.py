"""SELECT-only 数据库查询 Tool。

封装 SQLAlchemy session 执行 SELECT 查询为 LangChain ``@tool``,
供 Data Agent 的 ``text_to_sql`` 节点调用。

安全措施:
    - ``_assert_select_only``: 首词 SELECT 校验 + 多语句拒绝 + DDL/DML 关键字黑名单
    - ``_extract_referenced_tables``: FROM/JOIN 表名提取 + 白名单校验
    - 异常一律返回 ``"Query failed: <error>"`` 字符串（不向上抛异常）

输出: JSON 字符串 ``{"columns": [...], "rows": [...], "row_count": N}``
"""
from __future__ import annotations

import json
import logging
import re

from langchain_core.tools import tool
from sqlalchemy import text

from backend.db.session import SessionLocal

logger = logging.getLogger(__name__)

# 表名白名单（小写）
_ALLOWED_TABLES: frozenset[str] = frozenset({"product_sales", "ad_performance"})

# DDL/DML 关键字黑名单（首词匹配，大小写不敏感）
_FORBIDDEN_KEYWORDS: frozenset[str] = frozenset({
    "INSERT", "UPDATE", "DELETE", "MERGE",
    "CREATE", "DROP", "ALTER", "TRUNCATE",
    "GRANT", "REVOKE", "VACUUM", "REINDEX",
})


def _assert_select_only(sql: str) -> None:
    """校验 SQL 语句是否为合法的单条 SELECT。

    规则:
        1. 去掉首部空白与行注释后，首词必须是 SELECT
        2. 拒绝多语句（`;` 后非空字符）
        3. 拒绝 DDL/DML 关键字

    Args:
        sql: 待校验的 SQL 字符串。

    Raises:
        ValueError: 校验不通过时抛出。
    """
    # 去掉首部空白
    cleaned = sql.strip()
    # 去掉行注释
    cleaned = re.sub(r"--.*", "", cleaned).strip()

    if not cleaned:
        raise ValueError("empty SQL statement")

    # 首词提取（不区分大小写）
    first_word_match = re.match(r"(\w+)", cleaned)
    if not first_word_match:
        raise ValueError(f"non-SELECT statement: {sql!r}")

    first_word = first_word_match.group(1).upper()

    if first_word != "SELECT":
        raise ValueError(f"non-SELECT statement: {sql!r}")

    # 拒绝多语句：检查去掉末尾分号后是否仍有分号
    no_trailing_semi = cleaned.rstrip(";").strip()
    if ";" in no_trailing_semi:
        raise ValueError(f"multiple statements detected: {sql!r}")

    # 拒绝 DDL/DML 关键字（在整条 SQL 中出现即拒绝）
    tokens = set(re.findall(r"\b(\w+)\b", cleaned.upper()))
    forbidden_found = tokens & _FORBIDDEN_KEYWORDS
    if forbidden_found:
        raise ValueError(
            f"forbidden keyword(s): {sorted(forbidden_found)}"
        )


def _extract_referenced_tables(sql: str) -> set[str]:
    """从 SQL 中提取 FROM / JOIN 后的表名（小写）。

    不区分大小写匹配。白名单校验不在本函数内完成。

    Args:
        sql: 待提取表名的 SQL 字符串。

    Returns:
        提取到的表名集合（小写）。无 FROM/JOIN 时返回空集。
    """
    pattern = re.compile(
        r"\b(?:FROM|JOIN)\s+[\"`]?(\w+)[\"`]?",
        re.IGNORECASE,
    )
    return {m.group(1).lower() for m in pattern.finditer(sql)}


def _result_to_json(columns: list[str], rows: list[dict]) -> str:
    """将查询结果序列化为 JSON 字符串。

    Args:
        columns: 列名列表。
        rows: 行字典列表。

    Returns:
        形如 ``{"columns": [...], "rows": [...], "row_count": N}`` 的 JSON 字符串。
    """
    return json.dumps(
        {"columns": columns, "rows": rows, "row_count": len(rows)},
        ensure_ascii=False,
        default=str,
    )


def _execute_select(sql: str) -> str:
    """用 SessionLocal 开新 session 执行 SELECT 并返回 JSON 字符串。

    Args:
        sql: 合法的 SELECT SQL 字符串。

    Returns:
        JSON 格式的查询结果字符串。
    """
    db = SessionLocal()
    try:
        result = db.execute(text(sql))
        columns = list(result.keys())
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
        return _result_to_json(columns, rows)
    finally:
        db.close()


@tool
def db_query(sql: str) -> str:
    """执行 SELECT 查询并以 JSON 字符串返回结果。

    仅允许 SELECT 语句，表名限制在白名单内（product_sales / ad_performance）。
    失败时返回 "Query failed: <error>" 字符串。

    Args:
        sql: 完整的 SELECT SQL 字符串。

    Returns:
        成功: JSON 字符串 ``{"columns": [...], "rows": [...], "row_count": N}``
        失败: ``"Query failed: <error>"`` 字符串
    """
    try:
        _assert_select_only(sql)
        tables = _extract_referenced_tables(sql)
        if not tables.issubset(_ALLOWED_TABLES):
            illegal = sorted(tables - _ALLOWED_TABLES)
            return f"Query failed: table not in whitelist: {illegal}"
        return _execute_select(sql)
    except Exception as exc:
        logger.warning("db_query failed for sql=%r: %s", sql, exc)
        return f"Query failed: {exc}"


__all__ = ["db_query"]
