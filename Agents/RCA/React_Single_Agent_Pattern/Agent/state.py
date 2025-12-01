# from langgraph.graph import MessagesState

from langchain.agents import AgentState

# class RCAAgentState(MessagesState):
class RCAAgentState(AgentState):
  alert_message: str = ""
  alert_occurred_time: str = ""
  metric_list: list = []
  loki_labels_list: str = ""