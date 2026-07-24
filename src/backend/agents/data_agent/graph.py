"""Data Agent StateGraph — 8 个节点 + 条件分支 + SQL 重试循环 + SQLite 持久化。

导出编译后的 ``graph`` 对象供 ``api/deps.py`` 的 ``get_data_graph()`` 使用。

M7.7 落地前 Prompt 模板内联在模块顶部作为常量，后续统一抽出到
``prompts/data_prompts.py``。
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from langchain_core.messages import AIMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from backend.agents.data_agent.state import DataState
from backend.config import settings
from backend.core.llm_factory import create_llm
from backend.core.tools.db_query import db_query

logger = logging.getLogger(__name__)

# =========================================================================
# Prompt 模板（模块级常量，M7.7 统一抽出到 prompts/data_prompts.py）
# =========================================================================

CLASSIFY_ANALYSIS_TYPE_PROMPT = """\
判断用户的分析请求属于以下哪种类型：
- weekly_report: 请求按周分析/汇总/趋势（含"周""本周""上周"）
- monthly_report: 请求按月分析/汇总/趋势（含"月""本月""上月"）
- free_analysis: 其他自由分析请求（特定指标查询/自定义维度对比等）

仅输出一个单词：weekly_report / monthly_report / free_analysis。

用户请求：{query}"""

EXTRACT_INTENT_PROMPT = """\
你是一个数据分析意图提取专家。从用户的分析请求中提取具体的分析意图。
要求：
1. 提取用户想要分析的具体指标（如销售额、订单量、广告花费等）
2. 提取用户关心的维度（如按平台、按时间、按商品等）
3. 提取可能的时间范围
4. 用一句话描述分析目标

用户请求：{query}

分析意图："""

TEXT_TO_SQL_PROMPT = """\
你是一个SQL专家。根据以下分析意图生成PostgreSQL兼容的SELECT查询。
要求：
1. 只输出SQL语句，不要添加解释
2. 必须使用SELECT开头
3. 只能查询以下表：product_sales（产品销售表）、ad_performance（广告表现表）
4. 确保SQL语法正确

可用的表结构：

product_sales:
- id (INTEGER, PRIMARY KEY)
- platform (VARCHAR) — 平台名称（Amazon / Shopee / AliExpress）
- asin (VARCHAR) — 商品标识
- title (VARCHAR) — 商品标题
- category (VARCHAR) — 商品类目
- date (DATE) — 销售日期
- currency (VARCHAR) — 币种（USD / SGD / CNY）
- sales (FLOAT) — 销售额
- units (INTEGER) — 销量
- page_views (INTEGER) — 页面浏览量
- sessions (INTEGER) — 访客数

ad_performance:
- id (INTEGER, PRIMARY KEY)
- platform (VARCHAR) — 平台名称（Amazon / Shopee / AliExpress）
- asin (VARCHAR) — 商品标识
- campaign (VARCHAR) — 广告活动名称
- ad_type (VARCHAR) — 广告类型（SP / SB / SD）
- date (DATE) — 广告投放日期
- impressions (INTEGER) — 展示量
- clicks (INTEGER) — 点击量
- spend (FLOAT) — 广告花费
- ad_sales (FLOAT) — 广告带来的销售额
- orders (INTEGER) — 广告订单数
- acos (FLOAT) — 广告销售成本比
- ctr (FLOAT) — 点击率
- cpc (FLOAT) — 单次点击成本

分析意图：{intent}

SQL："""

FIX_SQL_PROMPT = """\
你是一个SQL修复专家。以下SQL执行时出现错误，请修正它。
要求：
1. 只输出修复后的SQL语句，不要添加解释
2. 必须使用SELECT开头
3. 只能用product_sales和ad_performance表
4. 确保SQL语法正确

原始SQL：{sql}

错误信息：{error}

修复后的SQL："""

GENERATE_REPORT_PROMPT = """\
你是一个数据分析报告生成专家。请根据用户的问题和查询结果生成易读的自然语言分析报告。
要求：
1. 用中文回答
2. 直接给出分析结论，不要提及"根据数据"等冗余描述
3. 突出关键数字和趋势
4. 如果查询结果为空，明确告知用户
5. 报告要结构化：总体概况 → 细分分析 → 结论建议

用户问题：{query}

SQL查询：{sql}

查询结果：{result}

分析报告："""

ERROR_RESPONSE_PROMPT = """\
数据分析过程中出现无法自动修复的错误。请友好地告知用户。
错误信息：{error}
生成的SQL：{sql}

回复用户："""


# =========================================================================
# 节点函数
# =========================================================================


def classify_analysis_type_node(state: DataState) -> dict:
    """判断用户请求属于周报/月报/自由分析。"""
    query = state.get("query", "")
    prompt = CLASSIFY_ANALYSIS_TYPE_PROMPT.format(query=query)

    try:
        llm = create_llm()
        response = llm.invoke(prompt)
        text = (
            response.content.strip().lower()
            if isinstance(response.content, str)
            else str(response.content).strip().lower()
        )
        if "weekly" in text:
            analysis_type = "weekly_report"
        elif "monthly" in text:
            analysis_type = "monthly_report"
        else:
            analysis_type = "free_analysis"
    except Exception:
        logger.exception("classify_analysis_type_node: LLM 调用失败，默认走自由分析")
        analysis_type = "free_analysis"

    logger.info("classify_analysis_type: %r -> %s", query, analysis_type)
    return {"analysis_type": analysis_type}


def predefined_report_node(state: DataState) -> dict:
    """预定义报告：根据 analysis_type 生成 SQL 模板。"""
    analysis_type = state.get("analysis_type", "")

    if analysis_type == "weekly_report":
        sql = (
            "SELECT platform, SUM(sales) AS total_sales, SUM(units) AS total_units "
            "FROM product_sales "
            "WHERE date >= '2026-07-01' "
            "GROUP BY platform ORDER BY total_sales DESC"
        )
    elif analysis_type == "monthly_report":
        sql = (
            "SELECT platform, SUM(sales) AS total_sales, SUM(units) AS total_units "
            "FROM product_sales "
            "WHERE date >= '2026-06-01' AND date < '2026-08-01' "
            "GROUP BY platform ORDER BY total_sales DESC"
        )
    else:
        sql = ""

    logger.info(
        "predefined_report: analysis_type=%s -> sql=%s",
        analysis_type,
        sql[:80],
    )
    return {"generated_sql": sql, "retry_count": 0, "max_retries": 2}


def extract_intent_node(state: DataState) -> dict:
    """从用户查询中提取分析意图。"""
    query = state.get("query", "")
    prompt = EXTRACT_INTENT_PROMPT.format(query=query)

    try:
        llm = create_llm()
        response = llm.invoke(prompt)
        intent = (
            response.content.strip()
            if isinstance(response.content, str)
            else str(response.content)
        )
    except Exception:
        logger.exception("extract_intent_node: LLM 调用失败，回退为原始 query")
        intent = query

    logger.info("extract_intent: %r -> %s", query, intent[:100])
    return {"extracted_intent": intent}


def text_to_sql_node(state: DataState) -> dict:
    """将分析意图转换为 SQL。"""
    intent = state.get("extracted_intent", state.get("query", ""))
    prompt = TEXT_TO_SQL_PROMPT.format(intent=intent)

    try:
        llm = create_llm()
        response = llm.invoke(prompt)
        sql = (
            response.content.strip()
            if isinstance(response.content, str)
            else str(response.content)
        )
    except Exception:
        logger.exception("text_to_sql_node: LLM 调用失败")
        sql = ""

    logger.info("text_to_sql: intent=%r -> sql=%s", intent[:50], sql[:80])
    return {"generated_sql": sql, "retry_count": 0, "max_retries": 2}


def execute_sql_node(state: DataState) -> dict:
    """执行 SQL 查询并返回结果。"""
    sql = state.get("generated_sql", "")
    if not sql:
        return {"sql_error": "no SQL to execute", "sql_result": None}

    result_str = db_query(sql)
    if result_str.startswith("Query failed:"):
        retry_count = state.get("retry_count", 0) + 1
        logger.warning(
            "execute_sql: sql=%r failed: %s (retry %d/%d)",
            sql[:80],
            result_str,
            retry_count,
            state.get("max_retries", 2),
        )
        return {
            "sql_error": result_str,
            "sql_result": None,
            "retry_count": retry_count,
        }

    try:
        result_data = json.loads(result_str)
    except json.JSONDecodeError:
        logger.exception("execute_sql: json 解析失败")
        retry_count = state.get("retry_count", 0) + 1
        return {
            "sql_error": "Query failed: JSON decode error",
            "sql_result": None,
            "retry_count": retry_count,
        }

    logger.info("execute_sql: success, rows=%d", result_data.get("row_count", 0))
    return {
        "sql_result": result_data,
        "sql_error": "",
        "retry_count": 0,
    }


def fix_sql_node(state: DataState) -> dict:
    """根据错误信息修复 SQL。"""
    sql = state.get("generated_sql", "")
    error = state.get("sql_error", "")
    prompt = FIX_SQL_PROMPT.format(sql=sql, error=error)

    try:
        llm = create_llm()
        response = llm.invoke(prompt)
        fixed_sql = (
            response.content.strip()
            if isinstance(response.content, str)
            else str(response.content)
        )
    except Exception:
        logger.exception("fix_sql_node: LLM 调用失败，保留原始 SQL")
        fixed_sql = sql

    logger.info("fix_sql: fixed sql=%s", fixed_sql[:80])
    return {"generated_sql": fixed_sql}


def generate_report_node(state: DataState) -> dict:
    """将查询结果组织为自然语言报告。"""
    query = state.get("query", "")
    sql = state.get("generated_sql", "")
    result = state.get("sql_result", {})

    result_str = json.dumps(result, ensure_ascii=False, default=str)
    prompt = GENERATE_REPORT_PROMPT.format(query=query, sql=sql, result=result_str)

    try:
        llm = create_llm()
        response = llm.invoke(prompt)
        report = (
            response.content.strip()
            if isinstance(response.content, str)
            else str(response.content)
        )
    except Exception:
        logger.exception("generate_report_node: LLM 调用失败")
        report = "抱歉，报告生成过程中出现错误，请稍后重试。"

    logger.info("generate_report: report_len=%d", len(report))
    return {"report": report, "messages": [AIMessage(content=report)]}


def error_response_node(state: DataState) -> dict:
    """告知用户分析失败。"""
    error = state.get("sql_error", "未知错误")
    sql = state.get("generated_sql", "")
    prompt = ERROR_RESPONSE_PROMPT.format(error=error, sql=sql)

    try:
        llm = create_llm()
        response = llm.invoke(prompt)
        report = (
            response.content.strip()
            if isinstance(response.content, str)
            else str(response.content)
        )
    except Exception:
        logger.exception("error_response_node: LLM 调用失败")
        report = f"数据分析失败：{error}"

    logger.info("error_response: %s", report[:100])
    return {"report": report, "messages": [AIMessage(content=report)]}


# =========================================================================
# 条件路由函数
# =========================================================================


def route_after_classify(state: DataState) -> str:
    """classify_analysis_type 后根据 analysis_type 二分流。"""
    at = state.get("analysis_type", "")
    if at in ("weekly_report", "monthly_report"):
        return "predefined_report"
    return "extract_intent"


def route_after_execute(state: DataState) -> str:
    """execute_sql 后三重路由：
    - sql_result 存在且 sql_error 为空 → generate_report
    - retry_count < max_retries          → fix_sql（重试）
    - retry_count >= max_retries         → error_response
    """
    sql_error = state.get("sql_error", "")
    sql_result = state.get("sql_result")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)

    if sql_result is not None and not sql_error:
        return "generate_report"
    if retry_count < max_retries:
        return "fix_sql"
    return "error_response"


# =========================================================================
# Checkpointer
# =========================================================================


def _create_checkpointer() -> SqliteSaver:
    """创建 SQLite 持久化的 MemorySaver。"""
    db_path = Path(settings.CHECKPOINT_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    return SqliteSaver(conn)


# =========================================================================
# Graph 构建与编译
# =========================================================================


def _build_graph() -> StateGraph:
    """构建 Data Agent 的 StateGraph（不编译）。"""
    builder = StateGraph(DataState)

    # 注册 8 个节点
    builder.add_node("classify_analysis_type", classify_analysis_type_node)
    builder.add_node("predefined_report", predefined_report_node)
    builder.add_node("extract_intent", extract_intent_node)
    builder.add_node("text_to_sql", text_to_sql_node)
    builder.add_node("execute_sql", execute_sql_node)
    builder.add_node("fix_sql", fix_sql_node)
    builder.add_node("generate_report", generate_report_node)
    builder.add_node("error_response", error_response_node)

    # START -> classify_analysis_type
    builder.set_entry_point("classify_analysis_type")

    # classify_analysis_type -> predefined_report / extract_intent（条件分支）
    builder.add_conditional_edges("classify_analysis_type", route_after_classify)

    # predefined_report -> execute_sql
    builder.add_edge("predefined_report", "execute_sql")

    # extract_intent -> text_to_sql -> execute_sql
    builder.add_edge("extract_intent", "text_to_sql")
    builder.add_edge("text_to_sql", "execute_sql")

    # execute_sql -> generate_report / fix_sql / error_response（重试循环）
    builder.add_conditional_edges("execute_sql", route_after_execute)

    # fix_sql -> execute_sql（重试循环）
    builder.add_edge("fix_sql", "execute_sql")

    # generate_report -> END
    builder.add_edge("generate_report", END)

    # error_response -> END
    builder.add_edge("error_response", END)

    return builder


# 模块级：编译 graph 对象（供 deps.py import）
try:
    _checkpointer = _create_checkpointer()
    _builder = _build_graph()
    graph = _builder.compile(checkpointer=_checkpointer)
    logger.info(
        "Data Agent StateGraph 编译成功，checkpointer 绑定: %s",
        settings.CHECKPOINT_DB_PATH,
    )
except Exception:
    logger.exception("Data Agent StateGraph 编译失败")
    raise

__all__ = ["graph"]
