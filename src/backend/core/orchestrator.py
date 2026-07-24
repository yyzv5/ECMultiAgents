"""编排层父图 — 意图识别 + 路由分发到 RAG / Data 子 Agent。

4 个节点 + 1 条件路由函数::

    START → classify_intent
        → [rag] → call_rag_agent → format_result → END
        → [data] → call_data_agent → format_result → END

策略要点:
- intent 识别采用二阶段策略:规则匹配优先 → LLM 兜底
- 只为 rag 和 data 两个 intent 路由(listing 由独立 API 处理)
- RAG/Data 子 Agent 使用独立 thread_id 管理多轮对话
- 编译后的 ``graph`` 对象由 ``api/deps.py`` 的 ``get_orchestrator()`` 导入
"""

import logging
import re
from typing import Any, NotRequired, TypedDict

from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)


# =========================================================================
# 子 Agent Graph 预导入(与 deps.py 风格一致,ImportError 时降级为 None)
# =========================================================================

try:
    from backend.agents.rag_agent.graph import graph as _rag_graph
except ImportError:
    _rag_graph: Any = None

try:
    from backend.agents.data_agent.graph import graph as _data_graph
except ImportError:
    _data_graph: Any = None


# =========================================================================
# 规则关键词
# =========================================================================

_DATA_KEYWORDS = [
    "销量", "销售额", "分析", "周报", "月报", "趋势", "统计", "报表",
    "报告", "排名", "对比", "同比", "环比", "增长", "下降", "数据",
    "广告", "花费", "利润", "成本", "毛利率", "ROI", "ACOS", "曝光",
    "点击", "转化", "利润率", "客单价",
]

_RAG_KEYWORDS = [
    "FBA", "fba", "Fulfillment by Amazon",
    "规则", "流程", "政策", "费用", "关税", "物流",
    "入库", "出库", "退货", "退款", "库存", "仓储",
    "标签", "认证", "合规", "知识产权", "商标", "专利",
    "分类", "类目", "禁售", "限制", "要求", "条件",
    "怎么办", "是什么", "什么意思", "如何",
    "知识库", "问答", "条款", "协议",
]


# =========================================================================
# LLM 兜底 Prompt
# =========================================================================

CLASSIFY_INTENT_PROMPT = """\
判断用户的跨境运营问题属于以下哪个意图：
- rag：知识库问答（关于平台规则、物流、流程、FAQ等）
- data：数据分析（查询销量、报表、趋势等）

仅输出一个单词：rag / data。

用户问题：{query}"""


# =========================================================================
# State 定义
# =========================================================================


class OrchestratorState(TypedDict):
    """编排层 State。

    不含 ``messages`` 与 ``add_messages`` —— 对话历史由子 Agent 各自管理。

    Attributes:
        query: 用户输入。
        session_id: 会话标识(UUID)。
        history: 对话历史(由 API 层或前端提供,供 classify_intent 参考)。
        intent: 识别到的意图: ``rag`` / ``data``。
        confidence: LLM 兜底时的置信度(规则匹配时为 1.0)。
        agent_input: 传递给子 Agent 的参数字典。
        agent_result: 子 Agent 返回的结果(经 format_result 统一包装)。
    """

    query: str
    session_id: str
    history: NotRequired[list[dict]]
    intent: NotRequired[str]
    confidence: NotRequired[float]
    agent_input: NotRequired[dict]
    agent_result: NotRequired[dict]


# =========================================================================
# 节点函数
# =========================================================================


def classify_intent(state: OrchestratorState) -> dict:
    """二阶段意图识别节点。

    第一阶段: 规则关键词匹配。
    第二阶段: 规则未命中时调用 LLM 兜底分类。

    Returns:
        包含 ``intent`` 和 ``confidence`` (LLM 兜底时)的 dict。
    """
    query = state.get("query", "")

    # ── 第一阶段: 规则关键词匹配 ──
    intent, confidence = _rule_based_classify(query)
    if intent is not None:
        logger.info("classify_intent [rule]: query=%r -> intent=%s", query, intent)
        return {"intent": intent, "confidence": confidence}

    # ── 第二阶段: LLM 兜底 ──
    intent, confidence = _llm_classify(query)
    logger.info("classify_intent [llm]: query=%r -> intent=%s", query, intent)
    return {"intent": intent, "confidence": confidence}


def _rule_based_classify(query: str) -> tuple[str | None, float]:
    """规则关键词匹配。返回 (intent | None, confidence)。"""
    # data 关键词优先
    for kw in _DATA_KEYWORDS:
        if kw in query:
            return "data", 1.0

    # rag 关键词
    for kw in _RAG_KEYWORDS:
        if kw in query:
            return "rag", 1.0

    return None, 0.0


def _llm_classify(query: str) -> tuple[str, float]:
    """LLM 兜底分类。失败时默认返回 rag。"""
    try:
        from backend.core.llm_factory import create_llm

        llm = create_llm()
        prompt = CLASSIFY_INTENT_PROMPT.format(query=query)
        response = llm.invoke(prompt)
        text = (
            response.content.strip().lower()
            if isinstance(response.content, str)
            else str(response.content).strip().lower()
        )

        if "data" in text:
            return "data", 0.8
        return "rag", 0.8
    except Exception:
        logger.exception("classify_intent: LLM 兜底失败，默认走 rag")
        return "rag", 0.5


def route_to_agent(state: OrchestratorState) -> str:
    """条件路由函数(非节点): 根据 intent 分发到对应子 Agent 的 call 节点。

    未知 intent 时兜底到 ``call_rag_agent``。
    """
    intent = state.get("intent", "rag")
    if intent == "data":
        return "call_data_agent"
    return "call_rag_agent"


def call_rag_agent(state: OrchestratorState) -> dict:
    """调用 RAG Agent StateGraph。

    thread_id = ``{session_id}_rag`` —— 与 Data Agent 隔离。
    """
    query = state.get("query", "")
    session_id = state.get("session_id", "unknown")

    if _rag_graph is None:
        logger.error("call_rag_agent: RAG Graph 未加载")
        return {
            "agent_result": {
                "intent": "rag",
                "answer": "知识库服务暂不可用，请稍后重试。",
                "sources": [],
                "confidence": 0.0,
                "rejected": False,
            }
        }

    try:
        result = _rag_graph.invoke(
            {"query": query, "messages": []},
            config={"configurable": {"thread_id": f"{session_id}_rag"}},
        )
        agent_result = {
            "intent": "rag",
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "confidence": result.get("confidence", 0.0),
            "rejected": result.get("rejected", False),
        }
        logger.info(
            "call_rag_agent: session=%s, answer_len=%d, rejected=%s",
            session_id,
            len(agent_result["answer"]),
            agent_result["rejected"],
        )
        return {"agent_result": agent_result}
    except Exception:
        logger.exception("call_rag_agent: 调用失败")
        return {
            "agent_result": {
                "intent": "rag",
                "answer": "知识库服务调用失败，请稍后重试。",
                "sources": [],
                "confidence": 0.0,
                "rejected": False,
            }
        }


def call_data_agent(state: OrchestratorState) -> dict:
    """调用 Data Agent StateGraph。

    thread_id = ``{session_id}_data`` —— 与 RAG Agent 隔离。
    """
    query = state.get("query", "")
    session_id = state.get("session_id", "unknown")

    if _data_graph is None:
        logger.error("call_data_agent: Data Graph 未加载")
        return {
            "agent_result": {
                "intent": "data",
                "report": "数据分析服务暂不可用，请稍后重试。",
                "analysis_type": "",
                "sql_used": None,
            }
        }

    try:
        result = _data_graph.invoke(
            {"query": query, "messages": []},
            config={"configurable": {"thread_id": f"{session_id}_data"}},
        )
        agent_result = {
            "intent": "data",
            "report": result.get("report", ""),
            "analysis_type": result.get("analysis_type", ""),
            "sql_used": result.get("generated_sql", None),
        }
        logger.info(
            "call_data_agent: session=%s, report_len=%d",
            session_id,
            len(agent_result["report"]),
        )
        return {"agent_result": agent_result}
    except Exception:
        logger.exception("call_data_agent: 调用失败")
        return {
            "agent_result": {
                "intent": "data",
                "report": "数据分析服务调用失败，请稍后重试。",
                "analysis_type": "",
                "sql_used": None,
            }
        }


def format_result(state: OrchestratorState) -> dict:
    """统一封装结果节点。

    把 ``agent_result`` 中的字段打平到最终的 ``agent_result`` 中,
    确保 API 层可以统一读取 ``agent_result["intent"]``, ``agent_result["answer"]`` 等。
    此节点主要做日志记录和完整性检查。
    """
    agent_result = state.get("agent_result", {})
    logger.info("format_result: intent=%s, keys=%s", agent_result.get("intent"), list(agent_result.keys()))
    # 直接透传 agent_result,不做额外转换
    return {"agent_result": agent_result}


# =========================================================================
# Graph 构建与编译
# =========================================================================


def _build_graph() -> StateGraph:
    """构建编排层父图的 StateGraph(不编译)。"""
    builder = StateGraph(OrchestratorState)

    # 注册 4 个节点
    builder.add_node("classify_intent", classify_intent)
    builder.add_node("call_rag_agent", call_rag_agent)
    builder.add_node("call_data_agent", call_data_agent)
    builder.add_node("format_result", format_result)

    # START -> classify_intent
    builder.set_entry_point("classify_intent")

    # classify_intent -> route_to_agent(条件) -> call_rag_agent / call_data_agent
    builder.add_conditional_edges(
        "classify_intent",
        route_to_agent,
        {"call_rag_agent": "call_rag_agent", "call_data_agent": "call_data_agent"},
    )

    # call_rag_agent / call_data_agent -> format_result -> END
    builder.add_edge("call_rag_agent", "format_result")
    builder.add_edge("call_data_agent", "format_result")
    builder.add_edge("format_result", END)

    return builder


# 模块级: 编译 graph 对象(供 deps.py import)
try:
    _builder = _build_graph()
    graph = _builder.compile()
    logger.info("Orchestrator StateGraph 编译成功")
except Exception:
    logger.exception("Orchestrator StateGraph 编译失败")
    raise

__all__ = ["OrchestratorState", "graph"]
