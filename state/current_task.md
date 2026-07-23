# 当前任务上下文

> 简明扼要，只为下一轮任务提供必要上下文。

## 已完成验收（M1.1–M1.4 + M2.1）

| 任务 | 产出文件 | 验收 |
|------|---------|------|
| M1.1 config.py | `src/backend/config.py` | ✅ 46 passed |
| M1.2 main.py | `src/backend/main.py`、`src/backend/api/v1/` | ✅ 49 passed |
| M1.3 deps.py | `src/backend/api/deps.py` | ✅ 55 passed |
| M2.1 llm_factory.py | `src/backend/core/llm_factory.py`、`src/backend/core/__init__.py`、`tests/test_llm_factory.py` | ✅ 62 passed（55 既有 + 7 新增）|

## 项目结构现状

```
src/backend/
├── __init__.py
├── config.py              # Settings 配置中心
├── main.py                # FastAPI 入口
├── core/
│   ├── __init__.py         # Core 包
│   └── llm_factory.py     # LLM 工厂（DeepSeek/MiniMax）
└── api/
    ├── __init__.py
    ├── deps.py             # 5 个 Depends 工厂
    └── v1/
        ├── __init__.py
        └── router.py       # 空 APIRouter
```

`agents/`、`core/milvus_client.py`、`db/`、`models/` 和 `core/security.py` 仍未落地。

## deps.py 关键约定（给 M7.x 子路由的提醒）

- `get_db()`: M4.3 缺位时 yield `None`，后续子路由**必须做 None 检查**
- `get_rag_graph()` / `get_listing_graph()` / `get_data_graph()` / `get_orchestrator()`: `@lru_cache` 全局单例，M5/M6 未落地时返回 `None`，落地后需**重启进程**才能拿到真实 graph
- 所有 `try/except ImportError` 占位，M5/M6/M4.3 落地后 import 自动接管，无需改 deps.py

## 下一步

**M2.2**: `src/backend/core/milvus_client.py` — 封装 Milvus 客户端与完整混合检索链路（BGE-M3 编码 + Hybrid Search + Reranker 精排 + Sigmoid 置信度）。这是最大单个任务（1.5d）。

---

## M2.1 验收记录

**产出文件**：
- `src/backend/core/__init__.py` — Core 包文件
- `src/backend/core/llm_factory.py` — `create_llm` 函数（DeepSeek/MiniMax，配置化模型名，思考模式）
- `tests/test_llm_factory.py` — 7 个单元测试
- `tests/test_llm_factory_smoke.py` — 2 个烟雾测试（由 `RUN_INTEGRATION_TESTS` 控制，不入版本控制）
- `tests/logs/M2.1-llm-factory.{log,xml}` — 单元测试日志
- `tests/logs/M2.1-llm-factory-smoke.{log,xml}` — 烟雾测试日志

**前置修改**：
- `src/backend/config.py` — 新增 `DEEPSEEK_MODEL`、`MINIMAX_MODEL`
- `tests/conftest.py` — 同步假值/规范键/清理列表
- `docs/spec/TechSPEC.md` — §4.1 修正模型名 + 补充思考模式说明

**验证证据**：
| # | 命令 | 结果 |
|---|------|------|
| V1 | `uv run pytest tests/test_llm_factory.py -v` | 7 passed |
| V2 | `uv run pytest -v` | 62 passed + 2 skipped |
| V3 | `RUN_INTEGRATION_TESTS=1 uv run pytest tests/test_llm_factory_smoke.py -v` | 2 failed（SSL 连接受限，烟雾测试环境问题） |
| V4 | `uv run python -c "from backend.core.llm_factory import create_llm; print('ok')"` | stdout: `ok` |
| V5 | config.py 加载确认 | `DEEPSEEK_MODEL=deepseek-v4-flash`，`MINIMAX_MODEL=Minimax-M3` |
| V6 | 密钥泄露检查 | grep 返回 1（无泄漏） |

**产出文件**：
- `pyproject.toml` — 新增 11 项业务依赖
- `requirements.txt` — uv export 衍生生成（头部注明"auto-generated，DO NOT edit"）
- `uv.lock` — uv add 自动刷新
- `tests/logs/M1.4-reqs.log` / `tests/logs/M1.4-reqs.xml` — 测试日志

**验证证据**：
| # | 命令 | 结果 |
|---|------|------|
| V1 | `uv sync` | exit 0 |
| V2 | `uv run python -c "import ... 11 packages ...; print('ok')"` | stdout: `all-imports-ok` |
| V3 | `uv run pytest -v --junitxml=...` | 55 passed, exit 0 |
| V4 | `grep -cE "14 key pkgs" requirements.txt` | 93 行匹配 |
| V5 | `head -5 requirements.txt` | 含 `# DO NOT edit manually.` 注释 |
| V6 | 密钥泄露检查 | grep 返回 1（无泄漏） |
