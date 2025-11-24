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
	// LokiEndpoint = os.Getenv("LOKI_ENDPOINT")
	LokiEndpoint = "http://loki:3100/loki/api/v1"
)

// GETパラメータ用にformタグを使用
type LokiQueryRangeRequest struct {
	Query     string `form:"query" binding:"required"` // LogQL
	Start     string `form:"start"`                    // default 1h. nanosecond Unix epoch または RFC3339 フォーマット
	End       string `form:"end"`                      // default now. nanosecond Unix epoch または RFC3339 フォーマット
	Limit     int    `form:"limit"`                    // default 100
	Step      string `form:"step"`                     // default a dynamic value based on `start` and `end`. Only applies to query types which produce a matrix response.
	Direction string `form:"direction"`                // default backward, can be `forward`(昇順, 古いログが先頭) or `backward`(降順, 新しいログが先頭)
}

type LokiQueryRangeResponse struct {
	Status string   `json:"status"`
	Data   LokiData `json:"data"`
}

type LokiData struct {
	ResultType string          `json:"resultType"` // 普通のログ検索の場合は`streams`、Metric queryの場合は`matrix`になる
	Result     json.RawMessage `json:"result"`     // query種類(log query、metric query)によってJSON のフィールドが違い、一旦Rawで受け取る
}

type LokiLogResult struct {
	Stream map[string]string `json:"stream"`
	Values [][]interface{}   `json:"values"`
}

type LokiMetricResult struct {
	Metric map[string]string `json:"metric"`
	Values [][]interface{}   `json:"values"`
}

type LokiLabelValuesRequest struct {
	Label string `form:"label" binding:"required"`
}

type LokiLabelsResponse struct {
	Status string   `json:"status"`
	Data   []string `json:"data"`
}

type LokiSelectorStreamsRequest struct {
	Selector string `form:"selector" binding:"required"`
}

type LokiSelectorStreamsResponse struct {
	Status string                   `json:"status"`
	Data   []map[string]interface{} `json:"data"`
}

func LokiQueryRange(c *gin.Context) {
	var request LokiQueryRangeRequest
	if err := c.ShouldBindQuery(&request); err != nil {
		slog.Error("failed to bind query parameters", "error", err)
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid query parameters"})
		return
	}

	queryParams := url.Values{}
	queryParams.Add("query", request.Query)
	if request.Start != "" {
		queryParams.Add("start", request.Start)
	}
	if request.End != "" {
		queryParams.Add("end", request.End)
	}
	if request.Limit != 0 {
		queryParams.Add("limit", strconv.Itoa(request.Limit))
	}
	if request.Step != "" {
		queryParams.Add("step", request.Step)
	}
	if request.Direction != "" {
		queryParams.Add("direction", request.Direction)
	}

	fullUrl := fmt.Sprintf("%s/query_range?%s", LokiEndpoint, queryParams.Encode())

	req, err := http.NewRequest("GET", fullUrl, nil)
	if err != nil {
		slog.Error("failed to create request", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create request"})
		return
	}

	// req.Header.Set("X-Scope-OrgID", request.TenantID) // Lokiをマルチテナント構成で使用している場合は必要
	client := &http.Client{
		Timeout: 10 * time.Second,
	}
	resp, err := client.Do(req)
	if err != nil {
		slog.Error("failed to get query range response from loki", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get query range response from loki"})
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
	// slog.Info("raw response from loki", "status", resp.StatusCode, "body", string(body))

	var response LokiQueryRangeResponse
	if err := json.Unmarshal([]byte(body), &response); err != nil {
		slog.Error("failed to unmarshal resoponse json", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to unmarshal resoponse json"})
		return
	}

	// // debug用
	// slog.Info("response", "■ status", response.Status, "■ data", response.Data, "■ result", response.Data.Result, "■ values", response.Data.Result[0].Values)

	var result []map[string]interface{}

	if response.Data.ResultType == "streams" {
		var logResults []LokiLogResult
		if err := json.Unmarshal(response.Data.Result, &logResults); err != nil {
			slog.Error("failed to unmarshal log result", "error", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to unmarshal log resoponse json"})
			return
		}

		if len(logResults) > 0 {
			result = append(result, map[string]interface{}{"data_type": "log"})
			for _, r := range logResults {
				entries := []map[string]interface{}{}
				// fmt.Println("labels:", r.Stream) // debug
				for _, v := range r.Values {
					// fmt.Println("timestamp:", v[0]) // debug
					// fmt.Println("log:", v[1]) // debug
					entries = append(entries, map[string]interface{}{"timestamp": v[0], "value": v[1]})
				}
				item := map[string]interface{}{
					"labels":  r.Stream,
					"entries": entries,
				}
				result = append(result, item)
			}
		} else {
			result = append(result, map[string]interface{}{"data": "データが見つかりませんでした。検索条件を変更してお試しください。(存在しないlabelを指定している可能性があります。labelを確認してください。)"})
		}
	} else if response.Data.ResultType == "matrix" {
		var metricResults []LokiMetricResult
		if err := json.Unmarshal(response.Data.Result, &metricResults); err != nil {
			slog.Error("failed to unmarshal metric result", "error", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to unmarshal metric resoponse json"})
			return
		}

		if len(metricResults) > 0 {
			result = append(result, map[string]interface{}{"data_type": "metric"})
			for _, r := range metricResults {
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
	}

	// fmt.Println("■■■ result:", result) // debug

	c.JSON(http.StatusOK, result)
}

func LokiGetAllLabels(c *gin.Context) {
	fullUrl := fmt.Sprintf("%s/labels", LokiEndpoint)

	req, err := http.NewRequest("GET", fullUrl, nil)
	if err != nil {
		slog.Error("failed to create request for getting labels", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create request for getting labels"})
		return
	}
	// req.Header.Set("X-Scope-OrgID", request.TenantID) # Lokiをマルチテナント構成で使用している場合は必要
	client := &http.Client{
		Timeout: 10 * time.Second,
	}
	resp, err := client.Do(req)
	if err != nil {
		slog.Error("failed to get labels from loki", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get labels from loki"})
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
	slog.Info("raw response from loki", "status", resp.StatusCode, "body", string(body))

	var response LokiLabelsResponse
	if err := json.Unmarshal([]byte(body), &response); err != nil {
		slog.Error("failed to unmarshal resoponse json", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to unmarshal resoponse json"})
		return
	}

	c.JSON(http.StatusOK, response.Data)
}

func LokiGetLabelValues(c *gin.Context) {
	var request LokiLabelValuesRequest
	if err := c.ShouldBindQuery(&request); err != nil {
		slog.Error("failed to bind query parameters", "error", err)
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid query parameters"})
		return
	}

	fullUrl := fmt.Sprintf("%s/label/%s/values", LokiEndpoint, request.Label)

	req, err := http.NewRequest("GET", fullUrl, nil)
	if err != nil {
		slog.Error("failed to create request for getting label values", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create request for getting label values"})
		return
	}
	// req.Header.Set("X-Scope-OrgID", request.TenantID) # Lokiをマルチテナント構成で使用している場合は必要
	client := &http.Client{
		Timeout: 10 * time.Second,
	}
	resp, err := client.Do(req)
	if err != nil {
		slog.Error("failed to get label values from loki", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get label values from loki"})
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
	slog.Info("raw response from loki", "status", resp.StatusCode, "body", string(body))

	var response LokiLabelsResponse
	if err := json.Unmarshal([]byte(body), &response); err != nil {
		slog.Error("failed to unmarshal resoponse json", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to unmarshal resoponse json"})
		return
	}

	c.JSON(http.StatusOK, response.Data)
}

func LokiGetStreamsSelectorHas(c *gin.Context) {
	var request LokiSelectorStreamsRequest
	if err := c.ShouldBindQuery(&request); err != nil {
		slog.Error("failed to bind query parameters", "error", err)
		c.JSON(http.StatusBadRequest, gin.H{"error": "failed to bind query parameters"})
		return
	}

	queryParams := url.Values{}
	queryParams.Add("match[]", request.Selector)

	slog.Info("Labels & Values Selector has", "selector", request.Selector)

	fullUrl := fmt.Sprintf("%s/series?%s", LokiEndpoint, queryParams.Encode())

	req, err := http.NewRequest("GET", fullUrl, nil)
	if err != nil {
		slog.Error("failed to create request", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create request"})
		return
	}

	// req.Header.Set("X-Scope-OrgID", request.TenantID) # Lokiをマルチテナント構成で使用している場合は必要
	client := &http.Client{
		Timeout: 10 * time.Second,
	}
	resp, err := client.Do(req)
	if err != nil {
		slog.Error("failed to get streams that a specific label selector has response from loki", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get streams that a specific label selector has response from loki"})
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
	slog.Info("raw response from loki", "status", resp.StatusCode, "body", string(body))

	var response LokiSelectorStreamsResponse
	if err := json.Unmarshal([]byte(body), &response); err != nil {
		slog.Error("failed to unmarshal resoponse json", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to unmarshal resoponse json"})
		return
	}

	c.JSON(http.StatusOK, response.Data)
}