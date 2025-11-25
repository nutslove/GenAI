import requests
from typing import Annotated
from langchain_core.tools import tool

TEMPO_WRAPPER_ENDPOINT = "http://o11y-tool:8070/o11y/tempo/api"

@tool
def run_tempo_query_trace(
  trace_id: Annotated[str, "The trace ID to execute against Grafana Tempo."]
) -> str:
  """
  Use this to execute a trace query against Grafana Tempo.

  Args:
    trace_id: The trace ID to execute against Grafana Tempo.
  Returns:
    The result of the trace query.
  """

  params = {
    'trace_id': trace_id
  }

  try:
    result = requests.post(f"{TEMPO_WRAPPER_ENDPOINT}/query_trace", params=params, timeout=10)
    result_str = f"""#### TraceID\n`{trace_id}`\n\n#### Result\n{result.json()}"""
    return result_str
  except requests.exceptions.RequestException as e:
    return f"Failed to execute trace query. Error: {repr(e)}"