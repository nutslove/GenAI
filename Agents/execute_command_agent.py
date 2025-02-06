from langchain_core.tools import tool
from langchain_experimental.utilities import PythonREPL
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_aws import ChatBedrock
from langgraph.graph import StateGraph, MessagesState
from langgraph.prebuilt import ToolNode
from typing import Literal, Annotated
import subprocess
import os
from IPython.display import display, Image

# This executes code locally, which can be unsafe
repl = PythonREPL()

@tool
def python_repl_tool(
    code: Annotated[str, "The python code to execute to generate your chart."],
) -> str:
    """Use this to execute python code and do math. If you want to see the output of a value,
    you should print it out with `print(...)`."""
    try:
        result = repl.run(code)
    except BaseException as e:
        return f"Failed to execute. Error: {repr(e)}"
    result_str = f"Successfully executed:\n\`\`\`python\n{code}\n\`\`\`\nStdout: {result}"
    print(result_str)
    return result_str

@tool
def shell_tool(
    command: Annotated[str, "The shell command to execute."],
) -> str:
    """Use this to execute shell commands."""
    try:
        result = subprocess.run(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except BaseException as e:
        return f"Failed to execute. Error: {repr(e)}"
    result_str = f"Successfully executed:\n\`\`\`shell\n{command}\n\`\`\`\nStdout: {result.stdout}\nStderr: {result.stderr}"
    print(result_str)
    return result_str

# Define available tools
tools = [python_repl_tool, shell_tool]
tool_node = ToolNode(tools)
llm = ChatBedrock(
    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
    model_kwargs={"temperature": 0.1}
).bind_tools(tools)

def should_continue(state: MessagesState) -> Literal["command_run_tools", "__end__"]:
    print("\nexecute_command_agent [should_continue] state:\n-----------------------------------\n", state, "\n-----------------------------------")
    messages = state['messages']
    last_message = messages[-1]
    print("\nexecute_command_agent [should_continue] Last message:\n-----------------------------------\n", last_message, "\n-----------------------------------")
    if last_message.tool_calls:
        return "command_run_tools"
    return "__end__"

def call_llm(state: MessagesState):
    system_prompt = SystemMessage(
        "You are a helpful assistant that can execute commands using the tools provided. You can use the following tools: python_repl_tool, shell_tool."
    )
    print("\nexecute_command_agent [call_llm] State:\n-----------------------------------\n", state, "\n-----------------------------------")

    response = llm.invoke([system_prompt] + state['messages'])
    return {"messages": [response]}

workflow = StateGraph(MessagesState)

workflow.add_node("command_run_agent", call_llm)
workflow.add_node("command_run_tools", tool_node)

workflow.add_edge("__start__", "command_run_agent")
workflow.add_conditional_edges(
    "command_run_agent",
    should_continue,
)
workflow.add_edge("command_run_tools", 'command_run_agent')
graph = workflow.compile()

# final_state = graph.invoke(
#     {"messages": [HumanMessage(content=input("Enter your message: "))]},
#     # config={"configurable": {"thread_id": 42}}
# )
# print(final_state["messages"][-1].content)

# for s in graph.stream(
#     {"messages": [HumanMessage(content=input("Enter your message: "))]}
# ):
#     print(s)
#     print("--------------------------------------------------")

# # Save the graph as a PNG
# png_data = graph.get_graph().draw_mermaid_png()
# with open("workflow_diagram.png", "wb") as f:
#     f.write(png_data)