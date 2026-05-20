logger.info(
    "fact_check_done",
    task_id="task-abc123",
    topic="量化部署",
    unsupported_facts=2,
    confidence=0.84,
    duration_ms=312,
)

# 生产 JSON 输出:
# {"event": "fact_check_done", "task_id": "task-abc123",
#  "topic": "量化部署", "unsupported_facts": 2, "confidence": 0.84,
#  "duration_ms": 312, "level": "info", "timestamp": "2026-05-12T11:23:45Z"}