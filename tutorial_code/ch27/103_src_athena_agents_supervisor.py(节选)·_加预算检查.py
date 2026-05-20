async def supervisor_node(state: ResearchState) -> Command:
    ledger = get_current_ledger()
    
    # 预算检查
    if ledger and ledger.is_exceeded:
        logger.warning("supervisor_abort_budget", spent=ledger.spent_usd)
        return Command(
            goto="__end__",
            update={
                "final_report": (
                    f"> ⚠️ 任务因预算超限提前结束。\n"
                    f"> 已花费 ${ledger.spent_usd:.4f} / 预算 ${ledger.budget_usd:.4f}\n\n"
                    + _partial_report_from(state)
                ),
                "abort_reason": "budget_exceeded",
            }
        )
    
    # 软警告:用了 80% 预算
    if ledger and ledger.spent_usd > ledger.budget_usd * 0.8:
        logger.warning("budget_warning_80pct", spent=ledger.spent_usd)
    
    # ... 原有调度逻辑 ...