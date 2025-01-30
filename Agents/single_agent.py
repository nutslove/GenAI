# from langchain_community.agent_toolkits.load_tools import load_tools
# from langchain.agents import initialize_agent, AgentType
# from langchain_aws import ChatBedrock, ChatBedrockConverse
# import langchain
# from typing import Optional
# from pydantic import BaseModel, Field

# def main():
#     langchain.verbose = True # Trueに設定するとデバックログが表示される
#     chat = ChatBedrock(
#         model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
#         model_kwargs={
#             "temperature": 0.1,
#             # "max_tokens": 8000,
#         }
#     )
#     tools = load_tools(["terminal"], llm=chat,allow_dangerous_tools=True)
#     agent_chain = initialize_agent(tools, chat, agent="zero-shot-react-description")
#     result = agent_chain.invoke("What is your currrent directory?")
#     print(result)

# if __name__ == '__main__':
#     main()

from langchain_core.tools import tool
from langchain_experimental.utilities import PythonREPL
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_aws import ChatBedrock
from langchain_aws.retrievers import AmazonKnowledgeBasesRetriever
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
    you should print it out with `print(...)`. This is visible to the user."""
    try:
        result = repl.run(code)
    except BaseException as e:
        return f"Failed to execute. Error: {repr(e)}"
    result_str = f"Successfully executed:\n\`\`\`python\n{code}\n\`\`\`\nStdout: {result}"
    return result_str

@tool
def shell_tool(
    command: Annotated[str, "The shell command to execute."],
) -> str:
    """Use this to execute shell commands. This is visible to the user."""
    try:
        result = subprocess.run(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except BaseException as e:
        return f"Failed to execute. Error: {repr(e)}"
    result_str = f"Successfully executed:\n\`\`\`shell\n{command}\n\`\`\`\nStdout: {result.stdout}\nStderr: {result.stderr}"
    return result_str

@tool
def rag_analysis(message_text: str, system: str, region: str) -> str:
    chain = retriever | (lambda docs: "\n\n".join(doc.page_content for doc in docs))
    result = chain.invoke(message_text)
    chain = prompt_for_rag | llm | StrOutputParser()
    response = chain.invoke({
        "error_message": message_text,
        "data_from_rag": result,
    })
    return response

# Define available tools
tools = [python_repl_tool, shell_tool]
tool_node = ToolNode(tools)
llm = ChatBedrock(
    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
    model_kwargs={
        "temperature": 0.1,
        # "max_tokens": 8000,
    }
).bind_tools(tools)

retriever = AmazonKnowledgeBasesRetriever(
    knowledge_base_id=os.getenv('KNOWLEDGEBASE_ID'),
    retrieval_config={
        "vectorSearchConfiguration": {
            "numberOfResults": 4
        }
    },
)

prompt_for_rag = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant that compares the given Error Message with the Data from RAG to determine whether the Error Message corresponds to a known issue.\n\
            If it is identified as a known issue, provide the relevant information from the Data from RAG.\n\
            If it is determined to be a new issue, propose the possible causes, impacts, and solutions for the Error Message.\n\
            Regarding the solution, execute commands that don't change anyting to investigate the issue(e.g. ls -l).\
            Do not execute commands to change config(e.g. rm -f /var/log/messages)!\
            Must answer in Japanese.",
        ),
        ("human", "## Error Message\n{error_message}\n\n## Data from RAG\n{data_from_rag}"),
    ]
)

def should_continue(state: MessagesState) -> Literal["tools", "__end__"]:
    messages = state['messages']
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return "__end__"

def call_llm(state: MessagesState):
    messages = state['messages']

    # Invoking `llm` will automatically infer the correct tracing context
    response = llm.invoke(messages)
    return {"messages": [response]}

workflow = StateGraph(MessagesState)

workflow.add_node("agent", call_llm)
workflow.add_node("tools", tool_node)

workflow.add_edge("__start__", "agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
)
workflow.add_edge("tools", 'agent')

graph = workflow.compile()

final_state = graph.invoke(
    {"messages": [HumanMessage(content=input("Enter your message: "))]},
    # config={"configurable": {"thread_id": 42}}
)
print(final_state["messages"][-1].content)

# Save the graph as a PNG
png_data = graph.get_graph().draw_mermaid_png()
with open("workflow_diagram.png", "wb") as f:
    f.write(png_data)
