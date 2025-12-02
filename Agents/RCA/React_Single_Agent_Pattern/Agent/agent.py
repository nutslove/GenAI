from dotenv import load_dotenv
import os
import requests
import time
from langchain.agents import create_agent
from langgraph.graph import StateGraph
from langchain_google_genai import GoogleGenerativeAIEmbeddings,ChatGoogleGenerativeAI
from langgraph.prebuilt import ToolNode
from langfuse.langchain import CallbackHandler as langfuse_callback_handler
from langchain.agents.middleware import SummarizationMiddleware
from langgraph._internal._runnable import RunnableCallable
from typing import Literal, Annotated, Tuple
from dataclasses import dataclass

import state
import loki
import tempo
import prometheus

load_dotenv('.env')
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./service-account-key.json"
os.environ["LANGFUSE_SECRET_KEY"]
os.environ["LANGFUSE_PUBLIC_KEY"]
os.environ["LANGFUSE_BASE_URL"]
grafana_api_key = os.getenv("GRAFANA_API_KEY")

# model = "gemini-2.0-flash-lite"
model = "gemini-2.5-flash"

tools = [loki.run_loki_logql, loki.get_loki_label_values, loki.get_list_of_streams, prometheus.run_prometheus_promql, prometheus.get_prometheus_label_values, prometheus.get_all_prometheus_labels, prometheus.get_labels_and_values_for_metric, tempo.run_tempo_query_trace]
tool_node = ToolNode(tools)
llm = ChatGoogleGenerativeAI(
    model=model,
    temperature=0,
    max_tokens=4096, # default: 8192
)
llm_with_tools = llm.bind_tools(tools)

summarize_prompt = """
You are a conversation summarizer for an AI agent performing alert investigation and root cause analysis.

## Your Task
Summarize the conversation history while preserving all critical information needed for ongoing investigation.

## Summary Structure
Organize your summary into the following sections:

### 1. Investigation Context
- Alert/incident details (alert name, severity, affected systems, timestamps)
- Initial hypothesis or suspected cause
- Scope of impact identified

### 2. Completed Investigation Steps
For each step taken, preserve:
- What was checked (tool/command/query used)
- The actual result or finding (include specific values, error messages, metric values)
- Conclusion drawn from that step

### 3. Key Findings So Far
- Confirmed facts and evidence discovered
- Ruled-out possibilities with reasoning
- Anomalies or patterns identified

### 4. Pending Investigation Items
- What still needs to be checked
- Unanswered questions
- Recommended next steps mentioned in the conversation

## Critical Rules

DO preserve:
- Specific metric values, thresholds, and timestamps
- Error messages, log entries, and stack traces (in condensed form)
- Resource identifiers (pod names, instance IDs, service names)
- Causal relationships discovered
- User's specific requests or constraints

DO NOT remove:
- Information that could be needed to avoid redundant investigation
- Context required to understand the current investigation state
- Technical details that informed decisions

Avoid:
- Generic statements without specific findings
- Redundant repetition of the same information
- Conversational filler that adds no investigative value

## Output Format
Write the summary in clear, concise prose or structured bullet points. Prioritize information density while maintaining readability. The summary should allow the investigation to continue seamlessly without re-checking already verified items.
"""

@dataclass
class AlertData:
    status: str
    labels: dict
    annotations: dict
    query: str
    log_message: str = ""

def get_query_in_alert_from_grafana(generator_url: str) -> str:
    # print(f"[DEBUG] Original generatorURL: {generator_url}")

    if "alerting/grafana" not in generator_url:
        print("Test Alert from Contact Point")
        return "Test Alert from Contact Point"

    try:
        alert_uid = generator_url.split("/")[-2]
        # print(f"[DEBUG] Extracted alert_uid: {alert_uid}")
        SPECIFIC_ALERT_RULE_ENDPOINT = "http://grafana:3000/api/v1/provisioning/alert-rules/" + alert_uid
        # print(f"[DEBUG] Constructed API Endpoint: {SPECIFIC_ALERT_RULE_ENDPOINT}")
    except IndexError as e:
        print("Invalid generatorURL format")
        raise e

    try:
        headers = {
            "Authorization": f"Bearer {grafana_api_key}",
        }

        response = requests.get(SPECIFIC_ALERT_RULE_ENDPOINT, headers=headers, timeout=5)
        # print(f"[DEBUG] Response Status Code: {response.status_code}")
        # print(f"[DEBUG] Response Body (first 500 chars): {response.text[:500]}")

        response.raise_for_status()

        # レスポンスが空でないか確認
        if not response.text:
            print("[Warning] Empty response from Grafana API")
            return ""

        try:
            response_json = response.json()
            # print(f"[DEBUG] Parsed JSON Response: {json.dumps(response_json, indent=2)}")
        except ValueError as e:
            print(f"[Warning] Failed to parse JSON response: {e}")
            return ""

        queries = ", ".join([d["model"]["expr"] for d in response_json["data"] if "expr" in d["model"]])
        # print(f"[DEBUG] Extracted Queries: {queries}")
        return queries
    except requests.RequestException as e:
        print(f"[Error] Error fetching alert rule from Grafana API: {e}")
        raise e

def extract_alert_info(alert_data: dict) -> str:
    status = alert_data.get("status", "unknown")
    labels = alert_data.get("labels", {})
    annotations = alert_data.get("annotations", {})
    generator_url = alert_data.get("generatorURL")
    log_message = labels.get("message", "N/A")
    query = get_query_in_alert_from_grafana(generator_url)

    alert_info = AlertData(
        status=status,
        labels=labels,
        annotations=annotations,
        query=query,
        log_message=log_message,
    )
    # print(f"Extracted Alert Info: {alert_info}")
    result = start_alert_cause_analysis(alert_info)
    return result

def start_alert_cause_analysis(alert: AlertData) -> str:
    # 動的にシステムプロンプトを生成
    alert_message = f"AlertName: {alert.labels.get('alertname')}\nLabels: {alert.labels}\nAnnotations: {alert.annotations}\nQuery: {alert.query}\nLog Message: {alert.log_message}"
    alert_occurred_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    loki_labels = loki.get_all_loki_labels()
    metrics = prometheus.get_all_metrics()

    system_prompt = f"""
## Role
You are a Root Cause Analysis (RCA) agent specialized in analyzing alerts from Grafana and investigating their causes using tools below.
You have access to the following tools:
1. run_loki_logql: Use this to execute LogQL queries to retrieve logs from Grafana Loki.
    - NG LogQL example:
        - `{{{{otelTraceID="c58ff9edaead7b757a3ae3411005945f"}}}}` # Missing curly braces around the selector
        - `{{{{job="varlogs"}}}} |= "error" | limit 10` # there is no 'limit' clause in LogQL
        - `{{{{namespace="monitoring", service_name="clickhouse"}}}} | tail` # there is no 'tail' clause in LogQL
        - `{{{{app="nginx"}}}} | sort` # there is no 'sort' clause in LogQL
        - `{{{{pod="langfuse-clickhouse-shard0-0"}}}} | sort @timestamp desc | limit 10` # there is no 'limit' or 'sort' clause in LogQL
        - `{{{{}}}} |~ "be8af83da40279d7f9cfb2bb256009fb"` # labels(selector) are required in LogQL queries
        - `{{{{pod="langfuse-clickhouse-shard0-0"}}}} | count_over_time([5m])` # wrong `count_over_time` usage
        - `count_over_time({{{{namespace="monitoring"}}}}[1h]) by (pod)` # by clause is not supported in `count_over_time`
        - `{{{{service_name=~".*"}}}} |~ "d49cfc23a353cd76f4c8244c373b2b01"` # When using the =~ operator, you cannot specify only ".*" without any other characters. If you want to specify everything without characters, please specify ".+" instead.
        - `{{{{pod="langfuse-clickhouse-shard0-0"}}}} |~ "error|warn|fail" [1h]` # Wrong usage of range selector (e.g., [1h]); requires `count_over_time` or other functions
        - `{{{{pod="langfuse-clickhouse-shard0-0"}}}} [30m]` # Wrong usage of range selector (e.g., [30m]); requires `count_over_time` or other functions
    - OK LogQL example:
        - `{{{{service_name=~".+"}}}} |= "c58ff9edaead7b757a3ae3411005945f"`
        - `{{{{job=~".*varlogs.*"}}}} |= "error"`
        - `count_over_time({{{{namespace="monitoring", service_name=~"clickhouse.*"}}}}[5m])`
2. get_loki_label_values: Use this to get the values that a specific label has from Grafana Loki.
3. get_list_of_streams: Use this to get the list of log streams in Grafana Loki.
4. run_prometheus_promql: Use this to execute PromQL queries to retrieve metrics from Prometheus.
5. get_prometheus_label_values: Use this to get the values that a specific label has from Prometheus.
6. get_all_prometheus_labels: Use this to get all labels that exist in Prometheus.
7. get_labels_and_values_for_metric: Use this to get the labels and their values for a specific metric from Prometheus.
8. run_tempo_query_trace: Use this to execute a trace query against Grafana Tempo.
    -  The format of the trace ID is a 32-character hexadecimal string (e.g., "4bf92f3577b34da6a3ce929d0e0e4736", "98100898d812021273ec14bd273e4dda"). If you find a trace ID in the logs, get detailed trace information using this tool with the trace ID.

## Available Information
#### Alert Message
{alert_message}
#### Alert Occurred Time
{alert_occurred_time}
#### Loki Labels List
{loki_labels}
#### Metric List
{metrics}
"""

    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        state_schema=state.RCAAgentState,
        middleware=[
            SummarizationMiddleware(
                model=model,
                trigger=("tokens", 4000),
                keep=("messages", 5),
                summary_prompt=summarize_prompt,
                trim_tokens_to_summarize=2000,
            ),
        ],
    )
    result = agent.invoke({
        "messages": [{"role": "user", "content": "analyze what is alert cause."}],
        "alert_message": alert_message,
        "alert_occurred_time": alert_occurred_time,
        "metric_list": metrics,
        "loki_labels_list": loki_labels,
    }, config={"recursion_limit": 120, "callbacks": [langfuse_callback_handler()]})

    return result["messages"][-1].content