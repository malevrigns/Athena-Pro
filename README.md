# Athena Pro · 单用户深度研究助手 (v5)

一个**真正可部署、可在线使用**的多 Agent 深度研究产品。
后端 FastAPI + 持久化 SQLite + 迭代式 supervisor 流水线,
前端 Vue 3 + Naive UI + Vue Flow + 流式 Markdown,
一键 `docker compose up` 即可在浏览器使用。

> 与上一代相比:从教学 demo 升级为单用户生产级产品。
> 真实 LLM 接入(OpenAI / Anthropic / DeepSeek / OpenRouter)、真实搜索(Tavily)、
> 报告导出 PDF/DOCX/MD、API Key 鉴权、SQLite 持久化、SSE 流式、UI 工作台。

---

## 主要特性

- **多 Agent 流水线**: Planner → Plan Review → Supervisor → Researcher (并发) → Quality Gate → Reviewer → Writer。质量不达标自动追加调研轮次。
- **真实 LLM 路由**: 通过 `ATHENA_LLM_PROVIDER` 切换 `mock / openai / anthropic / deepseek / openrouter`,各节点可独立指定模型。
- **真实搜索**: Tavily(密钥配置后自动启用),带重试与 30 分钟缓存。
- **流式响应**: SSE 实时推送,前端 Markdown 渐进渲染,断点重连。
- **持久化**: 任务、状态、事件、token 用量全部入 SQLite (WAL 模式)。重启进程后历史依然可见,未完成任务自动标记失败。
- **报告导出**: Markdown / HTML / PDF (WeasyPrint) / DOCX (pandoc),一键下载,引用 footnote 完整保留。
- **API 安全**: 单用户 Bearer Token,带 IP 维度滑动窗口限流。SSE 接受 `?api_key=` 注入(浏览器 EventSource 限制)。
- **企业级 UI**: Vue Flow 工作流画布(支持暗黑模式),Quality Gate 雷达,Token/Cost 拆解,Finding 折叠卡,引用追溯。
- **健康/配置 API**: `/health`, `/v1/config` 暴露状态,前端 Settings 页面可一键测试连接。

---

## 一键启动 (Docker)

```bash
git clone <repo> athena-pro && cd athena-pro
cp .env.example .env

# 必改: 生成一个长随机 API key
python -c "import secrets;print('ATHENA_API_KEY='+secrets.token_urlsafe(40))" >> .env

# (可选) 接入真实模型 / 搜索
# ATHENA_LLM_PROVIDER=openai
# ATHENA_OPENAI_API_KEY=sk-...
# ATHENA_DEFAULT_MODEL=gpt-4o-mini
# ATHENA_SEARCH_PROVIDER=tavily
# ATHENA_TAVILY_API_KEY=tvly-...

docker compose up -d --build
```

打开 <http://localhost:5173>:

1. 进入 **系统设置**,粘贴 `ATHENA_API_KEY`,保存。
2. 点 **测试连接** 应该看到 `API 正常`。
3. 回到 **研究工作台**,输入问题(或点 preset),开始研究。
4. 等流水线跑完,在右上角下载 PDF / DOCX / MD。

数据持久化在 named volume `athena-data`(挂载到容器 `/data`),包含 SQLite 和导出文件。

---

## 本地开发

### 后端

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"
cp .env.example .env  # 然后填入 keys 或保持 mock
python -m uvicorn athena.api.main:app --reload --port 8000
```

可选额外功能:
- `pip install ".[llm]"` — OpenAI / Anthropic SDK
- `pip install ".[search]"` — Tavily SDK
- `pip install ".[export]"` — WeasyPrint + pypandoc
  - PDF 需要系统库:`apt install libpango-1.0-0 libcairo2 fonts-noto-cjk`
  - DOCX 需要 `pandoc` 可执行文件

### 前端

```bash
cd web
npm install
VITE_API_PROXY=http://localhost:8000 npm run dev
```

打开 <http://localhost:5173>(开发模式 Vite 代理到 8000)。

### 测试

```bash
source .venv/bin/activate
python -m pytest tests -q       # 后端
cd web && npx vue-tsc --noEmit  # 前端类型检查
```

---

## 环境变量速查

| 变量 | 默认 | 说明 |
|---|---|---|
| `ATHENA_API_KEY` | (空) | Bearer Token,**生产必须**设置 |
| `ATHENA_REQUIRE_AUTH` | `true` | 关掉只在内网/本机调试时用 |
| `ATHENA_LLM_PROVIDER` | `mock` | `mock / openai / anthropic / deepseek / openrouter` |
| `ATHENA_DEFAULT_MODEL` | `mock-researcher` | 默认模型名 |
| `ATHENA_PLANNER_MODEL` / `_RESEARCHER_MODEL` / `_WRITER_MODEL` | (空) | 各节点单独覆盖 |
| `ATHENA_OPENAI_API_KEY` 等 | (空) | 对应 provider 的 key |
| `ATHENA_SEARCH_PROVIDER` | `mock` | `mock / tavily`,有 key 自动启用 tavily |
| `ATHENA_MAX_RESEARCH_ITERATIONS` | `2` | quality 不达标的重做轮次 |
| `ATHENA_QUALITY_THRESHOLD` | `0.7` | 达到该值停止 reviewer 回环 |
| `ATHENA_MAX_BUDGET_USD` | `5` | 软上限提醒 |
| `ATHENA_HARD_TIMEOUT_SEC` | `600` | 任务最长执行时长 |
| `ATHENA_RATE_LIMIT_PER_MINUTE` | `30` | 同 IP 同 path 的限流 |
| `ATHENA_DATA_DIR` | `.athena-data` | SQLite/exports 根目录 |
| `ATHENA_ALLOWED_ORIGINS` | `["http://localhost:5173"]` | CORS 白名单 |

---

## API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查(对外开放) |
| GET | `/v1/config` | 服务端配置快照(对外开放) |
| POST | `/v1/research` | 创建任务 |
| GET | `/v1/research` | 任务列表(从 SQLite 拉) |
| GET | `/v1/research/{id}` | 任务快照 |
| GET | `/v1/research/{id}/events` | 历史事件 |
| GET | `/v1/research/{id}/stream` | SSE 流(支持 `?api_key=`) |
| POST | `/v1/research/{id}/interrupt` | 软中断 |
| POST | `/v1/research/{id}/review` | 提交人工审阅 |
| POST | `/v1/research/{id}/export?fmt=md\|html\|pdf\|docx` | 导出报告 |
| GET | `/v1/research/{id}/download?filename=...` | 下载导出文件 |
| POST | `/v1/feedback` | 提交评分 / 评论 |

所有 `/v1/` 端点都要求 `Authorization: Bearer <ATHENA_API_KEY>`(`/v1/config` 除外)。

---

## 架构图

```
浏览器 (Vue3 + Naive + VueFlow + ofetch)
    │  Bearer Token
    │  SSE  ← /v1/research/{id}/stream
    ▼
FastAPI ── 中间件: CORS, RateLimit, Auth
    │
    ├─ runtime_store (in-memory)  ◀──┐
    │      │                          │
    │      │ async task                │
    │      ▼                          │
    │  graph/main_graph (iterative supervisor)
    │      │
    │      ├─ planner_node           │
    │      ├─ plan_review_node       │
    │      ├─ supervisor_node        │ ← 内部循环
    │      ├─ researcher_node (并发) │
    │      ├─ quality_gate_node      │
    │      ├─ reviewer_node          │
    │      └─ writer_node            │
    │      │                          │
    │      ▼                          │
    │   event_bus → persistence ─────┘
    │                                  
    └─ persistence/sqlite_store (WAL + 自动 schema)
                ▲
                │
            /data/athena.sqlite3
            /data/exports/*.{md,html,pdf,docx}
```

---

## 安全注意

- **总是**在生产设置 `ATHENA_API_KEY`,并通过 HTTPS 终止(nginx/caddy/cloudflare)。
- 前端的 API Key 保存在 `localStorage`,只在你信任的浏览器使用。
- `dompurify` 严格清洗渲染的 Markdown HTML,但仍不建议把不可信用户输入直接喂进任务问题。
- 速率限制只是基础防御,公网部署建议在反代层加 fail2ban 或 cloudflare turnstile。

---

## 路线图(已脱离 V1)

- ✅ 真实 LLM / 搜索 / 流式 / 导出
- ✅ SQLite 持久化 + 重启恢复
- ✅ Vue Flow 工作流可视化 + 流式 Markdown + 暗黑模式
- ✅ Docker Compose 一键部署
- ⏳ 文件 / 知识库上传 (RAG, pgvector)
- ⏳ 多用户与 RBAC (当前是单用户)
- ⏳ MCP 工具市场接入

```text
版本 5.0.0 · 真正能用 · 单用户生产可投
```
