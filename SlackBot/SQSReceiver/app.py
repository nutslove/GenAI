import os
import re
from typing import Literal
from typing_extensions import TypedDict
from langgraph.graph import MessagesState, START, END
from langgraph.types import Command
from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from langchain_aws import ChatBedrock, ChatBedrockConverse
from langchain_aws.retrievers import AmazonKnowledgeBasesRetriever
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool

# Define available agents
members = ["web_researcher", "rag", "nl2sql"]
# Add FINISH as an option for task completion
options = members + ["FINISH"]

# Create system prompt for supervisor
system_prompt = (
    "You are a supervisor tasked with managing a conversation between the"
    f" following workers: {members}. Given the following user request,"
    " respond with the worker to act next. Each worker will perform a"
    " task and respond with their results and status. When finished,"
    " respond with FINISH."
)

# Define router type for structured output
class Router(TypedDict):
    """Worker to route to next. If no workers needed, route to FINISH."""
    next: Literal["web_researcher", "rag", "nl2sql", "FINISH"]

# Create supervisor node function
def supervisor_node(state: MessagesState) -> Command[Literal["web_researcher", "rag", "nl2sql", "__end__"]]:
    messages = [
        {"role": "system", "content": system_prompt},
    ] + state["messages"]
    response = llm.with_structured_output(Router).invoke(messages)
    goto = response["next"]
    print(f"Next Worker: {goto}")
    if goto == "FINISH":
        goto = END
    return Command(goto=goto)




# Slack API クライアント
slack_client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))

llm = ChatBedrock(
    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
    model_kwargs={
        "temperature": 0.1,
        # "max_tokens": 8000,
    }
)

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
            Regarding the solution, suggest commands to investigate and solve the issue.\
            Must answer in Japanese.",
        ),
        ("human", "## Error Message\n{error_message}\n\n## Data from RAG\n{data_from_rag}"),
    ]
)

def rag_analysis(message_text: str, system: str, region: str) -> str:
    chain = retriever | (lambda docs: "\n\n".join(doc.page_content for doc in docs))
    result = chain.invoke(message_text)
    chain = prompt_for_rag | llm | StrOutputParser()
    response = chain.invoke({
        "error_message": message_text,
        "data_from_rag": result,
    })
    return response

@tool
def aws_personol_health_dashboard_check(region: str, account_id: str) -> str:
    pass

def handler(event, context):
    try:
        # SQSからのイベントには Records が含まれる
        for record in event['Records']:
            # メッセージ本文を取得
            message_body = record['body']
            
            # MessageAttributesを取得
            message_attributes = record.get('messageAttributes', {})
            
            # 属性の取り出し
            thread_ts = message_attributes.get('thread_ts', {}).get('stringValue', None)
            channel_id = message_attributes.get('channel_id', {}).get('stringValue', None)
            system = message_attributes.get('system', {}).get('stringValue', None)
            region = message_attributes.get('region', {}).get('stringValue', None)

            # メッセージ内容をログに出力
            print("Message Body:", message_body)
            print("thread_ts:", thread_ts)
            print("channel_id:", channel_id)
            print("system:", system)
            print("region:", region)

            response = rag_analysis(message_body ,system, region)

            slack_client.chat_postMessage(
                channel=channel_id,
                text=response,
                thread_ts=thread_ts
            )
    except Exception as e:
        print("Error processing messages:", str(e))
        raise e
