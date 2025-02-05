from typing import Annotated, Sequence
from langchain_core.messages import BaseMessage, ToolMessage, SystemMessage
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from typing import Literal
from typing_extensions import TypedDict
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import Command
from langgraph.prebuilt import create_react_agent
from langchain_aws.retrievers import AmazonKnowledgeBasesRetriever
from langchain_aws import ChatBedrock
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage
from IPython.display import display, Image
from pydantic import BaseModel, Field
import os
import json

class State(MessagesState):
    system_name: str = ""
    region: str = "ap-northeast-1"
    account_id: str = ""
    known: bool = False
    command: str = ""

llm = ChatBedrock( # 後日 "anthropic.claude-3-5-sonnet-20241022-v2:0" を試してみる
    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
    model_kwargs={"temperature": 0.1},
    beta_use_converse_api=False,
)

retriever = AmazonKnowledgeBasesRetriever(
    knowledge_base_id=os.getenv('KNOWLEDGEBASE_ID'),
    retrieval_config={
        "vectorSearchConfiguration": {
            "numberOfResults": 1
        }
    },
)

prompt_for_rag = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant that compares the given Error Message with the Data from RAG to determine whether the Error Message corresponds to a known issue.\n\
            If it is identified as a known issue, provide, set `known` to `True`.\n\
            Also, if there is a specific command to solve the issue in the data from RAG, set the command to `command`.\n\
            Don't set anything to `command` if there is no specific description of a command to solve the issue in the data from RAG.",
        ),
        ("human", "# Error Message\n{error_message}\n\n# Data from RAG\n{data_from_rag}"),
    ]
)

class RagResponse(BaseModel):
    known: bool = Field(..., description="Whether the Error Message corresponds to a known issue.")
    command: str = Field(..., description="The command to execute.")

@tool
def rag_analysis(state: State) -> State:
    """
    Perform RAG (Retrieval-Augmented Generation) analysis on the given error message.
    """
    chain = retriever | (lambda docs: "\n\n".join(doc.page_content for doc in docs))
    print("\nrag_agent state before update:\n------------------------------------------\n", state)
    print("\nrag_agent state['messages'][0].content:\n------------------------------------------\n", state["messages"][0].content)
    error_message = state["messages"][0].content
    rag_result = chain.invoke(error_message)
    print("\nrag_result:\n-----------------------------------------\n", rag_result)
    # chain = prompt_for_rag | llm | StrOutputParser()
    chain = prompt_for_rag | llm.with_structured_output(RagResponse)
    response = chain.invoke({
        "error_message": error_message,
        "data_from_rag": rag_result,
    })
    print("\nrag_agent response in rag_analysis tool:\n------------------------------------------\n", response)
    state["known"] = response.known # Stateのknownフィールドを更新
    state["command"] = response.command # Stateのcommandフィールドを更新
    # state["system_name"] = "Goku" # test（Supervisor AgentのStateがこの値に上書きされることを確認）
    # state["region"] = "us-west-2" # test（Supervisor AgentのStateがこの値に上書きされることを確認）
    # state["account_id"] = "2323232323" # test（Supervisor AgentのStateがこの値に上書きされることを確認）
    print("\nrag_agent state after update:\n------------------------------------------\n", state)
    return state

tools = [rag_analysis]
llm_model = llm.bind_tools(tools)

tools_by_name = {tool.name: tool for tool in tools} # 複数のツールがある場合に備えて辞書にしておく

def tool_node(state: State):
    outputs = []
    print('\nrag_agent state["messages"][-1] in tool_node:\n------------------------------------\n', state["messages"][-1])
    print("\nrag_agent state in tool_node:\n--------------------------------------------\n", state)
    for tool_call in state["messages"][-1].tool_calls:
        tool_result = tools_by_name[tool_call["name"]].invoke({"state": state})
        state.update(tool_result) # Stateを更新
        outputs.append(
            ToolMessage(
                content=tool_result,
                name=tool_call["name"],
                tool_call_id=tool_call["id"],
            )
        )
    state["messages"] = outputs
    return state # 次のNodeに入力としてStateを渡す

def call_model( # これがAgent
    state: State,
    config: RunnableConfig,
):
    # this is similar to customizing the create_react_agent with 'prompt' parameter, but is more flexible
    system_prompt = SystemMessage(
        "You are a helpful assistant that compares the given Error Message with the Data from RAG to determine whether the Error Message corresponds to a known issue."
    )
    response = llm_model.invoke([system_prompt] + state["messages"], config)
    print("\nrag_agent response in call_model:\n----------------------------------------------\n", response)
    print("\nrag_agent state in call_model:\n----------------------------------------------\n", state)

    state["messages"] = [response]
    return state # 次のNodeに入力としてStateを渡す。（他のフィールドはそのまま残るように、state 全体を返す）

# Define the conditional edge that determines whether to continue or not
def should_continue(state: State):
    messages = state["messages"]
    last_message = messages[-1]

    print("\nrag_agent [should_continue] state:\n----------------------------------\n", state)
    print("\nrag_agent [should_continue] last_message:\n----------------------------------\n", last_message)
    # If there is no function call, then we finish
    
    if not last_message.tool_calls:
        return "end"
    # Otherwise if there is, we continue
    else:
        return "continue"

builder = StateGraph(state_schema=State)
builder.add_node("rag_agent", call_model)
builder.add_node("rag_tools", tool_node)
builder.set_entry_point("rag_agent")
builder.add_conditional_edges(
    "rag_agent",
    should_continue,
    {
        "continue": "rag_tools",
        "end": END,
    },
)
builder.add_edge("rag_tools", "rag_agent")
graph = builder.compile()

# # Save the graph as a PNG
# png_data = graph.get_graph().draw_mermaid_png()
# with open("workflow_diagram.png", "wb") as f:
#     f.write(png_data)

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

    with open("final_state.txt", "w", encoding="utf-8") as f:
        f.write(pformat(final_state))

    print("Final state saved to final_state.txt")

def main():
    print_stream(graph.stream({
        "messages": [("user", input("input error message:\n"))],
        "system_name": "Goku",
        "region": "ap-northeast-1",
        "account_id": "1234567890",
        "known": False,
        "command": "",
        }, stream_mode="values"))

if __name__ == "__main__":
    main()