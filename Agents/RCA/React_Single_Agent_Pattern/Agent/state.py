from langgraph.graph import MessagesState

class RCAAgentState(MessagesState):
  alert_message: str = ""
  alert_occurred_time: str = ""
  metric_list: list = []
  loki_labels_list: str = ""