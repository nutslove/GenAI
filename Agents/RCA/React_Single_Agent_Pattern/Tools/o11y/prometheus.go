package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	_ "os"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
)

var (
	// PrometheusEndpoint = os.Getenv("PROMETHEUS_ENDPOINT")
	PrometheusEndpoint = "http://prometheus:9090/api/v1"
)

type PrometheusQueryRangeRequest struct {
	Query string `form:"query" binding:"required"` // PromQL
	Start string `form:"start"`
	End   string `form:"end"`
	Step  string `form:"step"`
}

type PrometheusQueryRangeResponse struct {
	Status string           `json:"status"`
	Data   PrometheusData   `json:"data"`
}

type PrometheusData struct {
	ResultType string             `json:"resultType"`
	Result     []PrometheusResult `json:"result"`
}

type PrometheusResult struct {
	Metric map[string]string `json:"metric"` // Label
	Values [][]interface{}   `json:"values"`
}

type PrometheusLabelValuesRequest struct {
	Label string `form:"label" binding:"required"`
}

type PrometheusLabelsResponse struct {
	Status string   `json:"status"`
	Data   []string `json:"data"`
}

type PrometheusLabelsValuesRequest struct {
	Metric string `form:"metric" binding:"required"`
}

type PrometheusLabelsValuesResponse struct {
	Status string                   `json:"status"`
	Data   []map[string]interface{} `json:"data"`
}

func timestampIsValid(timetype string, timestampStr string) bool {
	// RFC3339形式かチェック
	if _, err := time.Parse(time.RFC3339, timestampStr); err == nil {
		slog.Info("Type of timestamp is RFC3339", "timetype", timetype)
		return true
	}

	// Unix timestampとして数値変換を試行（1回だけ）
	timestamp, err := strconv.ParseInt(timestampStr, 10, 64)
	if err != nil {
		return false
	}

	// Unix timestamp（秒）かチェック
	// 2025年1月1日 00:00:00 UTC ~ 2100年12月31日 23:59:59 UTC
	if timestamp >= 1735689600 && timestamp <= 4133980799 {
		slog.Info("Type of timestamp is Unix timestamp (seconds)", "timetype", timetype)
		return true
	}

	// Unix timestamp（ミリ秒）かチェック
	// 2025年1月1日 00:00:00 UTC ~ 2100年12月31日 23:59:59 UTC
	if timestamp >= 1735689600000 && timestamp <= 4133980799000 {
		slog.Info("Type of timestamp is Unix timestamp (milliseconds)", "timetype", timetype)
		return true
	}

	return false
}

func processTimestamp(paramTimestamp, paramName string, defaultTimestamp int64) string {
	if paramTimestamp == "" {
		slog.Info(fmt.Sprintf("%s is not set. Use default.", paramName))
		return strconv.FormatInt(defaultTimestamp, 10)
	}

	if timestampIsValid(paramName, paramTimestamp) {
		return paramTimestamp
	}

	slog.Warn(fmt.Sprintf("%s format (%s) is invalid. Use default.", paramName, paramTimestamp))
	return strconv.FormatInt(defaultTimestamp, 10)
}

func processStep(step string) string {
	default_step := "600" // 10 minutes
	if step == "" {
		slog.Info("step is not set. Use default.")
		return default_step
	}

	stepInt, err := strconv.Atoi(step)
	if err != nil || stepInt <= 0 {
		slog.Warn(fmt.Sprintf("step format (%s) is invalid. Use default.", step))
		return default_step
	}

	return step
}

func PrometheusQueryRange(c *gin.Context) {
	var request PrometheusQueryRangeRequest
	if err := c.ShouldBindQuery(&request); err != nil {
		slog.Error("failed to bind query parameters", "error", err)
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid query parameters"})
		return
	}

	// デフォルトタイムスタンプ(start, end)
	defaultStartTimestamp := time.Now().Add(-1 * time.Hour).Unix()
	defaultEndTimestamp := time.Now().Unix()

	queryParams := url.Values{}
	queryParams.Add("query", request.Query)
	queryParams.Add("start", processTimestamp(request.Start, "start", defaultStartTimestamp))
	queryParams.Add("end", processTimestamp(request.End, "end", defaultEndTimestamp))
	queryParams.Add("step", processStep(request.Step)) // DataPointの間隔(秒)

	slog.Info("PromQL Request:", "promql", request.Query)

	fullUrl := fmt.Sprintf("%s/query_range?%s", PrometheusEndpoint, queryParams.Encode())

	req, err := http.NewRequest("GET", fullUrl, nil)
	if err != nil {
		slog.Error("failed to create request", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create request"})
		return
	}

	client := &http.Client{
		Timeout: 10 * time.Second,
	}
	resp, err := client.Do(req)
	if err != nil {
		slog.Error("failed to get query range response from Prometheus", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get query range response from Prometheus"})
		return
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		slog.Error("failed to read response body", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to read response body"})
		return
	}

	// // debug用（生の応答をログ出力）
	// slog.Info("raw response from Prometheus", "status", resp.StatusCode, "body", string(body))

	var response PrometheusQueryRangeResponse
	if err := json.Unmarshal([]byte(body), &response); err != nil {
		slog.Error("failed to unmarshal resoponse json", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to unmarshal resoponse json"})
		return
	}

	// // debug用
	// slog.Info("Response", "response:", response)

	var result []map[string]interface{}
	if len(response.Data.Result) > 0 {
		result = append(result, map[string]interface{}{"data_type": "metric"})
		for _, r := range response.Data.Result {
			entries := []map[string]interface{}{}
			// fmt.Println("labels:", r.Metric) // debug
			for _, v := range r.Values {
				// fmt.Println("timestamp:", v[0]) // debug
				// fmt.Println("value:", v[1]) // debug
				entries = append(entries, map[string]interface{}{"timestamp": v[0], "value": v[1]})
			}
			item := map[string]interface{}{
				"labels":  r.Metric,
				"entries": entries,
			}
			result = append(result, item)
		}
	} else {
		result = append(result, map[string]interface{}{"data": "データが見つかりませんでした。検索条件を変更してお試しください。(存在しないlabelを指定している可能性があります。labelを確認してください。)"})
	}

	c.JSON(http.StatusOK, result)
}

func PrometheusGetAllLabels(c *gin.Context) {
	fullUrl := fmt.Sprintf("%s/labels", PrometheusEndpoint)

	req, err := http.NewRequest("GET", fullUrl, nil)
	if err != nil {
		slog.Error("failed to create request for getting labels", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create request for getting labels"})
		return
	}
	client := &http.Client{
		Timeout: 10 * time.Second,
	}
	resp, err := client.Do(req)
	if err != nil {
		slog.Error("failed to get labels from Prometheus", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get labels from Prometheus"})
		return
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		slog.Error("failed to read response body", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to read response body"})
		return
	}

	// debug用（生の応答をログ出力）
	slog.Info("raw response from Prometheus", "status", resp.StatusCode, "body", string(body))
	var response PrometheusLabelsResponse
	if err := json.Unmarshal([]byte(body), &response); err != nil {
		slog.Error("failed to unmarshal resoponse json", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to unmarshal resoponse json"})
		return
	}

	c.JSON(http.StatusOK, response.Data)
}

func PrometheusGetLabelValues(c *gin.Context) {
	var request PrometheusLabelValuesRequest
	if err := c.ShouldBindQuery(&request); err != nil {
		slog.Error("failed to bind query parameters", "error", err)
		c.JSON(http.StatusBadRequest, gin.H{"error": "failed to bind query parameters"})
		return
	}

	slog.Info("Get Label Values Request:", "label", request.Label)

	fullUrl := fmt.Sprintf("%s/label/%s/values", PrometheusEndpoint, request.Label)

	req, err := http.NewRequest("GET", fullUrl, nil)
	if err != nil {
		slog.Error("failed to create request for getting label values", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create request for getting label values"})
		return
	}

	client := &http.Client{
		Timeout: 10 * time.Second,
	}
	resp, err := client.Do(req)
	if err != nil {
		slog.Error("failed to get label values from Prometheus", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get label values from Prometheus"})
		return
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		slog.Error("failed to read response body", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to read response body"})
		return
	}

	// debug用（生の応答をログ出力）
	slog.Info("raw response from Prometheus", "status", resp.StatusCode, "body", string(body))

	var response PrometheusLabelsResponse
	if err := json.Unmarshal([]byte(body), &response); err != nil {
		slog.Error("failed to unmarshal resoponse json", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to unmarshal resoponse json"})
		return
	}
	if len(response.Data) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"result": "データが見つかりませんでした。検索条件を変更してお試しください。(存在しないlabelを指定している可能性があります。labelを確認してください。)"})
		return
	}

	c.JSON(http.StatusOK, response.Data)
}

func PrometheusGetAllMetrics(c *gin.Context) {
	fullUrl := fmt.Sprintf("%s/label/__name__/values", PrometheusEndpoint)

	req, err := http.NewRequest("GET", fullUrl, nil)
	if err != nil {
		slog.Error("failed to create request for getting all metrics", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create request for getting all metrics"})
		return
	}
	client := &http.Client{
		Timeout: 10 * time.Second,
	}
	resp, err := client.Do(req)
	if err != nil {
		slog.Error("failed to get all metrics from Prometheus", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get all metrics from Prometheus"})
		return
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		slog.Error("failed to read response body", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to read response body"})
		return
	}

	// debug用（生の応答をログ出力）
	slog.Info("raw response from Prometheus", "status", resp.StatusCode, "body", string(body))

	var response PrometheusLabelsResponse
	if err := json.Unmarshal([]byte(body), &response); err != nil {
		slog.Error("failed to unmarshal resoponse json", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to unmarshal resoponse json"})
		return
	}

	c.JSON(http.StatusOK, response.Data)
}

func PrometheusGetLabelsValuesMetricHas(c *gin.Context) {
	var request PrometheusLabelsValuesRequest
	if err := c.ShouldBindQuery(&request); err != nil {
		slog.Error("failed to bind query parameters", "error", err)
		c.JSON(http.StatusBadRequest, gin.H{"error": "failed to bind query parameters"})
		return
	}

	queryParams := url.Values{}
	queryParams.Add("match[]", request.Metric)

	slog.Info("Labels & Values Metric has", "metric", request.Metric)

	fullUrl := fmt.Sprintf("%s/series?%s", PrometheusEndpoint, queryParams.Encode())

	req, err := http.NewRequest("GET", fullUrl, nil)
	if err != nil {
		slog.Error("failed to create request", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create request"})
		return
	}

	client := &http.Client{
		Timeout: 10 * time.Second,
	}
	resp, err := client.Do(req)
	if err != nil {
		slog.Error("failed to get labels&values that a specific metric has response from Prometheus", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get labels&values that a specific metric has response from Prometheus"})
		return
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		slog.Error("failed to read response body", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to read response body"})
		return
	}

	// debug用（生の応答をログ出力）
	slog.Info("raw response from Prometheus", "status", resp.StatusCode, "body", string(body))

	var response PrometheusLabelsValuesResponse
	if err := json.Unmarshal([]byte(body), &response); err != nil {
		slog.Error("failed to unmarshal resoponse json", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to unmarshal resoponse json"})
		return
	}

	if len(response.Data) == 0 {
		response.Data = []map[string]interface{}{
			{"result": "データが見つかりませんでした。検索条件を変更してお試しください。(存在しないmetricを指定している可能性があります。metricを確認してください。)"},
		}
	}
	c.JSON(http.StatusOK, response.Data)
}