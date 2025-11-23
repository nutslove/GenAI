package main

import (
	// "context"
	// "log"

	"github.com/gin-gonic/gin"
)

func main() {
	r := gin.Default()
	o11y := r.Group("/o11y")
	loki := o11y.Group("/loki")
	// thanos := o11y.Group("/thanos")
	// tempo := o11y.Group("/tempo")
	{
		// LokiからLogを取得
		loki_v1 := loki.Group("/api/v1")
		{
			loki_v1.POST("/query_range", LokiQueryRange)
			loki_v1.POST("/labels", LokiGetAllLabels)
			loki_v1.POST("/label_values", LokiGetLabelValues)
			loki_v1.POST("/streams_selector_has", LokiGetStreamsSelectorHas)
		}
		// thanos_v1 := thanos.Group("/api/v1")
		// {
		// 	thanos_v1.POST("/query_range", ThanosQueryRange)
		// 	thanos_v1.POST("/labels", ThanosGetAllLabels)
		// 	thanos_v1.POST("/label_values", ThanosGetLabelValues)
		// 	thanos_v1.POST("/all_metrics", ThanosGetAllMetrics)
		// 	thanos_v1.POST("/labels_values_metric_has", ThanosGetLabelsValuesMetricHas)
		// }
		// tempo := tempo.Group("/api")
		// {
		// 	tempo.POST("/query_trace", TempoQueryTrace)
		// }
	}
	r.Run(":8070")
}