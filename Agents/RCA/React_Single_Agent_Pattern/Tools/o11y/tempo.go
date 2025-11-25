package main

import (
	"io"
	_ "os"
	"time"

	"github.com/gin-gonic/gin"

	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
)

var (
	// TempoEndpoint = os.Getenv("TEMPO_ENDPOINT")
	TempoEndpoint = "http://tempo:3200/api/"
)

type TempoQueryTraceRequest struct {
	TraceID string `form:"trace_id" binding:"required"`
}

type TempoTraceResponse struct {
	Trace map[string]interface{} `json:"trace"`
}

func TempoQueryTrace(c *gin.Context) {
	var request TempoQueryTraceRequest
	if err := c.ShouldBindQuery(&request); err != nil {
		slog.Error("Failed to bind query parameters", "error", err)
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	slog.Info("Query trace Request:", "trace_id", request.TraceID)

	fullUrl := fmt.Sprintf("%s/v2/traces/%s", TempoEndpoint, request.TraceID)

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
		slog.Error("failed to get trace response from Tempo", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get trace response from Tempo"})
		return
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		slog.Error("failed to read response body", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to read response body"})
		return
	}

	var response TempoTraceResponse
	if err := json.Unmarshal([]byte(body), &response); err != nil {
		slog.Error("failed to unmarshal resoponse json", "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to unmarshal resoponse json"})
		return
	}

	if len(response.Trace) == 0 {
		response.Trace = map[string]interface{}{
			"result": "該当TraceIDのデータは存在しません。",
		}
	}
	c.JSON(http.StatusOK, response)
}