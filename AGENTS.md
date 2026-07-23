# ECMultiAgents项目导航

> 本文件是 AI 进入项目后**第一个必须读的文件**。
> 不读完本文件,禁止动代码。

---

## 1. 项目描述

跨境电商多Agent项目，用于面试演示。一期实现三个核心模块：
- **智能问答 RAG**：内部知识库问答（多轮对话记忆，稠密+稀疏混合检索）
- **上架助手**：多平台 Listing 并行审核与合规检查（支持人机协同中断）
- **数据智能**：自然语言驱动的数据分析（多轮对话记忆）

技术栈：Python + FastAPI + LangGraph + LangChain（含 core / community / text-splitters）+ Milvus 2.4+ + pymilvus + PostgreSQL + BGE-M3（FlagEmbedding）+ BGE-Reranker（FlagEmbedding）+ Pydantic / pydantic-settings + SQLAlchemy + JWT（python-jose）+ Tavily

---

## 2. 目录结构

```
08_ECMultiAgents/
├── AGENTS.md ← 本文件(全局导航 + 启动协议)
├── docs/
│ ├── rules/ ← 工程铁律与编码规范
│ ├── spec/ ← 版本化技术方案
│ └── lessons.md ← 踩坑记录
├── state/ ← AI 长期/短期记忆
│ ├── project_status.md ← 任务看板
│ └── current_task.md ← 当前工作台
├── src/
│ └── backend/
│ ├── config.py ← 配置中心（Pydantic Settings，所有可调参数集中管理）
│ ├── main.py ← FastAPI 应用入口
│ ├── api/ ← 接口层（v1 路由、鉴权、依赖注入）
│ ├── core/ ← 基础设施层（LLM 工厂、Milvus 客户端、工具、编排、安全）
│ ├── agents/ ← 三个 Agent 的 LangGraph 定义（rag_agent / listing_agent / data_agent）
│ ├── models/ ← ORM 模型 + Pydantic Schema
│ ├── db/ ← 数据库 session 管理 + 初始化脚本
│ └── prompts/ ← Prompt 模板（按模块拆分）
├── data/ ← 运行时数据（Checkpoint SQLite 持久化等）
└── tests/ ← 测试代码
```

---

## 3. 开发指引

> 不要直接尝试读取整个项目中所有文件——这会挤爆模型上下文窗口。
>
> 先根据指引阅读必要文档，接着分析当前需要开发的任务，再去看必要的文件即可。

### 1.开发前

每次开发前，都需要重新执行以下任务：

- 熟悉项目开发约束：必须遵守docs/rules/目录下的所有开发约束，每次开发前都需要重新熟悉所有开发约束，以防遗漏新的约束。
- 熟悉经验与教训：必须阅读docs/lesson.md文档，以防犯下之前产生过的错误。
- 获取当前开发状态：必须阅读state/current_task.md，熟悉当前正在做什么

### 2.开发后

每次开发后，都需要执行以下任务

- 更新开发状态：必须更新state/current_task.md，确保该文档始终表达最新的任务状态。
- 更新项目状态：阅读state/project_status.md，判断是否需要更新文档中的项目单元任务状态，按需更新文档，确保该文档始终表达准确的项目进度。

## 4.构建、运行与开发命令

使用 `uv` 管理依赖：

```bash
uv sync                      # 按 lock 文件同步依赖
uv run python main.py        # 启动入口
uv add <pkg>                 # 新增依赖
uv run <cmd>                 # 在虚拟环境中执行命令
```

### 4.1 环境配置

项目依赖 `.env.local` 提供运行时的全部配置（LLM API Key、Milvus 连接、PostgreSQL 连接等），该文件不入 Git。所有配置项及默认值见 `src/backend/config.py`。
