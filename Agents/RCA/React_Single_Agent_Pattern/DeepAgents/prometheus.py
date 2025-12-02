import requests
from typing import Annotated

PROMETHEUS_WRAPPER_ENDPOINT = "http://o11y-tool:8070/o11y/prometheus/api/v1"

def get_all_metrics() -> str:
  try:
    result = requests.post(f"{PROMETHEUS_WRAPPER_ENDPOINT}/all_metrics", timeout=10)
    result_json = result.json()
    all_metrics_exist = ", ".join(result_json) # Listで返ってくるので、文字列に変換
  except requests.exceptions.RequestException as e:
    all_metrics_exist = f"Failed to get metrics from Prometheus. Error: {repr(e)}"
  return all_metrics_exist

def run_prometheus_promql(
  query: Annotated[str, "The PromQL query to execute against Prometheus."]
) -> str:
  """
  Use this to excute PromQL query against Prometheus.

  Args:
    query: PromQL query to excute against Prometheus.
  Returns:
    The result of the PromQL queries.
  """

  params = {
    'query': query
  }

  try:
    result = requests.post(f"{PROMETHEUS_WRAPPER_ENDPOINT}/query_range", params=params, timeout=10)
    result_str = f"""#### PromQL\n`{query}`\n\n#### Result\n{result.json()}"""
    return result_str
  except requests.exceptions.RequestException as e:
    return f"Failed to execute PromQL: {query}. Error: {repr(e)}"

def get_prometheus_label_values(
  label: Annotated[str, "A label in Prometheus for checking its values."]
) -> str:
  """
  Use this to get the values that the label has from Prometheus.

  Args:
    label: A label in Prometheus to check its values.
  Returns:
    The values of label.
  """

  params = {
    'label': label
  }

  try:
    result = requests.post(f"{PROMETHEUS_WRAPPER_ENDPOINT}/label_values", params=params, timeout=10)
    result_json = result.json()
    values_label_has = f"""#### Prometheus Label\n`{label}`\n\n#### Values of label\n{", ".join(result_json)}"""
    return values_label_has
  except requests.exceptions.RequestException as e:
    return f"Failed to get the values of label[{label}] from Prometheus. Error: {repr(e)}"

def get_all_prometheus_labels() -> str:
  """
  Use this to get all labels that exist in Prometheus.

  Returns:
    The list of all labels that exist in Prometheus.
  """

  try:
    result = requests.post(f"{PROMETHEUS_WRAPPER_ENDPOINT}/labels", timeout=10)
    result_json = result.json()
    all_labels_exist = f"""#### All Labels in Prometheus\n{", ".join(result_json)}"""
    return all_labels_exist
  except requests.exceptions.RequestException as e:
    return f"Failed to get labels from Prometheus. Error: {repr(e)}"

def get_labels_and_values_for_metric(
  metric: Annotated[str, "A metric in Prometheus for checking its labels and their values. Only provide the metric name without any labels."]
):
  """
  Use this to get the labels and their values for a specific metric from Prometheus.

  Args:
    metric: The metric name in Prometheus to retrieve labels and values for. Should be provided without any label selectors (e.g., OK: 'cpu_usage', NG: 'cpu_usage{instance="server1"}').
  Returns:
    The labels and their values of the metric.
  """

  params = {
    'metric': metric
  }

  try:
    result = requests.post(f"{PROMETHEUS_WRAPPER_ENDPOINT}/labels_values_metric_has", params=params, timeout=10)
    result_json = f"""#### Labels and their values for metric[`{metric}`]\n{result.json()}"""
    return result_json
  except requests.exceptions.RequestException as e:
    return f"Failed to get the labels and their values of metric[{metric}] from Prometheus. Error: {repr(e)}"