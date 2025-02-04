from typing import Annotated
from langchain_core.tools import tool
from typing import Literal
from typing_extensions import TypedDict
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.types import Command
from langgraph.prebuilt import create_react_agent
from langchain_aws.retrievers import AmazonKnowledgeBasesRetriever
from langchain_aws import ChatBedrock
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage
from IPython.display import display, Image
from pydantic import BaseModel, Field
import os
from rag_agent import graph as rag_graph

class State(MessagesState):
    next: str
    system_name: str
    region: str
    account_id: str

llm = ChatBedrock(
    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0", model_kwargs={"temperature": 0.1}
)

class Router(TypedDict):
    next: Literal["rag_agent", "FINISH"]

members = ["rag_agent"]
options = members + ["FINISH"]

system_prompt_for_supervisor = (
    "You are a supervisor tasked with managing a conversation between the"
    f" following workers: {members}. Given the following user request,"
    " respond with the worker to act next. Each worker will perform a"
    " task and respond with their results and status. When finished,"
    " respond with FINISH."
)

def supervisor_node(state: State) -> Command[Literal["rag_agent","__end__"]]:
    messages = [
        {"role": "system", "content": system_prompt_for_supervisor},
    ] + state["messages"]
    response = llm.with_structured_output(Router).invoke(messages)
    goto = response["next"]
    if goto == "FINISH":
        goto = END
    return Command(goto=goto, update={"next": goto})

builder = StateGraph(State)
builder.add_node("supervisor_agent", supervisor_node)
builder.add_node("rag_agent", rag_graph)
builder.add_edge(START, "supervisor_agent")
graph = builder.compile()

# Save the graph as a PNG
png_data = graph.get_graph().draw_mermaid_png()
with open("supervisor_workflow_diagram.png", "wb") as f:
    f.write(png_data)

# for s in graph.stream(
#     {
#         "messages": [("user", input("input messages: \n"))],
#         "system_name": "goku",
#         "region": "ap-northeast-1",
#         "account_id": "123456789012",
#     },
#     # subgraphs=True
# ):
#     print(s)
#     print("----")