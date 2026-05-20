from langgraph.graph import MessagesState

# MessagesState 等价于:
# class MessagesState(TypedDict):
#     messages: Annotated[list[AnyMessage], add_messages]

# 如果你需要更多字段,继承它就行:
class MyState(MessagesState):
    user_id: str
    topic: str