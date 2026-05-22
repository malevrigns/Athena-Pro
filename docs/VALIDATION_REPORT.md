# Validation report

本报告记录当前代码规模与运行验证结果的真实口径(替代早期已过期的数字)。
最近更新:2026-05-22(Research OS Phase 4 — 文献调研闭环完成后)。

## 代码规模

| 区域 | 文件数 | 行数 | 说明 |
|---|---:|---:|---|
| `backend_py` (`src/athena/`) | 101 | 9983 | 可运行后端源码(FastAPI + 多 Agent runtime + Research OS 层)。 |
| `frontend_src` (`web/src/`) | 55 | 12956 | Vue 3 + Vite + Pinia + Element Plus 前端源码(`.ts` / `.vue` / `.css`)。 |
| `tests` (`tests/`) | 17 | 3274 | 后端 pytest 测试(含 `tests/research/` Research OS 套件)。 |
| `tutorial_code` | 150 | 7160 | 从教材提取的章节代码归档(练习、反模式、片段、完整示例),不参与生产 runtime。 |

数字用 `find … | wc -l` 与 `cat … | wc -l` 直接统计,随代码变动需重新核对。

## 运行验证

```bash
python -m compileall -q src
python -m pytest -q
(cd web && npm run build)
```

结果:`207 passed`;后端编译通过;前端 `vite build` 通过。

## 口径说明

教材章节代码包含大量「最小示例 / 错误示范 / 对照片段」,不应全部 import 到生产
runtime——它们归档在 `tutorial_code/`。运行型产品代码位于 `src/athena/` 与
`web/src/`,前端 UI 框架为 Element Plus。
