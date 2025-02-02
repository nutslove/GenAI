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
import os
import random

# def main():
#   text_message = input("Please enter a message: ")


# if __name__ == '__main__':
#     main()

# print("AWS_ACCESS_KEY_ID:", os.getenv("AWS_ACCESS_KEY_ID"))
# print("AWS_SECRET_ACCESS_KEY:", os.getenv("AWS_SECRET_ACCESS_KEY"))
# print("AWS_DEFAULT_REGION:", os.getenv("AWS_DEFAULT_REGION"))
# print("KNOWLEDGEBASE_ID:", os.getenv("KNOWLEDGEBASE_ID"))

class State(MessagesState):
    next: str
    system: str
    region: str
    account_id: str

retriever = AmazonKnowledgeBasesRetriever(
    knowledge_base_id=os.getenv('KNOWLEDGEBASE_ID'),
    retrieval_config={
        "vectorSearchConfiguration": {
            "numberOfResults": 4
        }
    },
)

llm = ChatBedrock(
    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0", model_kwargs={"temperature": 0.1}
)

prompt_for_rag = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant that compares the given Error Message with the Data from RAG to determine whether the Error Message corresponds to a known issue.\n\
            If it is identified as a known issue, provide the relevant information from the Data from RAG and respond with FINISH.",
        ),
        ("human", "## Error Message\n{error_message}\n\n## Data from RAG\n{data_from_rag}"),
    ]
)

# prompt_for_rag = (
#   "You are a helpful assistant that compares the given Error Message with the Data from RAG to determine whether the Error Message corresponds to a known issue."
#   "If it is identified as a known issue, provide the relevant information from the Data from RAG and respond with FINISH."
# )

@tool
def rag_analysis(state: State) -> str:
    """
    Perform RAG (Retrieval-Augmented Generation) analysis on the given message.

    Args:
        message_text (str): The input message to analyze.
        system (str): The system context.
        region (str): The AWS region.

    Returns:
        str: The result of the RAG analysis.
    """
    chain = retriever | (lambda docs: "\n\n".join(doc.page_content for doc in docs))
    result = chain.invoke(state["messages"][-1].content)
    chain = prompt_for_rag | llm | StrOutputParser()
    response = chain.invoke({
        "error_message": state["messages"][-1].content,
        "data_from_rag": result,
    })
    return response

@tool
def aws_personol_health_dashboard_check(state: State) -> str:
    """
    Check the AWS Personal Health Dashboard for the given region and account ID.
    """

    return random.choice(["ECS Service is running", "ECS Service is down"])

@tool
def alert_status_check(state: State) -> str:
    """
    Check the alert status for the given system.
    """
    return random.choice(["CPU Usage Alert is firing", "Memory Usage Alert is firing", "There are no alerts firing"])

members = ["aws_personol_health_dashboard_check","alert_status_check"]
options = members + ["FINISH"]

system_prompt = (
    "You are a supervisor tasked with managing a conversation between the"
    f" following workers: {members}. Given the following user request,"
    " respond with the worker to act next. Each worker will perform a"
    " task and respond with their results and status. When finished,"
    " respond with FINISH."
)

class Router(TypedDict):
    next: Literal["aws_personol_health_dashboard_check", "alert_status_check", "FINISH"]

def routing_for_rag(state: State) -> Literal["supervisor", "__end__"]:
    messages = state['messages']
    print("messages:\n", messages)
    last_message = messages[-1]
    print("last_message:\n", last_message)
    # if last_message.tool_calls:
    #     return "supervisor"
    return "__end__"

def routing_for_supervisor(state: State) -> Literal["aws_personol_health_dashboard_check", "alert_status_check", "__end__"]:
    messages = state["messages"]
    last_message = messages[-1]
    print("messages:\n", messages)
    print("last_message:\n", last_message)

    return "aws_personol_health_dashboard_check"

def supervisor_node(state: State) -> Command[Literal["aws_personol_health_dashboard_check","alert_status_check", "__end__"]]:
    messages = [
        {"role": "system", "content": system_prompt},
    ] + state["messages"]
    response = llm.with_structured_output(Router).invoke(messages)
    goto = response["next"]
    if goto == "FINISH":
        goto = END
    return Command(goto=goto, update={"next": goto})

rag_agent = create_react_agent(llm, tools=[rag_analysis])

def rag_analysis_node(state: State) -> Command[Literal["supervisor", "__end__"]]:
    # messages = [
    #     {"role": "system", "content": prompt_for_rag},
    # ] + state["messages"]
    messages = state["messages"]
    result = rag_agent.invoke(messages)
    goto = result["next"]
    if goto == "FINISH":
        goto = END
    return Command(
        update={
            # "messages": [
            #     HumanMessage(content=result["messages"][-1].content, name="rag_analysis")
            # ],
            "next": goto
        },
        goto=goto,
    )

alert_status_check_agent = create_react_agent(llm, tools=[alert_status_check])

def alert_status_check_node(state: State) -> Command[Literal["supervisor"]]:
    result = alert_status_check_agent.invoke(state)
    return Command(
        update={
            "messages": [
                HumanMessage(content=result["messages"][-1].content, name="alert_status_check_agent")
            ]
        },
        goto="supervisor",
    )

aws_personol_health_dashboard_check_agent = create_react_agent(llm, tools=[aws_personol_health_dashboard_check])

def aws_personol_health_dashboard_check_node(state: State) -> Command[Literal["supervisor"]]:
    result = aws_personol_health_dashboard_check_agent.invoke(state)
    return Command(
        update={
            "messages": [
                HumanMessage(content=result["messages"][-1].content, name="aws_personol_health_dashboard_check")
            ]
        },
        goto="supervisor",
    )

builder = StateGraph(State)
builder.add_node("supervisor", supervisor_node)
builder.add_node("rag_analysis", rag_analysis_node)
builder.add_node("alert_status_check", alert_status_check_node)
builder.add_node("aws_personol_health_dashboard_check", aws_personol_health_dashboard_check_node)
builder.add_edge(START, "rag_analysis")
builder.add_conditional_edges("rag_analysis", routing_for_rag)
builder.add_conditional_edges("supervisor", routing_for_supervisor)
builder.add_edge("aws_personol_health_dashboard_check", "supervisor")
builder.add_edge("alert_status_check", "supervisor")
graph = builder.compile()

# Save the graph as a PNG
png_data = graph.get_graph().draw_mermaid_png()
with open("workflow_diagram.png", "wb") as f:
    f.write(png_data)

for s in graph.stream(
    {
        "messages": [("user", input("input messages: \n"))],
        "system": "goku",
        "region": "ap-northeast-1",
        "account_id": "123456789012",
    }, subgraphs=True
):
    print(s)
    print("----")