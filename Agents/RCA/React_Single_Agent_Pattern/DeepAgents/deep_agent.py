from dotenv import load_dotenv
import os
import time
from deepagents import create_deep_agent
from langfuse import get_client
from langfuse.langchain import CallbackHandler
from langchain.chat_models import init_chat_model

import loki
import prometheus
import tempo

load_dotenv('.env')
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./service-account-key.json"
os.environ["LANGFUSE_SECRET_KEY"]
os.environ["LANGFUSE_PUBLIC_KEY"]
os.environ["LANGFUSE_BASE_URL"]

# Initialize Langfuse client
langfuse = get_client()

# Verify connection
if langfuse.auth_check():
    print("Langfuse client is authenticated and ready!")
else:
    print("Authentication failed. Please check your credentials and host.")

# Initialize Langfuse CallbackHandler for LangChain (tracing)
langfuse_handler = CallbackHandler()

model = init_chat_model(model="gemini-2.5-flash")

def get_system_prompt(alert_message: str, alert_occurred_time: str) -> str:

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
{loki.get_all_loki_labels()}
#### Metric List
{prometheus.get_all_metrics()}
"""

    return system_prompt

tools = [loki.run_loki_logql, loki.get_loki_label_values, loki.get_list_of_streams, prometheus.run_prometheus_promql, prometheus.get_prometheus_label_values, prometheus.get_all_prometheus_labels, prometheus.get_labels_and_values_for_metric, tempo.run_tempo_query_trace]

def start_alert_cause_analysis(alert_info: dict):

  alert_message = f"AlertName: {alert_info.labels.get('alertname')}\nLabels: {alert_info.labels}\nAnnotations: {alert_info.annotations}\nQuery: {alert_info.query}\nLog Message: {alert_info.log_message}"
  alert_occurred_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

  deep_agent = create_deep_agent(
    model=model,
    tools=tools,
    system_prompt=get_system_prompt(alert_message, alert_occurred_time)
  )
  deep_agent.invoke({
      "messages": [{"role": "user", "content": "analyze what is alert cause."}],
  }, config={"callbacks": [langfuse_handler]})