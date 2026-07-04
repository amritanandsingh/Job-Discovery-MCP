from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq

from dotenv import load_dotenv
load_dotenv()

import asyncio
import os
import sys

# Fail fast with a clear message if the Groq key is missing or wrong.
# Groq API keys start with "gsk_" — an "org_..." value is an organization ID, not a key.
if not os.getenv("GROQ_API_KEY", "").startswith("gsk_"):
    raise SystemExit(
        "GROQ_API_KEY in .env is missing or not a valid Groq API key "
        "(must start with 'gsk_'). Create one at https://console.groq.com/keys"
    )

async def main():
    client = MultiServerMCPClient(
        {
            "math":{
                "command": sys.executable,  # same python as the client ("python" may not be on PATH)
                "args": ["mathServer.py"],  # was math.py (file doesn't exist)
                "transport": "stdio"
            }
            ,
            "weather":{
                "url": "http://127.0.0.1:8000/mcp",  # FastMCP serves streamable-http at /mcp, not the root
                "transport": "streamable_http"
            }
        }
    )

    tools = await client.get_tools()

    model = ChatGroq(model="llama-3.3-70b-versatile")  # qwen-qwq-32b was decommissioned by Groq
    agent = create_react_agent(model, tools)
    math_result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "what is 5 and 6 of amritX ? and what is weather in New York City?"}]}
    )

    print(math_result["messages"][-1].content)

asyncio.run(main())
