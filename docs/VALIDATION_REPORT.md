# Validation report
本报告用于修正旧版中“代码规模”表述不准确的问题。
| 区域 | 文件数 | 行数 | 说明 |
|---|---:|---:|---|
| `backend_py` | 55 | 2023 | 可运行后端源码，不再宣称 7000+ 行。 |
| `frontend_src` | 35 | 1031 | Vue 3 + Vite + Pinia + Naive UI 前端源码。 |
| `tests` | 1 | 29 | 后端测试。 |
| `tutorial_code` | 248 | 11960 | 从教材 HTML 代码块提取的章节代码归档，含练习、反模式、片段、完整示例。 |
| `all_repo_code_like` | 295 | 14870 | 包含配置、文档、测试和教材归档。 |

## 运行验证

在当前容器中已执行：

```bash
python -m compileall -q src
python -m pytest tests -q
```

结果：`2 passed`。

## 口径说明

教材中的基础章节代码有大量“最小示例 / 错误示范 / 对照片段”，这些代码不应全部 import 到生产 runtime。它们已进入 `tutorial_code/`，运行型产品代码位于 `src/athena/` 和 `web/src/`。
