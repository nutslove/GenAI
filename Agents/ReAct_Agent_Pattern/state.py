from langgraph.graph import MessagesState

class State(MessagesState):
    system_name: str = ""
    region: str = "ap-northeast-1"
    account_id: str = ""
    known_issue: bool = False
    analysis_results: str = ""
    predefined_command: str = ""
    final_command: str = ""