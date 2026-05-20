# 装运行时依赖
uv sync

# 装运行时 + dev 依赖
uv sync --extra dev

# 装所有(运行时 + dev + eval + load)
uv sync --all-extras

# 锁定版本(生成 uv.lock,务必提交到 git)
uv lock

# 跑命令
uv run pytest
uv run uvicorn athena.api.main:app --reload