class CostTrackingCallback(BaseCallbackHandler):
    def __init__(self, node_name: str):
        self.node_name = node_name
    
    def on_llm_new_token(self, token: str, **kwargs):
        """每个 token 到来时检查 abort 标志。"""
        from athena.api.interrupt import check_abort
        check_abort()                                # 抛 TaskAborted 立刻中断 LLM 流
    
    def on_llm_end(self, response, **kwargs):
        # ... 原有的成本记账逻辑 ...
        pass