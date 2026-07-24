"""Data Agent Prompt 模板。

M7.7 — Prompt 模板已统一抽出到 prompts/data_prompts.py。

所有常量为字符串格式，供 data_agent/graph.py import 使用。
"""

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

__all__ = [
    "CLASSIFY_ANALYSIS_TYPE_PROMPT",
    "ERROR_RESPONSE_PROMPT",
    "EXTRACT_INTENT_PROMPT",
    "FIX_SQL_PROMPT",
    "GENERATE_REPORT_PROMPT",
    "TEXT_TO_SQL_PROMPT",
]
