from langgraph.prebuilt import create_react_agent
from mcp.server.fastmcp import FastMCP
from langchain_mcp_adapters.client import MultiServerMCPClient
import os
import asyncio
import uuid
import textwrap
from langfuse.langchain import CallbackHandler # sdk v3で「from langfuse.callback import CallbackHandler」から変更された

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "C:\\Users\\nuts_\\service-account-key.json"

langfuse_handler = CallbackHandler()


mcp_client = MultiServerMCPClient(
    {
        "loki": {
            "command": "python",
            "args": ["./loki_server.py"],
            "transport": "stdio",
        },
        # "weather": {
        #     "command": "python",
        #     "args": ["./weather_server.py"],
        #     "transport": "stdio",
        #     # "url": "http://localhost:8000/mcp/",
        #     # "transport": "streamable_http",
        # }
    }
)

async def main(error_message: str):
    system_prompt = textwrap.dedent(f"""\
        ## Role
        You are a helpful assistant that performs root cause analysis for system issues and alerts. You are an expert in troubleshooting infrastructure, application, and service-related problems with deep knowledge of system dependencies and common failure patterns.

        ## Task
        Given the following error message and available information, perform a comprehensive root cause analysis and propose solutions to resolve the issue.

        ## Analysis Steps
        Let's think step by step:
        1. Identify the issue: Analyze the error message and determine the most relevant resources.
        2. Investigate: Use the provided available information to investigate the issue.
        3. Verify the status and configuration of resources: check the status and configuration of resources. Please investigate not only the resource where the alert occurred, but also any potentially related resources to identify the true root cause.
        4. Propose a solution: Based on the analysis, propose a solution to resolve the issue.

        ## Available Information
        1. Error(Alert) Message:
        {error_message}

        ## Rules & Constraints
        - Please investigate not only the resource where the alert occurred, but also any potentially related resources to identify the true root cause.
        - root cause analysis results should be in Japanese.
    """).strip()

    tools = await mcp_client.get_tools()
    agent = create_react_agent(
        model="gemini-2.0-flash-lite",
        tools=tools,
        prompt=system_prompt,
    )

    predefined_run_id = str(uuid.uuid4())  # LangFuseのRunID(traceID)を生成

    response = await agent.ainvoke({"messages": error_message},config={"recursion_limit": 60, "callbacks": [langfuse_handler], "run_id": predefined_run_id})
    # weather_response = await agent.ainvoke({"messages": "what is the weather in nyc?"},config={"recursion_limit": 60, "callbacks": [langfuse_handler], "run_id": predefined_run_id})

    print("RCA Response:", response)
    # print("Math Response:", math_response)
    # print("Weather Response:", weather_response)

if __name__ == "__main__":
    asyncio.run(main(input("Input error message: ")))