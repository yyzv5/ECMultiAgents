## 跨境电商多 Agent 系统 — 一期开发文档

### 1. 项目概述

本项目是一个跨境电商多 Agent 系统，用于面试演示。一期实现三个核心模块：
- **智能问答 RAG**：内部知识库问答（支持多轮对话记忆，稠密+稀疏混合检索）
- **上架助手**：多平台 Listing 并行审核与合规检查（支持真正的人机协同中断）
- **数据智能**：自然语言驱动的数据分析（支持多轮对话记忆）

技术栈：Python + FastAPI + LangGraph + LangChain + Milvus 2.4+ + PostgreSQL

---

### 2. 项目结构

```
src/
├── backend/
│   ├── config.py                  # 配置中心（Pydantic Settings）
│   ├── main.py                    # FastAPI 应用入口
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                # 依赖注入
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py          # 聚合所有子路由
│   │       ├── auth.py            # 注册/登录/Token
│   │       ├── rag.py             # 智能问答接口
│   │       ├── listing.py         # 上架助手接口（含 resume 端点）
│   │       └── data_insight.py    # 数据智能接口
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py            # JWT 生成与校验
│   │   ├── llm_factory.py         # LLM 工厂
│   │   ├── milvus_client.py       # Milvus 封装（混合检索 + 重排 + 置信度）
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── search.py          # Tavily 联网搜索
│   │   │   └── db_query.py        # 数据库查询
│   │   └── orchestrator.py        # 编排层：父图 + 意图识别 + 路由
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── rag_agent/
│   │   │   ├── __init__.py
│   │   │   ├── graph.py           # RAG Agent StateGraph
│   │   │   └── state.py           # RAG Agent State
│   │   ├── listing_agent/
│   │   │   ├── __init__.py
│   │   │   ├── graph.py           # 上架助手 StateGraph
│   │   │   └── state.py           # 上架助手 State
│   │   └── data_agent/
│   │       ├── __init__.py
│   │       ├── graph.py           # 数据智能 StateGraph
│   │       └── state.py           # 数据智能 State
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py                # 用户 ORM 模型
│   │   └── schemas.py             # Pydantic 请求/响应模型
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py             # SQLAlchemy session 管理
│   │   └── init_data.py           # 离线数据初始化（含 Milvus Schema 创建）
│   └── prompts/
│       ├── __init__.py
│       ├── rag_prompts.py         # RAG 相关 Prompt
│       ├── listing_prompts.py     # 上架检查 Prompt（按平台拆分）
│       └── data_prompts.py        # 数据分析 Prompt
├── .env.local                     # 本地环境变量（不入 Git）
└── requirements.txt
```

---

### 3. 配置中心 `config.py`

采用 Pydantic Settings，所有可调参数集中管理，支持环境变量覆盖。

**配置项清单：**

| 分类 | 配置项 | 类型 | 默认值 | 说明 |
|------|--------|------|--------|------|
| LLM | `DEEPSEEK_BASE_URL` | str | — | DeepSeek API 地址 |
| LLM | `DEEPSEEK_API_KEY` | str | — | DeepSeek API Key |
| LLM | `MINIMAX_BASE_URL` | str | — | MiniMax API 地址 |
| LLM | `MINIMAX_API_KEY` | str | — | MiniMax API Key |
| LLM | `DEFAULT_LLM` | str | `"deepseek"` | 默认使用的 LLM |
| LLM | `LLM_TIMEOUT` | int | `30` | LLM 调用超时（秒） |
| Milvus | `MILVUS_HOST` | str | — | Milvus 主机地址 |
| Milvus | `MILVUS_PORT` | int | — | Milvus 端口 |
| Milvus | `MILVUS_COLLECTION` | str | `"knowledge_base"` | 知识库 Collection 名 |
| Milvus | `MILVUS_HYBRID_TOP_K` | int | `20` | 混合检索粗召回数量 |
| Milvus | `MILVUS_DENSE_WEIGHT` | float | `0.7` | 稠密向量融合权重 |
| Milvus | `MILVUS_SPARSE_WEIGHT` | float | `0.3` | 稀疏向量融合权重 |
| Reranker | `RERANKER_TOP_K` | int | `5` | 精排后保留数量 |
| Reranker | `CONFIDENCE_FALLBACK_THRESHOLD` | float | `0.6` | 低于此值触发联网搜索补充 |
| Reranker | `CONFIDENCE_UNRELIABLE_THRESHOLD` | float | `0.4` | 低于此值标记"可能不准确" |
| PG | `PG_HOST` / `PG_PORT` / `PG_USER` / `PG_PASSWORD` / `PG_DATABASE` | — | — | PostgreSQL 连接参数 |
| Tavily | `TAVILY_API_KEY` | str | — | Tavily 搜索 API Key |
| JWT | `SECRET_KEY` | str | — | JWT 签名密钥 |
| JWT | `JWT_ALGORITHM` | str | `"HS256"` | JWT 算法 |
| JWT | `JWT_EXPIRE_MINUTES` | int | `1440` | Token 过期时间（分钟） |
| Checkpoint | `CHECKPOINT_DB_PATH` | str | `"data/checkpoints.db"` | SQLite 持久化路径 |

**实现方式：**

使用 `pydantic-settings` 的 `BaseSettings`，自动从 `.env.local` 读取。环境变量名与配置项名一一对应。

---

### 4. 基础设施层

#### 4.1 LLM 工厂 (`core/llm_factory.py`)

**职责：** 统一管理 LLM 实例的创建，支持 DeepSeek 和 MiniMax 两个提供商。

**实现要点：**
- 接收 `model` 参数（`"deepseek"` 或 `"minimax"`），不传则使用 `DEFAULT_LLM`
- 返回 `ChatOpenAI` 实例，设置超时时间从 `LLM_TIMEOUT` 读取
- DeepSeek 模型名 `deepseek-v4-flash`（由 `DEEPSEEK_MODEL` 配置），MiniMax 模型名 `Minimax-M3`（由 `MINIMAX_MODEL` 配置）
- 支持 `thinking_mode: bool = False` 参数（默认关闭），启用时传递提供商特定的「思考模式」参数
- 不支持的 model 值抛出 `ValueError`

#### 4.2 Milvus 客户端 (`core/milvus_client.py`)

这是本次调整的核心模块。采用 **BGE-M3 双向量编码 + Milvus Hybrid Search + WeightedRanker + Reranker 精排 + Sigmoid 置信度** 的完整检索链路。

---

##### 4.2.1 总体检索架构

```
用户 Query
    │
    ▼
BGE-M3 同时编码 ──→ 稠密向量 dense_vec (1024维)
    │            ──→ 稀疏向量 sparse_vec ({token_id: weight})
    │
    ▼
Milvus Hybrid Search
    ├── AnnSearchRequest(dense_vector, IP, top_k=HYBRID_TOP_K)
    ├── AnnSearchRequest(sparse_vector, IP, top_k=HYBRID_TOP_K)
    └── WeightedRanker(DENSE_WEIGHT=0.7, SPARSE_WEIGHT=0.3)
    │
    ▼
粗召回结果（默认 20 条，含融合分数）
    │
    ▼
BGE-RERANKER-V2-M3 精排
    └── 对每条 (query, doc_text) 计算相关性 logits
    │
    ▼
Sigmoid(logits) → 置信度 (0~1)
    │
    ▼
取 top_k=RERANKER_TOP_K（默认 5）条
    │
    ▼
返回：[{text, source, hybrid_score, confidence}, ...]
```

##### 4.2.2 Milvus Collection Schema

Collection 名：`knowledge_base`（由 `MILVUS_COLLECTION` 配置）

| 字段名 | 数据类型 | 说明 |
|--------|----------|------|
| `id` | `INT64` | 主键，自动生成 |
| `text` | `VARCHAR(65535)` | 文档原文 |
| `source` | `VARCHAR(255)` | 文档来源标识（如 `platform_rules`、`internal_process`） |
| `dense_vector` | `FLOAT_VECTOR(1024)` | BGE-M3 稠密向量，维度 1024 |
| `sparse_vector` | `SPARSE_FLOAT_VECTOR` | BGE-M3 稀疏向量 |

**索引配置：**

| 向量字段 | 索引类型 | 度量方式 | 参数 |
|----------|----------|----------|------|
| `dense_vector` | `IVF_FLAT` | `IP`（内积） | `nlist=128` |
| `sparse_vector` | `SPARSE_INVERTED_INDEX` | `IP` | Milvus 默认参数 |

> **版本要求：** `SPARSE_FLOAT_VECTOR` 类型需要 Milvus 2.4.0 及以上。需确认本地 Milvus 版本。

##### 4.2.3 BGE-M3 编码模块

**使用方式：**

采用 `FlagEmbedding` 库的 `BGEM3FlagModel` 类。一次 `encode` 调用同时输出稠密向量和稀疏向量。

**关键参数：**
- `return_dense=True`：返回稠密向量
- `return_sparse=True`：返回稀疏词表权重（`lexical_weights`，格式为 `{token_id: weight}`）

**稀疏向量转换：**

BGE-M3 输出的 `lexical_weights` 是 Python dict，Milvus 要求的稀疏向量格式为 `{"indices": [...], "values": [...]}`。客户端内部完成此转换，对外透明。

**批量编码：**

初始化知识库时需要对大量文档进行编码。`BGEM3FlagModel.encode` 原生支持列表输入，一次传入所有文本即可批量生成稠密和稀疏向量。

##### 4.2.4 混合检索方法

使用 Milvus 2.4+ 的 `hybrid_search` API。

**调用步骤：**
1. 构建两个 `AnnSearchRequest`，分别指向 `dense_vector` 和 `sparse_vector` 字段
2. 稠密搜索使用 `IVF_FLAT` + `IP` 度量，`nprobe=10`
3. 稀疏搜索使用 `SPARSE_INVERTED_INDEX` + `IP` 度量
4. 创建 `WeightedRanker`，权重从 `MILVUS_DENSE_WEIGHT` 和 `MILVUS_SPARSE_WEIGHT` 读取
5. 调用 `collection.hybrid_search(reqs=[req_dense, req_sparse], rerank=ranker, limit=top_k, output_fields=["text", "source"])`
6. 返回结果列表，每条包含 `text`、`source`、`score`（WeightedRanker 融合分数）

**融合分数说明：**

`WeightedRanker` 返回的分数是 `0.7 * dense_score + 0.3 * sparse_score` 的加权和。由于两路搜索的度量都是 IP（内积），分数范围可能不一致。Milvus 在加权前会对两路分数做归一化处理，确保权重有意义。

##### 4.2.5 Reranker 精排与置信度

**精排流程：**

1. 取混合检索返回的 top_k 条结果的 `text` 字段
2. 将原始 query 与每条 `text` 组成 pair 列表：`[[query, doc1_text], [query, doc2_text], ...]`
3. 调用 `FlagReranker.compute_score(pairs)`，返回 logits 列表
4. 将 logits 通过 Sigmoid 函数映射为 0~1 区间的置信度
5. 按置信度降序排列，取前 `RERANKER_TOP_K` 条

**Sigmoid 映射：**

```
confidence = 1 / (1 + exp(-logit))
```

这是标准的 logits→概率映射方式。例如：logit=2.0 → confidence≈0.88，logit=0 → confidence=0.5，logit=-1.0 → confidence≈0.27。

**置信度用途：**

| 场景 | 阈值 | 动作 |
|------|------|------|
| `confidence >= 0.6` | 正常 | 直接使用检索结果，前端展示置信度 |
| `0.4 <= confidence < 0.6` | 偏低 | 触发联网搜索补充，合并后给 LLM；前端标注"置信度偏低，已补充网络搜索" |
| `confidence < 0.4` | 不可靠 | 触发联网搜索兜底，前端标注"内部知识库未找到高匹配内容，以下来自网络搜索"；如联网结果也不理想，告知用户"问题可能超出知识范围" |

**返回结果结构：**

```python
[
    {
        "text": "FBA入库要求：商品必须贴有FBA标签...",
        "source": "platform_rules",
        "hybrid_score": 0.82,        # WeightedRanker 融合分数
        "rerank_logit": 3.2,         # Reranker 原始 logits
        "confidence": 0.96           # Sigmoid 映射后的置信度
    },
    ...
]
```

##### 4.2.6 MilvusClient 对外接口

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `embed_query(text)` | `text: str` | `(dense_vec, sparse_vec)` | 编码单条 query，返回稠密+稀疏向量 |
| `embed_documents(texts)` | `texts: list[str]` | `(dense_vecs, sparse_vecs)` | 批量编码文档，用于初始化写入 |
| `hybrid_search(dense_vec, sparse_vec)` | 双向量 + `top_k` | `list[dict]` | 混合检索 + 重排 + 置信度，完整链路 |
| `insert(docs)` | `docs: list[dict]` | — | 批量插入文档（含双向量编码） |

#### 4.3 联网搜索 Tool (`core/tools/search.py`)

**职责：** 按需调用 Tavily 进行联网搜索，封装为 LangChain Tool。

**触发条件（不由 Tool 自身判断，由 RAG Graph 中的逻辑控制）：**
1. 问题无需走 RAG 流程（如时效性问题）→ 直接调用
2. RAG 检索结果置信度低于阈值 → 作为补充调用

**实现要点：**
- 封装 `TavilySearchResults` 为 `@tool` 装饰的函数
- 输入：`query: str`、`max_results: int = 5`
- 输出：搜索结果列表，每条含 `content`、`url`

#### 4.4 数据库查询 Tool (`core/tools/db_query.py`)

**职责：** 执行 SELECT 查询，供数据智能 Agent 使用。封装为 LangChain Tool。

**安全措施：**
- 仅允许 `SELECT` 语句（正则校验）
- 表名白名单：`product_sales`、`ad_performance`
- 返回 JSON 格式的列名和行数据
- 异常捕获并返回错误信息

#### 4.5 JWT 鉴权 (`core/security.py`)

**职责：** 用户身份认证，保护业务接口。

**实现要点：**
- 使用 `python-jose` 生成和校验 JWT
- `create_access_token(user_id)` 生成 Token，过期时间由 `JWT_EXPIRE_MINUTES` 控制
- `verify_token(token)` 校验 Token 有效性，无效抛出 401
- `get_current_user` 作为 FastAPI Depends，从 `Authorization: Bearer <token>` 中提取 user_id

#### 4.6 用户模型 (`models/user.py`)

**字段：** `id`（自增主键）、`username`（唯一）、`hashed_password`、`created_at`

密码使用 `bcrypt` 哈希存储。

#### 4.7 业务数据表与演示数据 (`db/init_data.py`)

**职责：** 初始化演示环境所需的一切数据，包括：
1. PostgreSQL 业务表建表（`product_sales`、`ad_performance`）并插入演示数据（至少 30 条，跨 3 个月，覆盖三个平台）
2. Milvus Collection 创建（含 Schema + 双索引）+ 插入至少 20 条跨境运营知识文档

**Milvus 初始化细节：**
- 先检查 Collection 是否存在，不存在则创建
- Schema 包含 5 个字段（id、text、source、dense_vector、sparse_vector）
- 分别对 dense_vector 和 sparse_vector 创建索引
- 加载 Collection 到内存
- 使用 `embed_documents` 批量编码文档，同时获取稠密和稀疏向量
- 一次性批量插入
- `flush` 确保数据持久化

---

### 5. 三个 Agent 的 LangGraph 定义

#### 5.1 智能问答 RAG Agent (`agents/rag_agent/`)

##### 5.1.1 State 定义

| 字段 | 类型 | 说明 |
|------|------|------|
| `query` | `str` | 当前用户输入 |
| `messages` | `list[dict]` | 多轮对话历史（LangGraph `add_messages` reducer） |
| `rewritten_query` | `str` | Query 改写结果 |
| `retrieved_docs` | `list[dict]` | 混合检索粗召回结果 |
| `reranked_docs` | `list[dict]` | 精排后结果（含置信度） |
| `web_results` | `list[dict]` | 联网搜索结果 |
| `context` | `str` | 合并后的 LLM 上下文 |
| `is_valid` | `bool` | 是否为有效跨境运营问题 |
| `need_web` | `bool` | 是否需要联网搜索 |
| `answer` | `str` | 最终回答 |
| `sources` | `list[str]` | 引用来源 |
| `rejected` | `bool` | 是否为拒绝回答 |
| `confidence` | `float` | 检索置信度（取最高值） |

##### 5.1.2 Graph 流程

```
START
    │
    ▼
query_rewrite（LLM 补全指代、扩展缩写）
    │
    ▼
validate_question（LLM 判断是否有效跨境运营问题）
    │
    ├── [无效] → reject_answer → END
    │
    └── [有效]
        │
        ▼
    hybrid_retrieval（混合检索 + 重排 + 置信度）
        │
        ▼
    check_confidence（判断置信度）
        │
        ├── [confidence >= 0.6] → merge_context（仅用内部知识）→ generate_answer → END
        │
        └── [confidence < 0.6] → web_search（联网补充）
                │
                ▼
            merge_context（合并内部知识 + 联网结果）→ generate_answer → END
```

**关键变化说明：**

相比常见的 "先检索再联网" 或 "检索联网并行" 模式，本设计采用 **"先检索、看置信度、按需联网"** 的串行策略，原因是：
- 大部分内部知识库问题置信度足够，无需联网
- 联网搜索有延迟和 API 消耗
- 先检索拿到置信度后，可以在 Prompt 中告知 LLM "内部知识库置信度偏低，以下联网结果仅作参考"，让 LLM 更好地融合信息

##### 5.1.3 各节点职责

| 节点 | 职责 | 输入 | 输出 |
|------|------|------|------|
| `query_rewrite` | 基于历史补全指代、扩展缩写，生成独立检索查询 | `query` + `messages` | `rewritten_query` |
| `validate_question` | 判断是否属于跨境运营相关问题 | `query` | `is_valid`（bool） |
| `hybrid_retrieval` | 完整检索链路：BGE-M3 编码 → Hybrid Search → Reranker 精排 → Sigmoid 置信度 | `rewritten_query` | `reranked_docs`（含 confidence）、`confidence`（最高值） |
| `check_confidence` | 判断是否需要联网补充 | `confidence` | `need_web`（bool） |
| `web_search` | 按需调用 Tavily | `rewritten_query` | `web_results` |
| `merge_context` | 拼接知识库结果、联网结果（如有）、对话历史 | `reranked_docs` + `web_results` + `messages` | `context` |
| `generate_answer` | LLM 基于上下文生成回答 | `context` + `query` | `answer` + `sources` |
| `reject_answer` | 返回礼貌拒绝 | — | `answer` + `rejected=True` |

##### 5.1.4 Query 改写 Prompt 模板

```
你是一个查询改写专家。基于对话历史，将用户的当前问题改写为独立完整的检索查询。
要求：
1. 补全指代词（如"它"、"那个"→具体实体）
2. 扩展缩写（如"FBA"→"Fulfillment by Amazon"）
3. 保留原问题核心意图
4. 仅输出改写后的查询文本，不添加解释

对话历史：
{history}

当前问题：{query}

改写后的查询：
```

##### 5.1.5 问题有效性校验 Prompt 模板

```
判断以下问题是否与跨境电商运营相关。
相关领域包括：平台规则、物流报关、内部流程、运营知识、Listing上架、广告投放、数据分析等。
如果是问候、闲聊或完全无关的问题，返回 false。
仅返回 true 或 false。

问题：{query}
```

##### 5.1.6 回答生成 Prompt 模板

```
你是跨境电商运营助手。请根据以下参考资料回答用户问题。

要求：
1. 基于参考资料回答，不要编造
2. 如果参考资料不足以回答，明确告知用户
3. 回答末尾注明引用来源
4. 如果知识库置信度偏低但已补充网络搜索结果，需在回答中提示"部分信息来自网络搜索，请核实后使用"

参考资料：
{context}

用户问题：{query}
```

##### 5.1.7 多轮记忆

通过 LangGraph 的 `MemorySaver`（SQLite 持久化）实现，`thread_id` 作为会话标识。`messages` 字段使用 `add_messages` reducer 自动累积历史。

---

#### 5.2 上架助手 Agent (`agents/listing_agent/`)

##### 5.2.1 State 定义

核心字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `platform` | `str` | 目标平台（Amazon / Shopee / AliExpress） |
| `title` | `str` | 商品标题 |
| `image_urls` | `list[str]` | 图片链接列表 |
| `variations` | `list[dict]` | 变体信息 |
| `category` | `str` | 类目 |
| `attributes` | `dict` | 属性键值对 |
| `audit_results` | `dict[str, list[AuditIssue]]` | 5 个维度的审核结果 |
| `all_issues` | `list[AuditIssue]` | 汇总的所有问题 |
| `passed` | `bool` | 是否全部通过 |
| `need_human_review` | `bool` | 是否需要人工介入 |
| `human_feedback` | `str` | 人工反馈 |
| `human_decision` | `str` | 人工决定（approve / reject / modify） |

##### 5.2.2 Graph 流程

```
START → task_parse
    → (并行 5 路) title_check / image_check / variation_check / category_check / compliance_check
    → aggregate → decide
    → [passed] → do_listing → END
    → [failed + 可自动修复] → auto_fix → do_listing → END
    → [failed + 需人工] → human_review(interrupt) → resume → END
```

##### 5.2.3 并行审核

5 个审核节点通过 LangGraph 的 `Send` API 并行调度，各自独立调用 LLM，互不阻塞。

##### 5.2.4 HitL 中断与恢复

- 在 `human_review` 节点触发 `graph.interrupt()`
- 前端展示违规详情，等待人工决定
- 恢复时使用 `Command(resume={"human_decision": "...", "human_feedback": "..."})` 继续执行

##### 5.2.5 平台规则

按平台维护在 `prompts/listing_prompts.py`，每个审核节点的 System Prompt = 通用指令 + 平台特定规则片段。本期覆盖 Amazon、Shopee、AliExpress 三个平台。

---

#### 5.3 数据智能 Agent (`agents/data_agent/`)

此模块本期不做架构调整，与初版文档保持一致。

##### 5.3.1 State 定义

核心字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `query` | `str` | 用户输入 |
| `messages` | `list[dict]` | 多轮对话历史 |
| `analysis_type` | `str` | 分析类型（weekly_report / monthly_report / free_analysis） |
| `extracted_intent` | `str` | 自由分析中提取的分析意图 |
| `generated_sql` | `str` | LLM 生成的 SQL |
| `sql_result` | `dict` | SQL 执行结果 |
| `sql_error` | `str` | SQL 执行错误信息 |
| `retry_count` | `int` | 重试次数 |
| `max_retries` | `int` | 最大重试次数（2） |
| `report` | `str` | 最终分析报告 |

##### 5.3.2 Graph 流程

```
START → classify_analysis_type
    → [预定义报告] → predefined_report → generate_sql_template → execute_sql → generate_report → END
    → [自由分析] → extract_intent → text_to_sql → execute_sql
        → [成功] → generate_report → END
        → [失败 & retry < 2] → fix_sql → execute_sql（循环）
        → [失败 & retry >= 2] → error_response → END
```

##### 5.3.3 重试循环

通过 LangGraph 的 `conditional_edges` 实现：`execute_sql` 后检查 `sql_error`，有错误且未超重试次数则回到 `fix_sql`，否则走向 `generate_report` 或 `error_response`。

---

### 6. 编排层 — 父级 LangGraph (`core/orchestrator.py`)

编排层本身也是一个 LangGraph，负责意图识别 + 路由到子 Agent。

##### 6.1 State 定义

| 字段 | 类型 | 说明 |
|------|------|------|
| `query` | `str` | 用户输入 |
| `history` | `list[dict]` | 对话历史 |
| `intent` | `str` | 识别的意图（rag / listing / data） |
| `confidence` | `float` | 意图识别置信度 |
| `agent_input` | `dict` | 传给子 Agent 的输入参数 |
| `agent_result` | `dict` | 子 Agent 返回的结果 |

##### 6.2 意图识别策略

**两阶段识别：规则优先 + LLM 兜底**

1. **规则匹配（优先）：** 关键词/正则快速命中
   - 含"上架"、"listing"、"审核"、"合规"、"标题规范"等 → `listing`
   - 含"销量"、"报表"、"数据"、"分析"、"周报"、"月报"等 → `data`
   - 含"FBA"、"规则"、"流程"、"怎么"、"什么是"、"SOP"等 → `rag`

2. **LLM 分类（兜底）：** 规则未命中时，调用 LLM 分类
   - 输出 `{"intent": "rag|listing|data", "confidence": 0.0~1.0}`
   - 低于 0.7 默认走 RAG

##### 6.3 子 Agent 路由

| 意图 | 路由目标 | 构造方式 |
|------|----------|----------|
| `rag` | RAG Graph | 传入 `query` + `session_id`（thread_id），由 RAG Graph 内部管理记忆 |
| `listing` | Listing Graph | 从 query 中解析平台 + 商品信息，构造 `ListingState` |
| `data` | Data Graph | 传入 `query` + `session_id`，由 Data Graph 内部管理记忆 |

##### 6.4 会话隔离

RAG 和 Data Agent 各自维护独立的 `MemorySaver` 和 `thread_id`，确保多轮对话上下文不串扰。

---

### 7. API 路由设计

#### 7.1 鉴权接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/auth/register` | 注册（username + password） |
| POST | `/v1/auth/login` | 登录，返回 JWT token |

#### 7.2 业务接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/chat` | 统一对话入口（编排层路由） |
| POST | `/v1/listing/audit` | 上架审核 |
| POST | `/v1/listing/audit/{task_id}/resume` | 人工审核后恢复 |
| POST | `/v1/data/analyze` | 数据分析（直接调用 Data Agent） |

#### 7.3 `POST /v1/chat` 请求/响应

**请求体：**
```json
{
    "query": "FBA入库有什么尺寸要求？",
    "session_id": "uuid-string"
}
```

**响应体（正常）：**
```json
{
    "code": 0,
    "data": {
        "intent": "rag",
        "answer": "FBA标准件外箱尺寸不超过63.5cm...",
        "sources": ["平台规则 - FBA入库要求"],
        "confidence": 0.92,
        "rejected": false
    }
}
```

**响应体（拒绝）：**
```json
{
    "code": 0,
    "data": {
        "intent": "rag",
        "answer": "抱歉，这个问题与跨境电商运营无关，我无法回答。",
        "rejected": true
    }
}
```

#### 7.4 上架审核接口

**请求：** `POST /v1/listing/audit`
```json
{
    "platform": "Amazon",
    "title": "Wireless Bluetooth Earbuds Pro with Active Noise Cancellation, Deep Bass, Black",
    "image_urls": ["https://..."],
    "variations": [{"color": "Black", "size": "One Size"}],
    "category": "Electronics",
    "attributes": {"brand": "SoundMax"}
}
```

**响应（需人工审核）：**
```json
{
    "code": 0,
    "data": {
        "status": "pending_human_review",
        "task_id": "uuid-xxx",
        "issues": [
            {
                "field": "title",
                "rule": "字符超限",
                "detail": "当前 85 字符，Amazon 限制 75 字符（非 Media 类目）",
                "suggestion": "建议删减为：Wireless Earbuds Pro with ANC, Black"
            }
        ]
    }
}
```

**恢复：** `POST /v1/listing/audit/{task_id}/resume`
```json
{
    "human_decision": "modify",
    "human_feedback": "标题改为：Wireless Earbuds Pro with ANC, Black"
}
```

#### 7.5 数据分析接口

**请求：** `POST /v1/data/analyze`
```json
{
    "query": "我负责的蓝牙耳机在各平台近3个月销量趋势怎么样？",
    "session_id": "uuid-string"
}
```

**响应：**
```json
{
    "code": 0,
    "data": {
        "analysis_type": "free_analysis",
        "report": "根据查询结果，蓝牙耳机近3个月...",
        "sql_used": "SELECT platform, SUM(sales) ..."
    }
}
```

---

### 8. 依赖注入 (`api/deps.py`)

**职责：** 管理全局单例和请求级资源。

| 依赖 | 作用域 | 说明 |
|------|--------|------|
| `get_db` | 请求级 | 每次请求获取新的数据库 session，请求结束关闭 |
| `get_rag_graph` | 全局单例 | 使用 `@lru_cache` 缓存，只构建一次 |
| `get_listing_graph` | 全局单例 | 同上 |
| `get_data_graph` | 全局单例 | 同上 |
| `get_orchestrator` | 全局单例 | 同上 |

---

### 9. 开发任务拆解与工时预估

| 编号 | 任务 | 内容 | 预估工时 |
|------|------|------|------|
| T1 | 项目骨架 | FastAPI 入口 + 路由注册 + deps + requirements.txt | 0.5d |
| T2 | 配置中心 | `config.py` + `.env.local`，包含所有新增检索参数 | 0.25d |
| T3 | LLM 工厂 | DeepSeek/MiniMax 统一封装 | 0.5d |
| T4 | Milvus 客户端 | BGE-M3 双向量编码 + Hybrid Search + Reranker 精排 + Sigmoid 置信度 | 1.5d |
| T5 | 工具层 | Tavily 搜索 Tool + DB 查询 Tool | 0.5d |
| T6 | JWT 鉴权 | 用户表 + 注册/登录 API | 1d |
| T7 | 数据初始化 | PG 假数据 + Milvus Schema 创建 + 知识库文档初始化 | 0.75d |
| T8 | RAG Agent | StateGraph：