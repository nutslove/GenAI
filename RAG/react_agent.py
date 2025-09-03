from langgraph.prebuilt import create_react_agent
from mcp.server.fastmcp import FastMCP
from langchain_mcp_adapters.client import MultiServerMCPClient
import os
import asyncio
import uuid
from langfuse.langchain import CallbackHandler # sdk v3で「from langfuse.callback import CallbackHandler」から変更された

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/nutslove/GCP_VertexAI/service-account-key.json"

langfuse_handler = CallbackHandler()


client = MultiServerMCPClient(
    {
        "math": {
            "command": "python",
            "args": ["./math_server.py"],
            "transport": "stdio",
        },
        "weather": {
            "command": "python",
            "args": ["./weather_server.py"],
            "transport": "stdio",
            # "url": "http://localhost:8000/mcp/",
            # "transport": "streamable_http",
        }
    }
)

async def main():
    tools = await client.get_tools()
    agent = create_react_agent("gemini-2.0-flash-lite", tools)

    predefined_run_id = str(uuid.uuid4())  # LangFuseのRunID(traceID)を生成

    math_response = await agent.ainvoke({"messages": "what's (3 + 5) x 12?"},config={"recursion_limit": 60, "callbacks": [langfuse_handler], "run_id": predefined_run_id})
    weather_response = await agent.ainvoke({"messages": "what is the weather in nyc?"},config={"recursion_limit": 60, "callbacks": [langfuse_handler], "run_id": predefined_run_id})

    print("Math Response:", math_response)
    print("Weather Response:", weather_response)

if __name__ == "__main__":
    asyncio.run(main())