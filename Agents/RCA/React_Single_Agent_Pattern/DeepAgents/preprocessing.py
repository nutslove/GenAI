from dataclasses import dataclass
import requests
from dotenv import load_dotenv
import os

import deep_agent

load_dotenv('.env')
grafana_api_key = os.getenv("GRAFANA_API_KEY")

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
    return alert_info