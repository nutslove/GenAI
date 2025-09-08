import json
import logging
from urllib.parse import urlencode
from typing import Optional, List, Dict, Any, Union

import requests
from mcp.server.fastmcp import FastMCP

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("Loki")

# Lokiのエンドポイント（環境に応じて変更）
LOKI_ENDPOINT = "http://192.168.0.176:31100/loki/api/v1"

@mcp.tool()
def query_range(
    query: str,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Query Loki for log or metric data within a time range.
    
    Args:
        query: LogQL query string
        limit: Maximum number of entries to return. Default: 100
    
    Returns:
        List containing query results with metadata and entries, or error message if no data found
    """
    try:
        # Lokiへのクエリパラメータを構築
        query_params = {'query': query}
        
        if limit:
            query_params['limit'] = str(limit)

        logger.info(f"LogQL Request: logql={query}")

        # Lokiエンドポイントへのリクエスト
        full_url = f"{LOKI_ENDPOINT}/query_range?{urlencode(query_params)}"

        headers = {'X-Scope-OrgID': 'homelab'}

        response = requests.get(full_url, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"Loki request failed: status={response.status_code}, body={response.text}")
            raise Exception(f"failed to get query range response from loki: {response.status_code}")
        
        # デバッグ用（生の応答をログ出力）
        # logger.info(f"raw response from loki: status={response.status_code}, body={response.text}")
        
        # JSON応答の解析
        try:
            loki_response = response.json()
        except json.JSONDecodeError as e:
            logger.error(f"failed to unmarshal response json: {e}")
            raise Exception("failed to unmarshal response json")
        
        # 結果の処理
        result = []
        data = loki_response.get('data', {})
        result_type = data.get('resultType', '')
        raw_result = data.get('result', [])
        
        if result_type == "streams":
            if len(raw_result) > 0:
                result.append({"data_type": "log"})
                
                for log_result in raw_result:
                    stream = log_result.get('stream', {})
                    values = log_result.get('values', [])
                    
                    entries = []
                    for value in values:
                        entries.append({
                            "timestamp": value[0],
                            "value": value[1]
                        })
                    
                    item = {
                        "labels": stream,
                        "entries": entries
                    }
                    result.append(item)
            else:
                result.append({"data": "データが見つかりませんでした。検索条件を変更してお試しください。(存在しないlabelを指定している可能性があります。labelを確認してください。)"})
                
        elif result_type == "matrix":
            if len(raw_result) > 0:
                result.append({"data_type": "metric"})
                
                for metric_result in raw_result:
                    metric = metric_result.get('metric', {})
                    values = metric_result.get('values', [])
                    
                    entries = []
                    for value in values:
                        entries.append({
                            "timestamp": value[0],
                            "value": value[1]
                        })
                    
                    item = {
                        "labels": metric,
                        "entries": entries
                    }
                    result.append(item)
            else:
                result.append({"data": "データが見つかりませんでした。検索条件を変更してお試しください。(存在しないlabelを指定している可能性があります。labelを確認してください。)"})
        
        # logger.info(f"result: {result}")  # デバッグ用
        
        return result
        
    except requests.RequestException as e:
        logger.error(f"failed to get query range response from loki: {e}")
        raise Exception(f"failed to get query range response from loki: {str(e)}")
    except Exception as e:
        logger.error(f"unexpected error: {e}")
        raise Exception(f"internal server error: {str(e)}")

@mcp.tool()
def get_all_labels() -> List[str]:
    """
    Get all available label names from Loki.
    
    Returns:
        List of all available label names
    """
    try:        
        full_url = f"{LOKI_ENDPOINT}/labels"

        headers = {'X-Scope-OrgID': 'homelab'}

        response = requests.get(full_url, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"Loki labels query failed: status={response.status_code}, body={response.text}")
            raise Exception(f"failed to get labels from loki: {response.status_code}")
        
        # デバッグ用（生の応答をログ出力）
        logger.info(f"raw response from loki: status={response.status_code}, body={response.text}")
        
        try:
            loki_response = response.json()
        except json.JSONDecodeError as e:
            logger.error(f"failed to unmarshal response json: {e}")
            raise Exception("failed to unmarshal response json")
        
        labels = loki_response.get('data', [])
        
        return labels
        
    except requests.RequestException as e:
        logger.error(f"failed to get labels from loki: {e}")
        raise Exception(f"failed to get labels from loki: {str(e)}")
    except Exception as e:
        logger.error(f"unexpected error: {e}")
        raise Exception(f"internal server error: {str(e)}")

@mcp.tool()
def get_label_values(label: str) -> List[str]:
    """
    Get all possible values for a specific label from Loki.
    
    Args:
        label: Label name to get values for
    
    Returns:
        List of all possible values for the specified label
    """
    try:
        logger.info(f"Get Label Values Request: label={label}")

        full_url = f"{LOKI_ENDPOINT}/label/{label}/values"

        headers = {'X-Scope-OrgID': 'homelab'}

        response = requests.get(full_url, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"Loki label values query failed: status={response.status_code}, body={response.text}")
            raise Exception(f"failed to get label values from loki: {response.status_code}")
        
        # デバッグ用（生の応答をログ出力）
        logger.info(f"raw response from loki: status={response.status_code}, body={response.text}")
        
        try:
            loki_response = response.json()
        except json.JSONDecodeError as e:
            logger.error(f"failed to unmarshal response json: {e}")
            raise Exception("failed to unmarshal response json")
        
        values = loki_response.get('data', [])
        
        return values
        
    except requests.RequestException as e:
        logger.error(f"failed to get label values from loki: {e}")
        raise Exception(f"failed to get label values from loki: {str(e)}")
    except Exception as e:
        logger.error(f"unexpected error: {e}")
        raise Exception(f"internal server error: {str(e)}")

if __name__ == "__main__":
    mcp.run(transport="stdio")