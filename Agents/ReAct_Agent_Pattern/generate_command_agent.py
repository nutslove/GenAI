from langchain_core.tools import tool
from langchain_experimental.utilities import PythonREPL
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_aws import ChatBedrock
from langgraph.graph import StateGraph, MessagesState, END
from langgraph.prebuilt import ToolNode
from typing import Literal, Annotated
from typing_extensions import TypedDict
import subprocess
import os
from pydantic import BaseModel, Field
from IPython.display import display, Image
from rag_agent import graph as rag_graph
from state import State, Response
from execute_command_agent import graph as execute_command_graph

# This executes code locally, which can be unsafe
repl = PythonREPL()

# class Response(TypedDict):
#     analysis_results: str = Field(..., description="The root cause analysis of the error message.")
#     final_command: str = Field(..., description="The final command to execute to resolve the issue.")

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
# tools = [python_repl_tool, shell_tool]
tools = [python_repl_tool, shell_tool, Response]
tool_node = ToolNode(tools)

# Force the model to use tools by passing tool_choice="any"
llm_with_tools = ChatBedrock(
    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
    model_kwargs={"temperature": 0.1}
# ).bind_tools(tools)
).bind_tools(tools, tool_choice="any")

# Define the function that responds to the user
def respond(state: State):
    # Construct the final answer from the arguments of the last tool call
    tool_call = state["messages"][-1].tool_calls[0]
    response = Response(**tool_call["args"])
    # Since we're using tool calling to return structured output,
    # we need to add  a tool message corresponding to the WeatherResponse tool call,
    # This is due to LLM providers' requirement that AI messages with tool calls
    # need to be followed by a tool message for each tool call
    tool_message = {
        "type": "tool",
        "content": "Here is your structured response",
        "tool_call_id": tool_call["id"],
    }
    # We return the final answer
    return {"final_response": response, "messages": [tool_message]}

# def should_continue(state: State) -> Literal["command_run_tools", "__end__"]:
def should_continue(state: State) -> Literal["command_run_tools", "respond", "__end__"]:
    print("\nexecute_command_agent [should_continue] state:\n-----------------------------------\n", state, "\n-----------------------------------")
    messages = state['messages']
    last_message = messages[-1]
    print("\nexecute_command_agent [should_continue] Last message:\n-----------------------------------\n", last_message, "\n-----------------------------------")
    # if state["known_issue"] and state["predefined_command"] != "":
    if state["known_issue"] and state["predefined_command"] != "":
        # state["final_command"] = state["predefined_command"]
        # state["analysis_results"] = last_message.content
        state["final_response"].final_command = state["predefined_command"]
        state["final_response"].analysis_results = messages[-2].content # rag_agentの結果は一つ前のメッセージに入っている
        return "__end__"
    elif len(last_message.tool_calls) == 1 and last_message.tool_calls[0]["name"] == "Response":
        return "respond"
    elif last_message.tool_calls:
        return "command_run_tools"
    # return "__end__"

system_prompt = f"""
You are a helpful assistant that can execute commands using the tools provided to check the status of resources you need to verify while troubleshooting the issue.
You can use the following tools: python_repl_tool, shell_tool.
Given the following user request and an associated error message, perform a root cause analysis of the error message and propose command(s) to resolve the issue.

Let's think step by step:
1. Analyze the error message and Think what should check first.(e.g. Check if IAM user exists)
2. Check the status of the resources that you need to verify. (e.g. Check the status of the IAM user)
3. If you need to check further, use the tools provided to verify the status of the resources. (e.g. python_repl_tool, shell_tool)
4. If you find any issue, propose a command to resolve the issue. (e.g. aws iam create-user --user-name <USER_NAME>)

Never execute any command that changes(create/update/delete) the state of resources.
You can use read-only/reference commands like 'aws ecs describe-services --cluster <CLUSTER_NAME> --services <SERVICE_NAME>' to check the status of an ECS service or 'aws ecs list-clusters' to confirm the name of the cluster while generating the final command.
For example, you can use the command 'aws ecs describe-services --cluster <CLUSTER_NAME> --services <SERVICE_NAME>' to check the status of an ECS service or 'aws ecs list-clusters' to confirm the name of the cluster.
In the final answer, you must provide analysis results in the `analysis_results` field for the error message and the information provided by the previous worker.
In the final answer, you must also provide a command to create/update/delete the state of resources in the `final_command` field in a ready-to-run format like 'aws ecs update-service --cluster <CLUSTER_NAME> --service <SERVICE_NAME> --task-definition <TASK_DEFINITION_NAME>:<NEW_REVISION>'.
Make sure the final command is correct and ready to run without any comments.
"""

def call_llm(state: State):
    systemprompt = SystemMessage(system_prompt)
    print("\nexecute_command_agent [call_llm] State:\n-----------------------------------\n", state, "\n-----------------------------------")

    try:
        # response = llm.with_structured_output(Response).invoke([systemprompt] + state['messages'])
        response = llm_with_tools.invoke([systemprompt] + state['messages'])
    except Exception as e:
        print("\nError occurred in aws_phd_agent call_llm llm_model.invoke:\n----------------------------------------------\n", e)
    finally:
        # response = llm.with_structured_output(Response).invoke([system_prompt] + state["messages"] + [HumanMessage(state["messages"][0].content)])
        response = llm_with_tools.invoke([systemprompt] + state["messages"] + [HumanMessage(state["messages"][0].content)])
    return {"messages": [response]}

workflow = StateGraph(State)

workflow.add_node("command_run_agent", call_llm)
workflow.add_node("respond", respond)
workflow.add_node("command_run_tools", tool_node)
workflow.add_node("rag_agent", rag_graph)

workflow.add_edge("__start__", "rag_agent")
workflow.add_edge("rag_agent", "command_run_agent")
workflow.add_conditional_edges(
    "command_run_agent",
    should_continue,
)
workflow.add_edge("command_run_tools", 'command_run_agent')
workflow.add_edge("respond", END)

graph = workflow.compile()

def main():
    final_state = graph.invoke({
        "messages": [("user", input("input error message:\n"))],
        "system_name": "Factory",
        "region": "ap-northeast-1",
        "account_id": "0123456789",
        "known_issue": False,
        "predefined_command": "",
        # "analysis_results": "",
        # "final_command": "",
        "final_response": Response(analysis_results="", final_command="")
    })

    # print("\nFinal analysis_results:\n------------------------------------\n", final_state["analysis_results"])
    # print("\nFinal command:\n------------------------------------\n", final_state["final_command"])

    # print("\nFinal final_response:\n------------------------------------\n", final_state["final_response"])
    print("\nFinal analysis_results:\n------------------------------------\n", final_state["final_response"].analysis_results)
    print("\nFinal final_command:\n------------------------------------\n", final_state["final_response"].final_command)

    execute_or_not = input("Do you want to execute the command? (yes/no): ")
    if execute_or_not == "yes":
        execute_command_graph.invoke(
            {
                "messages": [HumanMessage(content=final_state["final_response"].final_command)]
            }
        )

    # Save the graph as a PNG
    png_data = graph.get_graph().draw_mermaid_png()
    with open("workflow_diagram.png", "wb") as f:
        f.write(png_data)

if __name__ == "__main__":
    main()

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