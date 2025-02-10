from langgraph.graph import MessagesState
from pydantic import Field, BaseModel
from typing_extensions import TypedDict

# class Response(TypedDict):
class Response(BaseModel): # Stateの中で使う場合はTypedDictではエラーが出るのでBaseModelに変更
    analysis_results: str = Field(..., description="The root cause analysis of the error message.")
    final_command: str = Field(..., description="The final command to execute to resolve the issue.")

class State(MessagesState):
    system_name: str = ""
    region: str = "ap-northeast-1"
    account_id: str = ""
    known_issue: bool = False
    predefined_command: str = ""
    final_response: Response