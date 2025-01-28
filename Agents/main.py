from langchain_community.agent_toolkits.load_tools import load_tools
from langchain.agents import initialize_agent, AgentType
from langchain_aws import ChatBedrock, ChatBedrockConverse
import langchain
from typing import Optional
from pydantic import BaseModel, Field

def main():
    langchain.verbose = True # Trueに設定するとデバックログが表示される
    chat = ChatBedrock(
        model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
        model_kwargs={
            "temperature": 0.1,
            # "max_tokens": 8000,
        }
    )
    tools = load_tools(["terminal"], llm=chat,allow_dangerous_tools=True)
    agent_chain = initialize_agent(tools, chat, agent="zero-shot-react-description")
    result = agent_chain.invoke("What is your currrent directory?")
    print(result)

if __name__ == '__main__':
    main()