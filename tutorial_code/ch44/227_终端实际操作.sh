# 安装
$ pip install athena-cli

# 配置(一次性)
$ export ATHENA_SERVER=https://athena.example.com
$ export ATHENA_TOKEN=sk-...

# 快问快答(pipe 友好)
$ athena ask "Python 异步 GIL 在 3.13 还存在吗" | tee answer.md

# 进 TUI 模式
$ athena
  → 全屏 Textual UI,可创建任务、看历史、改设置

# 看历史
$ athena history --limit 5 --status done
┌──────────┬───────┬──────────────────────────┬─────────┬─────────────────┐
│ ID       │ 状态  │ 问题                      │ 成本    │ 创建时间        │
├──────────┼───────┼──────────────────────────┼─────────┼─────────────────┤
│ a3f29b1c │ done  │ Python 异步 GIL 在 3.13...│ $0.142  │ 2026-05-13 09:15│
│ b7d11e22 │ done  │ 调研 2026 Q1 半导体...    │ $0.221  │ 2026-05-13 08:43│
└──────────┴───────┴──────────────────────────┴─────────┴─────────────────┘

# 续接昨天没看完的任务
$ athena resume b7d11e22
  → 进 TUI,自动重放该任务全过程,显示完整报告

# 导出为 PDF
$ athena export a3f29b1c -o gil.pdf --format pdf
已导出到 gil.pdf

# 查成本
$ athena cost
本月累计: $4.27
预算: $50.00 (9%)
剩余: $45.73

按模型分布:
  gpt-4o-mini              $2.183
  gpt-4o                   $1.602
  claude-3-5-haiku         $0.485

# 管权限
$ athena permissions list
3c91a    session     bash_tool                       2026-05-13 08:32
4d22b    forever     github__list_issues             2026-05-12 14:15

$ athena permissions revoke 4d22b
已撤回 4d22b