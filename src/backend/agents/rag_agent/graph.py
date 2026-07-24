"""RAG Agent StateGraph — 8 个节点 + 条件分支 + SQLite 持久化。

导出编译后的 ``graph`` 对象供 ``api/deps.py`` 的 ``get_rag_graph()`` 使用。

M7.7 落地前 Prompt 模板内联在模块顶部作为常量，后续统一抽出到
``prompts/rag_prompts.py``。
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from backend.agents.rag_agent.state import RagState
from backend.config import settings
from backend.core.llm_factory import create_llm
from backend.core.milvus_client import MilvusClient
from backend.core.tools.search import web_search

logger = logging.getLogger(__name__)

# =========================================================================
# Prompt 模板（模块级常量，M7.7 统一抽出到 prompts/rag_prompts.py）
# =========================================================================

QUERY_REWRITE_PROMPT = """\
你是一个查询改写专家。基于对话历史，将用户的当前问题改写为独立完整的检索查询。
要求：
1. 补全指代词（如"它"、"那个"→具体实体）
2. 扩展缩写（如"FBA"→"Fulfillment by Amazon"）
3. 保留原问题核心意图
4. 仅输出改写后的查询文本，不添加解释

对话历史：
{history}

当前问题：{query}

改写后的查询："""

VALIDATE_QUESTION_PROMPT = """\
判断以下问题是否与跨境电商运营相关。
相关领域包括：平台规则、物流报关、内部流程、运营知识、Listing上架、广告投放、数据分析等。
如果是问候、闲聊或完全无关的问题，返回 false。
仅返回 true 或 false。

问题：{query}"""

GENERATE_ANSWER_PROMPT = """\
你是跨境电商运营助手。请根据以下参考资料回答用户问题。

要求：
1. 基于参考资料回答，不要编造
2. 如果参考资料不足以回答，明确告知用户
3. 回答末尾注明引用来源
4. 如果知识库置信度偏低但已补充网络搜索结果，需在回答中提示"部分信息来自网络搜索，请核实后使用"

参考资料：
{context}

用户问题：{query}"""

# =========================================================================
# 辅助函数
# =========================================================================


def _format_history(messages: list, max_turns: int = 6) -> str:
    """将对话历史格式化为 Prompt 可用的纯文本（保留最近 max_turns 轮）。"""
    lines: list[str] = []
    for msg in messages[-max_turns:]:
        role = "用户" if isinstance(msg, HumanMessage) else "助手"
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _format_context(
    reranked_docs: list[dict] | None,
    web_results: list[dict] | None,
) -> str:
    """将检索结果和联网结果格式化为 LLM 上下文字符串。"""
    parts: list[str] = []

    if reranked_docs:
        parts.append("[知识库结果]")
        for i, doc in enumerate(reranked_docs, 1):
            text = doc.get("text", "")
            source = doc.get("source", "未知来源")
            conf = doc.get("confidence", 0.0)
            parts.append(f"{i}. {text}\n   来源：{source}（置信度：{conf:.2f}）")
        parts.append("")

    if web_results:
        parts.append("[网络搜索结果]")
        for i, res in enumerate(web_results, 1):
            content = res.get("content", "")
            url = res.get("url", "")
            parts.append(f"{i}. {content}\n   链接：{url}")
        parts.append("")

    context = "\n".join(parts).strip()
    return context or "未找到相关参考信息。"


def _extract_sources(
    reranked_docs: list[dict] | None,
    web_results: list[dict] | None,
) -> list[str]:
    """从检索结果中提取去重后的来源标识列表。"""
    sources: list[str] = []
    seen: set[str] = set()

    if reranked_docs:
        for doc in reranked_docs:
            source = doc.get("source", "")
            if source and source not in seen:
                sources.append(source)
                seen.add(source)

    if web_results:
        for res in web_results:
            url = res.get("url", "")
            if url and url not in seen:
                sources.append(url)
                seen.add(url)

    return sources


# =========================================================================
# 节点函数
# =========================================================================


def query_rewrite_node(state: RagState) -> dict:
    """基于对话历史改写用户查询。"""
    query = state.get("query", "")
    messages = state.get("messages", [])
    history = _format_history(messages)
    prompt = QUERY_REWRITE_PROMPT.format(history=history, query=query)

    try:
        llm = create_llm()
        response = llm.invoke(prompt)
        rewritten = (
            response.content.strip()
            if isinstance(response.content, str)
            else str(response.content)
        )
    except Exception:
        logger.exception("query_rewrite_node: LLM 调用失败，回退为原始 query")
        rewritten = query

    logger.info("query_rewrite: %r -> %r", query, rewritten)
    return {"rewritten_query": rewritten}


def validate_question_node(state: RagState) -> dict:
    """判断问题是否与跨境运营相关。"""
    query = state.get("query", "")
    prompt = VALIDATE_QUESTION_PROMPT.format(query=query)

    try:
        llm = create_llm()
        response = llm.invoke(prompt)
        text = (
            response.content.strip().lower()
            if isinstance(response.content, str)
            else str(response.content).strip().lower()
        )
        is_valid = "true" in text or "yes" in text
    except Exception:
        logger.exception("validate_question_node: LLM 调用失败，默认放行")
        is_valid = True

    logger.info("validate_question: %r -> %s", query, is_valid)
    return {"is_valid": is_valid}


def hybrid_retrieval_node(state: RagState) -> dict:
    """执行 Milvus 混合检索 + 精排 + 置信度计算。"""
    rewritten = state.get("rewritten_query", "")
    logger.info("hybrid_retrieval: query=%r", rewritten)

    try:
        client = MilvusClient()
        docs = client.hybrid_search(rewritten)
    except Exception:
        logger.exception("hybrid_retrieval_node: Milvus 检索失败")
        docs = []

    confidence = max((d.get("confidence", 0.0) for d in docs), default=0.0)
    logger.info(
        "hybrid_retrieval: retrieved %d docs, max confidence=%.4f",
        len(docs),
        confidence,
    )
    return {"reranked_docs": docs, "confidence": confidence}


def check_confidence_node(state: RagState) -> dict:
    """判断是否需要联网搜索补充。"""
    confidence = state.get("confidence", 0.0)
    need_web = confidence < settings.CONFIDENCE_FALLBACK_THRESHOLD
    logger.info(
        "check_confidence: confidence=%.4f, threshold=%.2f, need_web=%s",
        confidence,
        settings.CONFIDENCE_FALLBACK_THRESHOLD,
        need_web,
    )
    return {"need_web": need_web}


def web_search_node(state: RagState) -> dict:
    """联网搜索补充信息。"""
    rewritten = state.get("rewritten_query", "")
    logger.info("web_search: query=%r", rewritten)

    try:
        result = web_search(query=rewritten, max_results=5)
        if isinstance(result, str):
            logger.warning("web_search_node: 搜索返回错误: %s", result)
            web_results: list[dict[str, str]] = []
        else:
            web_results = result if isinstance(result, list) else []
    except Exception:
        logger.exception("web_search_node: 搜索调用异常")
        web_results = []

    logger.info("web_search: got %d results", len(web_results))
    return {"web_results": web_results}


def merge_context_node(state: RagState) -> dict:
    """拼接检索结果和联网结果为 LLM 上下文。"""
    reranked_docs = state.get("reranked_docs", [])
    web_results = state.get("web_results", [])
    context = _format_context(reranked_docs, web_results)
    logger.info("merge_context: context length=%d chars", len(context))
    return {"context": context}


def generate_answer_node(state: RagState) -> dict:
    """基于上下文生成最终回答。"""
    query = state.get("query", "")
    context = state.get("context", "")
    prompt = GENERATE_ANSWER_PROMPT.format(context=context, query=query)

    try:
        llm = create_llm()
        response = llm.invoke(prompt)
        answer = (
            response.content.strip()
            if isinstance(response.content, str)
            else str(response.content)
        )
    except Exception:
        logger.exception("generate_answer_node: LLM 调用失败")
        answer = "抱歉，回答生成过程中出现错误，请稍后重试。"

    reranked_docs = state.get("reranked_docs", [])
    web_results = state.get("web_results", [])
    sources = _extract_sources(reranked_docs, web_results)

    logger.info("generate_answer: answer_len=%d, sources=%s", len(answer), sources)
    return {
        "answer": answer,
        "sources": sources,
        "messages": [AIMessage(content=answer)],
    }


def reject_answer_node(state: RagState) -> dict:
    """礼貌拒绝回答无关问题。"""
    answer = "抱歉，这个问题与跨境电商运营无关，我无法回答。"

    logger.info("reject_answer: 已拒绝回答")
    return {
        "answer": answer,
        "rejected": True,
        "sources": [],
        "messages": [AIMessage(content=answer)],
    }


# =========================================================================
# 条件路由函数
# =========================================================================


def route_after_validation(state: RagState) -> str:
    """根据校验结果路由：有效 -> hybrid_retrieval，无效 -> reject_answer。"""
    return "hybrid_retrieval" if state.get("is_valid") else "reject_answer"


def route_after_confidence(state: RagState) -> str:
    """根据置信度路由：高 -> merge_context（仅内部知识），低 -> web_search。"""
    return "web_search" if state.get("need_web") else "merge_context"


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
    """构建 RAG Agent 的 StateGraph（不编译）。"""
    builder = StateGraph(RagState)

    # 注册 8 个节点
    builder.add_node("query_rewrite", query_rewrite_node)
    builder.add_node("validate_question", validate_question_node)
    builder.add_node("hybrid_retrieval", hybrid_retrieval_node)
    builder.add_node("check_confidence", check_confidence_node)
    builder.add_node("web_search", web_search_node)
    builder.add_node("merge_context", merge_context_node)
    builder.add_node("generate_answer", generate_answer_node)
    builder.add_node("reject_answer", reject_answer_node)

    # START -> query_rewrite
    builder.set_entry_point("query_rewrite")

    # query_rewrite -> validate_question
    builder.add_edge("query_rewrite", "validate_question")

    # validate_question -> hybrid_retrieval / reject_answer（条件分支）
    builder.add_conditional_edges("validate_question", route_after_validation)

    # hybrid_retrieval -> check_confidence
    builder.add_edge("hybrid_retrieval", "check_confidence")

    # check_confidence -> web_search / merge_context（条件分支）
    builder.add_conditional_edges("check_confidence", route_after_confidence)

    # web_search -> merge_context
    builder.add_edge("web_search", "merge_context")

    # merge_context -> generate_answer -> END
    builder.add_edge("merge_context", "generate_answer")
    builder.add_edge("generate_answer", END)

    # reject_answer -> END
    builder.add_edge("reject_answer", END)

    return builder


# 模块级：编译 graph 对象（供 deps.py import）
try:
    _checkpointer = _create_checkpointer()
    _builder = _build_graph()
    graph = _builder.compile(checkpointer=_checkpointer)
    logger.info(
        "RAG Agent StateGraph 编译成功，checkpointer 绑定: %s",
        settings.CHECKPOINT_DB_PATH,
    )
except Exception:
    logger.exception("RAG Agent StateGraph 编译失败")
    raise

__all__ = ["graph"]
