# 安装 uv(macOS / Linux)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 在工作目录初始化项目
uv init athena --package
cd athena