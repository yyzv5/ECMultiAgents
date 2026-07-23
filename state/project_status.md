# 跨境电商多 Agent 系统 — 一期开发任务分配表

> **使用说明**：开发人员在对应任务的"状态"列填写 `未开始`、`开发中`、`已完成`。遇到阻塞请在"备注"列说明。

## M1: 项目骨架与配置中心

**目标**：搭建 FastAPI 应用框架，集中管理所有配置项，定义项目依赖。

| 任务编号 | 脚本路径                  | 任务描述              | 核心实现要点                                                 | 预估工时 | 状态     | 负责人 | 备注 |
| -------- | ------------------------- | --------------------- | ------------------------------------------------------------ | -------- | -------- | ------ | ---- |
| M1.1     | `src/backend/config.py`   | 创建配置中心          | ① 继承 `pydantic_settings.BaseSettings`，从 `.env.local` 和环境变量读取配置<br>② 必须包含文档第 3 节表格列出的所有 LLM、Milvus、Reranker、PG、Tavily、JWT、Checkpoint 配置项<br>③ 为 `MILVUS_HYBRID_TOP_K`、`RERANKER_TOP_K` 等提供合理默认值<br>④ 实例化全局单例 `settings` 供其他模块导入 | 0.25d    | ✅ 已完成 | 开发 Agent | 组长首轮验收发现 `PG_*` 键未迁移、单例类型断言 tautological、缺真实 `.env.local` 烟雾测试，已返修：经用户授权迁移 `DB_* → PG_*`；单例断言改为 `isinstance(settings, backend_config.Settings)`；新增 `TestProjectDotenv.test_project_dotenv_can_build_settings` 用真实 `.env.local` 加载并断言关键字段非空/为正。验收：`uv sync --dev`、`uv run pytest tests/test_config.py -v`、`uv run pytest -v` 均 46 passed 退出 0；`uv run python -c "from backend.config import settings; print('settings-loaded')"` 输出 `settings-loaded`；日志 `tests/logs/M1.1-config.{log,xml}`（本地，`.gitignore`）。最小 uv bootstrap 已并入本任务，M1.4 仍需补齐完整业务依赖。 |
| M1.2     | `src/backend/main.py`     | 创建 FastAPI 应用入口 | ① 创建 `FastAPI` 应用实例<br>② 使用 `app.include_router` 注册 `api/v1/router.py` 中的路由，设置前缀 `/v1`<br>③ 添加根路径 GET 接口 `/health`，返回 `{"status": "ok"}` | 0.25d    | ✅ 已完成 | 开发 Agent | 验收通过:49 passed,uvicorn三断言全过,AGENTS.md文档同步修复。 |
| M1.3     | `src/backend/api/deps.py` | 实现依赖注入          | ① 定义 `get_db` 函数，作为 FastAPI 的 `Depends`，创建并注入数据库会话，请求结束后自动关闭<br>② 使用 `functools.lru_cache` 为 `get_rag_graph`、`get_listing_graph`、`get_data_graph`、`get_orchestrator` 提供全局单例的懒加载<br>③ 需预先导入 M5 和 M6 对应构建函数，前期可先定义函数体为 `pass` | 0.25d    | ✅ 已完成 | 开发 Agent | 验收通过:55 passed(V1–V7全过),try/except ImportError占位,M5/M6/M4.3落地后自动接管。 |
| M1.4     | `requirements.txt`        | 编写项目依赖清单      | 列出所有必需的 Python 包及其推荐版本，包括但不限于：`fastapi`、`uvicorn`、`langgraph`、`langchain`、`langchain-openai`、`pymilvus`、`FlagEmbedding`、`pydantic-settings`、`sqlalchemy`、`psycopg2-binary`、`python-jose`、`bcrypt`、`tavily-python` 等 | 0.1d     | ✅ 已完成 | 开发 Agent |      |

---

## M2: 基础设施层

**目标**：封装 LLM、Milvus 和 JWT 的基础调用能力，为上层 Agent 模块提供稳定、统一的服务接口。

| 任务编号 | 脚本路径                            | 任务描述                             | 核心实现要点                                                 | 预估工时 | 状态     | 负责人 | 备注 |
| -------- | ----------------------------------- | ------------------------------------ | ------------------------------------------------------------ | -------- | -------- | ------ | ---- |
| M2.1     | `src/backend/core/llm_factory.py`   | 创建 LLM 工厂                        | ① 从 `config.py` 导入 `settings`<br>② 实现 `create_llm(model: str = None)` 函数<br>③ 根据传入的 `model`（`"deepseek"` / `"minimax"`）或默认值，返回对应的 `ChatOpenAI` 实例<br>④ 设置 `base_url`、`api_key`、`temperature`、`timeout` 等参数<br>⑤ 不支持的 `model` 值抛出 `ValueError` | 0.5d     | ✅ 已完成 | 开发 Agent | 62 passed（55 既有 + 7 新增）+ 2 烟雾测试 skipped（环境受限）；V1-V6 全过 |
| M2.2     | `src/backend/core/milvus_client.py` | 封装 Milvus 客户端与完整混合检索链路 | ① **初始化**：连接 Milvus 并检查/获取 Collection 对象<br>② **编码模块**：使用 `FlagEmbedding.BGEM3FlagModel` 加载模型，实现 `embed_query(text)` 和 `embed_documents(texts)` 方法，内部自动处理稀疏向量格式转换<br>③ **混合检索**：实现 `hybrid_search(query)` 方法，执行"稠密+稀疏混合检索 → WeightedRanker 融合 → `BGE-RERANKER-V2-M3` 精排 → Sigmoid 置信度计算"完整链路<br>④ **数据插入**：实现 `insert(docs)` 方法，接收文档列表，调用 `embed_documents` 编码后批量插入<br>⑤ **返回结果**：严格遵循文档 4.2.5 节定义的结构返回检索结果 | 1.5d     | ⬜ 未开始 |        |      |
| M2.3     | `src/backend/core/security.py`      | 实现 JWT 鉴权工具                    | ① 实现 `create_access_token(user_id: str)` → `str`，使用 `settings.JWT_SECRET_KEY` 和 `settings.JWT_EXPIRE_MINUTES` 签发 Token<br>② 实现 `verify_token(token: str)` → `dict`，校验 Token 有效性，失败则抛出 `HTTPException(401)`<br>③ 实现 `get_current_user(...)` FastAPI 依赖函数，从请求头 `Authorization: Bearer <token>` 提取并验证 Token，返回 `user_id` | 0.5d     | ⬜ 未开始 |        |      |

---

## M3: 工具层

**目标**：封装外部工具（搜索、数据库查询）为标准的 LangChain Tool，供 Agent 调用。

| 任务编号 | 脚本路径                             | 任务描述                 | 核心实现要点                                                 | 预估工时 | 状态     | 负责人 | 备注 |
| -------- | ------------------------------------ | ------------------------ | ------------------------------------------------------------ | -------- | -------- | ------ | ---- |
| M3.1     | `src/backend/core/tools/search.py`   | 封装 Tavily 联网搜索工具 | ① 使用 `@tool` 装饰器封装 `TavilySearchResults` 为 `web_search` 函数<br>② 函数接收 `query: str, max_results: int = 5` 作为输入<br>③ 返回搜索结果列表，列表元素需包含 `content` 和 `url` 字段 | 0.25d    | ⬜ 未开始 |        |      |
| M3.2     | `src/backend/core/tools/db_query.py` | 封装数据库查询工具       | ① 使用 `@tool` 装饰器封装 `db_query_tool` 函数<br>② **安全校验**：对传入 SQL 进行 `SELECT` 正则匹配，表名白名单校验（`product_sales`, `ad_performance`），不通过则返回错误信息<br>③ **执行逻辑**：使用数据库 session 执行 SQL，将结果格式化为 JSON 字符串（含列名和行数据）后返回<br>④ 使用 `try-except` 捕获所有异常并将异常信息作为字符串返回 | 0.25d    | ⬜ 未开始 |        |      |

---

## M4: 数据层

**目标**：定义数据库模型，实现鉴权和业务接口所需的数据库操作，并准备好演示用的初始化数据。

| 任务编号 | 脚本路径                        | 任务描述                               | 核心实现要点                                                 | 预估工时 | 状态     | 负责人 | 备注 |
| -------- | ------------------------------- | -------------------------------------- | ------------------------------------------------------------ | -------- | -------- | ------ | ---- |
| M4.1     | `src/backend/models/user.py`    | 定义用户 ORM 模型                      | ① 创建 SQLAlchemy `User` 模型，映射到 `users` 表<br>② 字段：`id` (Integer, PK), `username` (String, Unique), `hashed_password` (String), `created_at` (DateTime)<br>③ 实现 `hash_password(password: str)` 和 `verify_password(password: str, hashed: str)` 静态方法，使用 `bcrypt` | 0.25d    | ⬜ 未开始 |        |      |
| M4.2     | `src/backend/models/schemas.py` | 定义所有 API 的 Pydantic 请求/响应模型 | ① 定义 `RegisterRequest`, `LoginRequest`, `TokenResponse`<br>② 定义 `ChatRequest`, `ChatResponse`, `DataResponse`<br>③ 定义 `ListingAuditRequest`, `ListingAuditResponse`, `ResumeRequest`<br>④ 定义 `AuditIssue` 模型，包含 `field`, `rule`, `detail`, `suggestion` 字段<br>⑤ 为所有模型添加详细的 Field 描述 | 0.5d     | ⬜ 未开始 |        |      |
| M4.3     | `src/backend/db/session.py`     | 管理数据库会话                         | ① 使用 `sqlalchemy.create_engine` 创建同步引擎，连接字符串从 `settings` 拼接<br>② 创建 `SessionLocal` 工厂<br>③ 提供 `get_db` 的生成器实现，供 `api/deps.py` 导入和使用 | 0.25d    | ⬜ 未开始 |        |      |
| M4.4     | `src/backend/db/init_data.py`   | 初始化所有离线演示数据                 | ① **PG 数据**：使用 `Base.metadata.create_all` 建表，插入演示数据到 `product_sales` 和 `ad_performance` 表（至少 30 条，跨 3 个月，覆盖三个平台）<br>② **Milvus 数据**：调用 `MilvusClient` 创建 `knowledge_base` Collection（如不存在），定义 Schema 和索引，插入至少 20 条跨境运营知识文档<br>③ 设计为可独立运行的脚本：`python src/backend/db/init_data.py` | 0.75d    | ⬜ 未开始 |        |      |

---

## M5: Agent 模块

**目标**：使用 LangGraph 实现三个核心 Agent 的状态图逻辑。

| 任务编号 | 脚本路径                                    | 任务描述                         | 核心实现要点                                                 | 预估工时 | 状态     | 负责人 | 备注 |
| -------- | ------------------------------------------- | -------------------------------- | ------------------------------------------------------------ | -------- | -------- | ------ | ---- |
| M5.1     | `src/backend/agents/rag_agent/state.py`     | 定义 RAG Agent 的 State          | ① 继承 `TypedDict` 或使用 `Annotated` 定义文档 5.1.1 节表格中的所有字段<br>② 正确配置 `messages` 字段的 `add_messages` reducer | 0.25d    | ⬜ 未开始 |        |      |
| M5.2     | `src/backend/agents/rag_agent/graph.py`     | 构建 RAG Agent 的 StateGraph     | ① 实现 8 个节点：`query_rewrite`, `validate_question`, `hybrid_retrieval`, `check_confidence`, `web_search`, `merge_context`, `generate_answer`, `reject_answer`<br>② 组装图，实现文档 5.1.2 节描述的完整条件分支流程<br>③ 使用 `MemorySaver` 并绑定 SQLite 持久化（`settings.CHECKPOINT_DB_PATH`），实现多轮记忆<br>④ 导出编译后的 `graph` 对象 | 1.5d     | ⬜ 未开始 |        |      |
| M5.3     | `src/backend/agents/listing_agent/state.py` | 定义上架助手 Agent 的 State      | ① 继承 `TypedDict`，定义文档 5.2.1 节表格中的所有字段        | 0.25d    | ⬜ 未开始 |        |      |
| M5.4     | `src/backend/agents/listing_agent/graph.py` | 构建上架助手 Agent 的 StateGraph | ① 实现审核节点：`task_parse`, `title_check`, `image_check`, `variation_check`, `category_check`, `compliance_check`<br>② 实现流程节点：`aggregate`, `decide`, `auto_fix`, `do_listing`, `human_review`<br>③ 使用 `Send` API 并行调度 5 个审核节点<br>④ 在 `human_review` 节点使用 `interrupt()` 实现真正的人机协同中断<br>⑤ 导出编译后的 `graph` 对象 | 1.5d     | ⬜ 未开始 |        |      |
| M5.5     | `src/backend/agents/data_agent/state.py`    | 定义数据智能 Agent 的 State      | ① 继承 `TypedDict`，定义文档 5.3.1 节表格中的所有字段        | 0.25d    | ⬜ 未开始 |        |      |
| M5.6     | `src/backend/agents/data_agent/graph.py`    | 构建数据智能 Agent 的 StateGraph | ① 实现节点：`classify_analysis_type`, `predefined_report`, `extract_intent`, `text_to_sql`, `execute_sql`, `fix_sql`, `generate_report`, `error_response`<br>② 实现文档 5.3.2 节描述的流程，包含 SQL 生成的错误重试循环（最多 2 次）<br>③ 使用 `MemorySaver` 管理多轮对话<br>④ 导出编译后的 `graph` 对象 | 1.5d     | ⬜ 未开始 |        |      |

---

## M6: 编排层

**目标**：创建父级 LangGraph，实现意图识别与路由。

| 任务编号 | 脚本路径                           | 任务描述         | 核心实现要点                                                 | 预估工时 | 状态     | 负责人 | 备注 |
| -------- | ---------------------------------- | ---------------- | ------------------------------------------------------------ | -------- | -------- | ------ | ---- |
| M6.1     | `src/backend/core/orchestrator.py` | 构建编排层 Graph | ① 定义 `OrchestratorState`（参考文档 6.1 节）<br>② 实现意图识别节点 `classify_intent`，严格遵循"规则匹配优先 + LLM 兜底"的两阶段策略<br>③ 实现路由节点，根据 `intent` 字段将请求分别路由到 RAG、Listing 或 Data Agent<br>④ 为 RAG 和 Data Agent 管理独立的 `thread_id`，确保会话隔离<br>⑤ 导出编译后的编排层 `graph` 对象 | 1d       | ⬜ 未开始 |        |      |

---

## M7: API 路由层

**目标**：实现所有对外的 RESTful API 接口，连接请求、鉴权和 Agent 逻辑。

| 任务编号 | 脚本路径                                     | 任务描述             | 核心实现要点                                                 | 预估工时 | 状态     | 负责人 | 备注 |
| -------- | -------------------------------------------- | -------------------- | ------------------------------------------------------------ | -------- | -------- | ------ | ---- |
| M7.1     | `src/backend/api/v1/__init__.py`             | 创建包文件           | 空文件或包声明                                               | 0d       | ⬜ 未开始 |        |      |
| M7.2     | `src/backend/api/v1/router.py`               | 聚合所有 v1 子路由   | ① 创建 `APIRouter` 实例<br>② 使用 `include_router` 将 `auth.router`、`rag.router`、`listing.router`、`data_insight.router` 挂载到此路由下，设置合适的前缀 | 0.25d    | ⬜ 未开始 |        |      |
| M7.3     | `src/backend/api/v1/auth.py`                 | 实现注册/登录接口    | ① 实现 `POST /register`，接收 `RegisterRequest`，创建用户并返回成功信息<br>② 实现 `POST /login`，接收 `LoginRequest`，校验密码，调用 `create_access_token` 并返回 `TokenResponse` | 0.5d     | ⬜ 未开始 |        |      |
| M7.4     | `src/backend/api/v1/rag.py`                  | 实现统一对话接口     | ① 实现 `POST /chat`<br>② 从 `deps` 注入编排层 Graph<br>③ 接收 `ChatRequest`，以 `query` 和 `session_id` 为输入，执行编排图<br>④ 将结果格式化为 `ChatResponse` 返回 | 0.5d     | ⬜ 未开始 |        |      |
| M7.5     | `src/backend/api/v1/listing.py`              | 实现上架助手相关接口 | ① 实现 `POST /listing/audit`，注入 Listing Graph，接收 `ListingAuditRequest`，执行审核流程<br>② 在遇到 `interrupt` 时，返回 `ListingAuditResponse` 且状态为 `pending_human_review`<br>③ 实现 `POST /listing/audit/{task_id}/resume`，接收 `ResumeRequest`，使用 LangGraph `Command` 恢复指定 `task_id` 的执行 | 0.75d    | ⬜ 未开始 |        |      |
| M7.6     | `src/backend/api/v1/data_insight.py`         | 实现数据分析接口     | ① 实现 `POST /data/analyze`<br>② 注入 Data Agent Graph<br>③ 接收请求，执行 Data Graph，返回 `DataResponse` | 0.25d    | ⬜ 未开始 |        |      |
| M7.7     | `src/backend/prompts/` 下所有 `*_prompts.py` | 整理所有 Prompt 模板 | ① `rag_prompts.py`：查询改写、问题校验、答案生成等 Prompt<br>② `listing_prompts.py`：各审核维度的通用指令及 Amazon、Shopee、AliExpress 的平台特定规则<br>③ `data_prompts.py`：意图分类、SQL 生成、报告生成等 Prompt<br>④ 所有 Prompt 均以字符串常量形式定义 | 0.5d     | ⬜ 未开始 |        |      |

---

## 开发规范提醒

| 规范项   | 要求                                                        |
| -------- | ----------------------------------------------------------- |
| 编码风格 | 遵循 PEP 8，使用 type hints                                 |
| 错误处理 | 所有外部调用（LLM、Milvus、PG）必须有 try-except 和日志记录 |
| 日志     | 使用 Python `logging` 模块，关键节点打印日志                |
| 可测试性 | 每个 Agent Graph 可独立运行测试，不依赖 FastAPI             |
| 阻塞上报 | 遇到阻塞时在"备注"列说明原因和需要的支持，同步到项目群      |
