
from dotenv import load_dotenv
import os
import requests
import time
from langgraph.graph import StateGraph
from langchain_google_genai import GoogleGenerativeAIEmbeddings,ChatGoogleGenerativeAI
from langgraph.prebuilt import ToolNode
from langfuse.callback import CallbackHandler as langfuse_callback_handler
from typing import Literal, Annotated, Tuple
from dataclasses import dataclass

import state
import loki

load_dotenv('.env')
grafana_api_key = os.getenv("GRAFANA_API_KEY")

tool_node = ToolNode([loki.run_loki_logql, loki.get_loki_label_values, loki.get_list_of_streams]) 
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-lite",
    temperature=0,
    max_tokens=4096, # default: 8192
)
llm_with_tools = llm.bind_tools(tool_node)

@dataclass
class AlertData:
    status: str
    labels: dict
    annotations: dict
    query: str
    log_message: str = ""

def get_query_in_alert_from_grafana(generator_url: str) -> str:
    if "?orgId=" in generator_url:
        print("Test Alert from Contact Point")
        return "Test Alert from Contact Point"
    try:
        alert_uid = generator_url.split("/")[-2]
        SPECIFIC_ALERT_RULE_ENDPOINT = generator_url.split("alerting/grafana")[0] + "api/v1/provisioning/alert-rules/" + alert_uid
    except IndexError as e:
        print("Invalid generatorURL format")
        raise e

    try:
        headers = {
            "Authorization": f"Bearer {grafana_api_key}",
        }

        response = requests.get(SPECIFIC_ALERT_RULE_ENDPOINT, headers=headers, timeout=5)
        response.raise_for_status()
        response_json = response.json()
        queries = ", ".join([d["model"]["expr"] for d in response_json["data"] if "expr" in d["model"]])
        return queries
    except requests.RequestException as e:
        print(f"Error fetching alert rule from Grafana API: {e}")
        raise e

def extract_alert_info(alert_data: dict) -> str:
    status = alert_data.get("status", "unknown")
    labels = alert_data.get("labels", {})
    annotations = alert_data.get("annotations", {})
    generator_url = alert_data.get("generatorURL")
    query = get_query_in_alert_from_grafana(generator_url)

    alert_info = AlertData(
        status=status,
        labels=labels,
        annotations=annotations,
        query=query,
        log_message=labels.get("message", "N/A")
    )
    # print(f"Extracted Alert Info: {alert_info}")
    result = start_alert_cause_analysis(alert_info)
    return result

def start_alert_cause_analysis(alert: AlertData):
    workflow = StateGraph(state.RCAAgentState)
    workflow.add_node("call_llm", call_llm)
    workflow.add_node("tool_execution", tool_node)
    workflow.add_edge("__start__", "call_llm")
    workflow.add_conditional_edge("call_llm", should_continue)
    graph = workflow.compile()
    final_state = graph.invoke({
        "alert_message": f"AlertName: {alert.labels.get("alertname")}\nLabels: {alert.labels}\nAnnotations: {alert.annotations}\nQuery: {alert.query}\nLog Message: {alert.log_message}",
        "alert_occurred_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "metric_list": [],
        "loki_labels_list": "",
    },config={"recursion_limit": 120, "callbacks": [langfuse_callback_handler()]})
    return final_state["messages"][-1]["content"]

def should_continue(state: state.RCAAgentState) -> Literal["run_tools","__end__"]:
    messages = state['messages']
    last_message = messages[-1]['content']
    if not last_message.tool_calls:
        return "__end__"
    return "run_tools"

def call_llm(state: state.RCAAgentState):
    system_prompt = """
You are a Root Cause Analysis (RCA) agent specialized in analyzing alerts from Grafana and investigating their causes using tools.
"""
    res = llm_with_tools.invoke([system_prompt] + state["messages"])
    return {"messages": res}