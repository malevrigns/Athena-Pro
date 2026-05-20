---
name: excel-analysis
description: 处理 Excel/CSV 数据分析任务。当用户上传表格或问"分析这份数据"时使用。
version: 1.0.0
author: athena-team
when_to_use:
  - 用户提到 Excel / xlsx / csv / 数据分析 / 透视表
  - 问题涉及销售/财务/运营数据的趋势/对比/分布
requires_tools:
  - read_xlsx              # 来自 excel-mcp
  - apply_formula
  - python_repl            # Athena 内置 sandbox
---

# Excel 数据分析

你正在处理用户的表格数据分析任务。请遵循以下流程:

## 标准工作流

1. **读取数据** · 用 `read_xlsx(path)` 工具读入,返回 sheet 列表和前 5 行预览
2. **识别列语义** · 通过列名 + 前几行内容,判断每列是: 日期 / 金额 / 类别 / 数量 / 标签
3. **数据清洗** · 检查缺失值、异常值。**绝不要默默丢弃数据**,要在最终报告里说明
4. **分析维度** · 按列语义选合适的聚合方式:
   - 金额列 → SUM, 不要 AVG
   - 数量列 → SUM 或 COUNT
   - 类别列 → GROUP BY
   - 日期列 → 时序分组(日/周/月/季度,根据数据跨度选)
5. **画图** · 用 `scripts/quick_chart.py`(详见 reference/chart-types.md 选合适图类型)
6. **撰写报告** · 用三段式: 数据概览 → 关键发现 → 建议行动

## 重要原则

- **不要凭直觉得出结论**:每个数字都要在表里能查到
- **金额单位要明确**:报告里写"销售额 1.2M"必须说清是 USD 还是 CNY
- **缺失数据要透明**:报告里专门一段说明"X 月份数据缺失,以下分析不含该月"

## 进阶资源

- 公式速查: 读 `reference/formulas.md`
- 趋势分析方法: 读 `reference/trends.md`
- 图表选型: 读 `reference/chart-types.md`