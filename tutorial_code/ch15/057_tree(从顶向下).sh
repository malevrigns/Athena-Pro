athena/
├── pyproject.toml              # ← 这一章
├── uv.lock
├── .env.example                # 环境变量模板
├── .gitignore
├── README.md
├── Dockerfile                  # 第 30 章
├── docker-compose.yml          # 第 30 章
├── Makefile                    # 常用命令封装
│
├── src/athena/
│   ├── __init__.py
│   ├── __main__.py             # python -m athena 入口
│   ├── cli.py                  # athena CLI 命令
│   │
│   ├── config.py               # ← 这一章下面就写
│   ├── logging.py              # 结构化日志(第 26 章)
│   │
│   ├── state/
│   │   ├── __init__.py
│   │   └── schemas.py          # 第 16 章
│   │
│   ├── prompts/                # Prompt 资产(第 18 章)
│   │   ├── planner.py
│   │   ├── researcher.py
│   │   ├── reviewer.py
│   │   └── writer.py
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── search.py           # 第 17 章
│   │   ├── fetcher.py
│   │   └── cache.py
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── planner.py          # 第 18 章
│   │   ├── researcher.py       # 第 19 章
│   │   ├── supervisor.py       # 第 20 章
│   │   ├── fact_checker.py     # 第 21 章
│   │   ├── citation_validator.py
│   │   ├── reviewer.py
│   │   └── writer.py           # 第 22 章
│   │
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── builder.py          # 第 20 章
│   │   ├── subgraphs.py        # 子图复用
│   │   └── policies.py         # 重试/超时/限流
│   │
│   ├── persistence/
│   │   ├── __init__.py
│   │   ├── checkpointer.py     # 第 23 章
│   │   └── reports.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py             # 第 24 章
│   │   ├── routes.py
│   │   ├── streaming.py        # SSE
│   │   ├── auth.py
│   │   └── schemas.py
│   │
│   └── observability/
│       ├── __init__.py
│       ├── tracing.py          # 第 26 章
│       ├── metrics.py
│       └── costs.py            # 第 27 章
│
└── tests/                      # 第 29 章
    ├── unit/
    ├── integration/
    ├── eval/
    │   ├── dataset.jsonl
    │   └── run_eval.py
    └── load/
        └── locustfile.py