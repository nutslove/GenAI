import requests
import os
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from state import State

LOKI_WRAPPER_ENDPOINT = "http://o11y-tool:8070/o11y/loki/api/v1"

def get_all_loki_labels(state: State) -> dict:
  try:
    result = requests.post(f"{LOKI_WRAPPER_ENDPOINT}/labels", timeout=10)
    result_json = result.json()
    all_labels_exist = ", ".join(result_json) # Listで返ってくるので、文字列に変換
    print(f"List of labels: {all_labels_exist}")
  except requests.exceptions.RequestException as e:
    print(f"Failed to get labels from Loki. Error: {repr(e)}")
    all_labels_exist = f"Failed to get labels from Loki. Error: {repr(e)}"

  return {"loki_labels_list": all_labels_exist}

@tool
def run_loki_logql(
  query: Annotated[str, "The LogQL query to excute against Grafana Loki."]
  # TODO: デフォルトでは1時間前までのログを対象とする。もしそれより前のログが必要な場合はstart引数も追加（バックエンドのloki.go側でUNIX TIMESTAMPに変換する必要あり）
) -> str:
  """
  Use this to excute LogQL query against Grafana Loki.
  Do not include "limit" in the query, as LogQL does not have a "limit" clause.
  The query must be a valid LogQL query.
  Example of a valid(OK) LogQL query:
    - {service_name="alloy"}
    - {pod="alloy-shdq6"} |~ "warn"
    - count_over_time({pod="alloy-shdq6"} |~ "warn"[5m])
  Example of an invalid(NG) LogQL query:
    - {service_name="alloy"} | limit 10
    - {service_name="alloy"} | count_over_time(1s)

  Args:
      query: LogQL query to excute for Grafana Loki.(Do not include "limit" in the query, as LogQL does not have a "limit" clause.)
  Returns:
      The result of the LogQL queries.
  """

  params = {
    'query': query
  }

  try:
    result = requests.post(f"{LOKI_WRAPPER_ENDPOINT}/query_range", params=params, timeout=10)
    print(f"[run_loki_logql] LogQL: {query}, Result: {result.json()}")
    result_str = f"""#### LogQL\n`{query}`\n\n#### Result\n{result.json()}"""
    return result_str
  except requests.exceptions.RequestException as e:
    print(f"Failed to execute LogQL. Error: {repr(e)}")
    return f"Failed to execute LogQL: {query}. Error: {repr(e)}"
  

@tool
def get_loki_label_values(
  label: Annotated[str, "A label in Loki for checking its values."]
):
  """
  Use this to get the values that a specific label has from Grafana Loki.

  Args:
    sid: system name.
    label: A specific label in Loki to check its values.
  Returns:
    The values of label.
  """

  params = {
    'label': label
  }

  try:
    result = requests.post(f"{LOKI_WRAPPER_ENDPOINT}/label_values", params=params, timeout=10)
    result_json = result.json()
    values_label_has = f"""#### Loki Label\n`{label}`\n\n#### Values of label\n{", ".join(result_json)}"""
    print(f"the values that the label has: {values_label_has}")
    return values_label_has
  except requests.exceptions.RequestException as e:
    print(f"Failed to get the values of label[{label}] from Loki. Error: {repr(e)}")
    return f"Failed to get the values of label[{label}] from Loki. Error: {repr(e)}"

@tool
def get_list_of_streams(
  selector: Annotated[str, "A label selector part of LogQL to check its streams (Only provide the label selector portion. Do not include filter operators, parser expressions, or line format expressions.)"]
):
  """
  Use this to retrieve streams matching a specific label selector from Grafana Loki.

  Args:
    sid: system name.
    selector: A specific LogQL label selector to query streams for. Only provide the label selector portion. Do not include filter operators, parser expressions, or line format expressions.
  Returns:
    Streams matching the specified label selector.
  """

  params = {
    'selector': selector
  }

  try:
    result = requests.post(f"{LOKI_WRAPPER_ENDPOINT}/streams_selector_has", params=params, timeout=10)
    result_json = result.json()
    print(f"the streams that the label selector has: {result_json}")
    result_str = f"""#### Label Selector\n`{selector}`\n\n#### Streams\n{result_json}"""
    return result_str
  except requests.exceptions.RequestException as e:
    print(f"Failed to get the streams of label selector [{selector}] from Loki. Error: {repr(e)}")
    return f"Failed to get the streams of label selector [{selector}] from Loki. Error: {repr(e)}"