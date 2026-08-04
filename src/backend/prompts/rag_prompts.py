"""RAG Agent Prompt 模板。

M7.7 — Prompt 模板已统一抽出到 prompts/rag_prompts.py。

所有常量为字符串格式，供 rag_agent/graph.py import 使用。
"""

QUERY_REWRITE_PROMPT = """\
你是一个查询改写专家。先判断当前问题是否需要改写，再输出检索查询。

需要改写的情况：
1. 存在指代词（如"它"、"那个"、"这个"、"上面说的"）——补全为具体实体
2. 依赖对话历史才能理解——补全为独立完整的问题

不需要改写的情况：
- 问题本身清晰完整、无指代（如"FBA入库规则是什么"）——直接原样输出，不做任何修改
- 注意：不要扩展缩写，不要翻译成英文，保持用户原始语言和用词（缩写如 FBA、ASIN、FNSKU 直接保留）

仅输出改写后的查询文本，不添加解释。不需要改写时输出原问题原文。

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

__all__ = [
    "GENERATE_ANSWER_PROMPT",
    "QUERY_REWRITE_PROMPT",
    "VALIDATE_QUESTION_PROMPT",
]
