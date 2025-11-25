package main

import (
	"github.com/gin-gonic/gin"
)

func main() {
	r := gin.Default()
	o11y := r.Group("/o11y")
	loki := o11y.Group("/loki")
	prometheus := o11y.Group("/prometheus")
	tempo := o11y.Group("/tempo")
	{
		loki_v1 := loki.Group("/api/v1")
		{
			loki_v1.POST("/query_range", LokiQueryRange)
			loki_v1.POST("/labels", LokiGetAllLabels)
			loki_v1.POST("/label_values", LokiGetLabelValues)
			loki_v1.POST("/streams_selector_has", LokiGetStreamsSelectorHas)
		}

		prometheus_v1 := prometheus.Group("/api/v1")
		{
			prometheus_v1.POST("/query_range", PrometheusQueryRange)
			prometheus_v1.POST("/labels", PrometheusGetAllLabels)
			prometheus_v1.POST("/label_values", PrometheusGetLabelValues)
			prometheus_v1.POST("/all_metrics", PrometheusGetAllMetrics)
			prometheus_v1.POST("/labels_values_metric_has", PrometheusGetLabelsValuesMetricHas)
		}

		tempo := tempo.Group("/api")
		{
			tempo.POST("/query_trace", TempoQueryTrace)
		}
	}
	r.Run(":8070")
}