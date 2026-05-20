    async def get_session_summary(self, session_id: str) -> dict:
        """给前端"恢复 session"页面用的数据。"""
        s = await self.db.get(Session, session_id)
        if not s:
            return None
        
        task_count = await self.db.scalar(
            select(func.count(Task.task_id)).where(Task.session_id == session_id)
        )
        recent_tasks = (await self.db.execute(
            select(Task)
            .where(Task.session_id == session_id)
            .order_by(desc(Task.created_at))
            .limit(10)
        )).scalars().all()
        
        return {
            "session_id": s.session_id,
            "user_id": s.user_id,
            "created_at": s.created_at.isoformat(),
            "last_active_at": s.last_active_at.isoformat(),
            "total_cost_usd": s.total_cost_usd,
            "preferences": s.preferences or {},
            "task_count": task_count,
            "recent_tasks": [{
                "task_id": t.task_id,
                "question": t.question[:120],
                "status": t.status,
                "created_at": t.created_at.isoformat(),
                "cost_usd": t.cost_usd,
            } for t in recent_tasks],
        }