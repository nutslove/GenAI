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
from aws_phd_agent import graph as aws_phd_graph

class State(MessagesState):
    system_name: str = ""
    region: str = "ap-northeast-1"
    account_id: str = ""
    known: bool = False
    command: str = ""

llm = ChatBedrock(
    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
    model_kwargs={"temperature": 0.1},
    beta_use_converse_api=False,
)

class Router(TypedDict):
    next: Literal["aws_phd_agent", "FINISH"]

members = ["aws_phd_agent"]
options = members + ["FINISH"]

system_prompt_for_supervisor = (
    "You are a supervisor tasked with managing a conversation between the"
    f" following workers: {members}. Given the following user request,"
    " respond with the worker to act next. Each worker will perform a"
    " task and respond with their results and status. When finished,"
    " respond with FINISH."
)

def supervisor_node(state: State) -> Command[Literal["aws_phd_agent", "__end__"]]:
# def supervisor_node(state: State) -> Command:
    print("\nstate['messages'][0] in supervisor_node:\n------------------------------------\n", state["messages"][0])
    # messages = [{"role": "system", "content": system_prompt_for_supervisor}] + state["messages"][0] # state["messages"][0]には最初に入力されたエラーメッセージが入っている
    messages = [{"role": "system", "content": system_prompt_for_supervisor, "role": "user", "content": state["messages"][0].content}] # state["messages"][0].contentには最初に入力されたエラーメッセージが入っている
    print("\nstate in supervisor_node:\n------------------------------------\n", state)
    response = llm.with_structured_output(Router).invoke(messages)
    goto = response["next"]
    print("\nnext in supervisor_node:\n------------------------------------\n", goto)
    if goto == "FINISH" or (state["known"] and state["command"] != ""):
        goto = END
    # return Command(goto=goto, update={"next": goto})
    # return Command(goto=goto, update={"messages": messages})
    # return Command(goto=None)
    return Command(goto=goto)

builder = StateGraph(state_schema=State)
builder.add_node("supervisor_agent", supervisor_node)
builder.add_node("rag_agent", rag_graph)
builder.add_node("aws_phd_agent", aws_phd_graph)
builder.add_edge(START, "rag_agent")
builder.add_edge("rag_agent", "supervisor_agent")
builder.add_edge("aws_phd_agent", "supervisor_agent")
graph = builder.compile()

# Save the graph as a PNG
png_data = graph.get_graph().draw_mermaid_png()
with open("supervisor_workflow_diagram.png", "wb") as f:
    f.write(png_data)

from pprint import pformat

def print_stream(stream):
    final_state = None
    for s in stream:
        final_state = s
        message = s["messages"][-1]
        if isinstance(message, tuple):
            print(message)
        else:
            message.pretty_print()

    with open("supervisor_final_state.txt", "w", encoding="utf-8") as f:
        f.write(pformat(final_state))

    print("Final state saved to supervisor_final_state.txt")

def main():
    print_stream(graph.stream({
        "messages": [("user", input("input error message:\n"))],
        "system_name": "Factory",
        "region": "ap-northeast-1",
        "account_id": "0123456789",
        "known": False,
        "command": "",
        },
        # subgraphs=True,
        stream_mode="values",
        config={"recursion_limit": 5},
        ))

if __name__ == "__main__":
    main()