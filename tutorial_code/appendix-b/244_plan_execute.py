"""
"先规划再执行"模式。
"""
from typing import Annotated, Literal
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.graph.message import add_messages
from langgraph.types import Command
import operator

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


class State(MessagesState):
    task: str
    plan: list[str]
    completed_steps: Annotated[list[str], operator.add]
    current_step: int


class Plan(BaseModel):
    steps: list[str] = Field(..., description="完成任务的步骤列表")


def planner(state) -> Command[Literal["executor"]]:
    plan = llm.with_structured_output(Plan).invoke([
        {"role": "system", "content": "把任务拆解为 3-5 个清晰的执行步骤。"},
        {"role": "user", "content": state["task"]},
    ])
    return Command(goto="executor", update={"plan": plan.steps, "current_step": 0})


def executor(state) -> Command[Literal["executor", "__end__"]]:
    step_idx = state["current_step"]
    if step_idx >= len(state["plan"]):
        return Command(goto=END)
    
    current = state["plan"][step_idx]
    result = llm.invoke([
        {"role": "system", "content": f"执行步骤:{current}"},
        {"role": "user", "content": state["task"]},
    ])
    
    return Command(
        goto="executor",
        update={
            "completed_steps": [f"{current} => {result.content}"],
            "current_step": step_idx + 1,
        }
    )


builder = StateGraph(State)
builder.add_node("planner", planner)
builder.add_node("executor", executor)
builder.add_edge(START, "planner")
graph = builder.compile()