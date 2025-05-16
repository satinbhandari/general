Here’s a minimal working example of using the Google ADK with MCP tools (adapters) in Python. This example demonstrates:

Creating an async MCP toolset connection

Creating an LlmAgent using a Gemini LLM

Running the ADK agent using run_async



---

1. agent.py — Define MCP tool agent

# agent.py
from contextlib import AsyncExitStack
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters, SseServerParameters

async def create_agent():
    """Creates an ADK agent with local + remote MCP toolsets."""
    common_exit_stack = AsyncExitStack()

    local_tools, _ = await MCPToolset.from_server(
        connection_params=StdioServerParameters(
            command="npx",
            args=["@modelcontextprotocol/server-filesystem"],
        )
    )
    remote_tools, _ = await MCPToolset.from_server(
        connection_params=SseServerParameters(
            url="http://your-mcp-server-url.com/sse"
        )
    )

    async_exit_stack = common_exit_stack

    agent = LlmAgent(
        model="gemini-2.0-flash",
        name="enterprise_assistant",
        instruction="Help user accessing their file systems",
        tools=[*local_tools, *remote_tools]
    )

    return agent, async_exit_stack


---

2. main.py — Run ADK with the agent

# main.py
import asyncio
from google.adk.cli.fast_api import run_async
from agent import create_agent

agent_task = asyncio.create_task(create_agent())

async def startup():
    agent, stack = await agent_task
    await run_async(agent=agent)

if __name__ == "__main__":
    asyncio.run(startup())


---

3. Key Notes

StdioServerParameters connects to a local MCP file system using Node.js (npx command).

SseServerParameters connects to a remote MCP server over HTTP.

Make sure your Node.js server is running with MCP support or stubbed locally.

Replace "gemini-2.0-flash" with your BaseLLM if you’ve wrapped Gemini manually.



---

4. Optional (Custom BaseLLM)

If you're using a custom Gemini model via BaseLLM:

from google.adk.llms.base_llm import BaseLLM

class GeminiLLM(BaseLLM):
    async def generate_text(self, prompt: str, **kwargs):
        # Implement your Gemini 2.0 Flash logic here (e.g., via Google SDK or API)
        return "response from Gemini"

# Then update agent creation:
agent = LlmAgent(
    model=GeminiLLM(),
    name="enterprise_assistant",
    instruction="Help user accessing their file systems",
    tools=[*local_tools, *remote_tools]
)


---

Let me know if:

You're using a custom LLM wrapper and want help structuring it.

You want to enable tracing, logging, or flow diagrams.

You're running into FastAPI or CLI usage issues.





You're absolutely right to question this — google.adk.cli.fast_api.run_async does not export a function called run_async in the current release of the Google Automated Decision Kit (ADK). That was part of an internal or older dev variant and not intended for public usage.

Here's how to correctly run your ADK agent with FastAPI:

You should manually start the FastAPI app and mount your agent using ADK's create_fastapi_app.


---

✅ Correct Way to Run ADK Agent in FastAPI

1. agent.py – Same as before (create the agent)

No changes needed here. Keep create_agent() as an async function returning the agent.

2. main.py – Start FastAPI app

# main.py
import asyncio
import uvicorn
from fastapi import FastAPI
from agent import create_agent
from google.adk.cli.fast_api import create_fastapi_app

app = FastAPI()

async def init():
    agent, exit_stack = await create_agent()
    adk_app = create_fastapi_app(agent)
    app.mount("/", adk_app)

@app.on_event("startup")
async def startup_event():
    await init()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


---

✅ Dependencies You Need

Make sure you install the correct packages:

pip install "git+https://github.com/google/automated-decision-kit.git"
pip install uvicorn fastapi


---

Bonus: Testing It

Once running, you can POST to:

POST http://localhost:8000/apps/agent/users/<user_id>/sessions/<session_id>

Or try visiting /docs to see the OpenAPI UI.


---

Let me know if you'd like:

A template for GeminiLLM if you're using Gemini.

Help mocking or connecting a local MCP tool.

CLI-only version with no FastAPI.


