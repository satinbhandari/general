the implementation should use the create_react_agent and adhere to the A2A protocol with langgraph framework and also use the A2AStarletteApplication for request handler and start the application via uvicorn.server

Of course. Based on your specific requirements, here is a complete implementation of a LangGraph agent that uses `create_react_agent`, adheres to the A2A protocol, is served by `A2AStarletteApplication`, and includes a custom authentication layer. The application is started programmatically with `uvicorn`.

This approach correctly integrates the A2A protocol's authentication mechanism with a LangGraph agent.

### Core Concepts of this Implementation

1.  **A2A Protocol Authentication**: Unlike the `langgraph.json` method, authentication in a pure `A2AStarletteApplication` is handled differently. It's declared in the `AgentCard` and then implemented in a custom request handler.
2.  **`create_react_agent`**: We will use LangGraph's prebuilt function to quickly create a powerful ReAct agent.
3.  **A2A-LangGraph Bridge**: A custom `AgentExecutor` class is created to act as a bridge. It receives requests from the A2A handler and invokes the LangGraph agent.
4.  **Custom Request Handler**: We will subclass `DefaultRequestHandler` from the A2A SDK to insert our own logic for validating the API key sent by the client.
5.  **Programmatic Server Start**: The `uvicorn.Server` is used to run the application, providing more control than running it from the command line.

### Complete, Runnable Code

Create a single Python file named `a2a_agent_server.py` with the following content.

```python
# a2a_agent_server.py

import asyncio
import uvicorn
from typing import Dict, Any

# --- LangGraph and LangChain Imports ---
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

# --- A2A Protocol Imports ---
from a2a.server.app import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler, AuthenticatedRequest
from a2a.server.agent_executor import AgentExecutor
from a2a.server.task_store import InMemoryTaskStore
from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    Task,
    Response,
    Error,
    ErrorScope,
    SecurityScheme,
    SecuritySchemeType,
)

# --- Configuration & Secrets ---
# In a real app, load these from environment variables or a secure vault.
OPENAI_API_KEY = "your-openai-api-key-here"  # <-- IMPORTANT: Replace with your key
VALID_API_KEYS = {
    "secret-key-123": {"user": "Alice"},
    "secret-key-456": {"user": "Bob"},
}

# --- 1. Define the LangGraph ReAct Agent ---

@tool
def get_weather(city: str) -> str:
    """Gets the weather for a given city."""
    if "san francisco" in city.lower():
        return "It's foggy and 60 degrees in San Francisco."
    return f"It's sunny and 75 degrees in {city}."

# Initialize the LLM
# Make sure your OPENAI_API_KEY is set correctly above
llm = ChatOpenAI(model="gpt-4o", api_key=OPENAI_API_KEY, temperature=0)

# Create the ReAct agent using the prebuilt constructor
langgraph_agent = create_react_agent(
    model=llm,
    tools=[get_weather],
)

# --- 2. Create the A2A Protocol Components ---

class LangGraphAgentExecutor(AgentExecutor):
    """
    This class acts as a bridge between the A2A framework and the LangGraph agent.
    """
    async def execute_skill(
        self,
        task: Task,
        skill: AgentSkill,
        request: AuthenticatedRequest,
    ) -> Response | Error:
        """
        This method is called by the request handler to run the agent's logic.
        """
        try:
            print(f"Executing skill '{skill.id}' for user '{request.auth_info.get('user')}'")
            query = task.input.data

            # Prepare the input for the LangGraph agent
            langgraph_input = {"messages": [("user", query)]}

            # Invoke the LangGraph agent
            result = await langgraph_agent.ainvoke(langgraph_input)

            # Extract the final message from the agent's output
            final_response = result["messages"][-1].content

            return Response.from_text(final_response)

        except Exception as e:
            print(f"Error executing skill: {e}")
            return Error(
                scope=ErrorScope.TASK,
                message=f"An error occurred: {e}",
            )


class CustomAuthRequestHandler(DefaultRequestHandler):
    """
    A custom request handler that overrides the default authentication to
    check for a custom 'x-api-key' header.
    """
    async def _authenticate_request(self, headers: Dict[str, Any]) -> AuthenticatedRequest | Error:
        """
        This method is called on every incoming request to validate credentials.
        """
        api_key = headers.get("x-api-key")

        if not api_key:
            return Error(
                scope=ErrorScope.REQUEST,
                message="Missing required header: x-api-key",
                auth_error=True,
            )

        if api_key in VALID_API_KEYS:
            # Authentication successful.
            # The returned dictionary is passed to the AgentExecutor.
            return AuthenticatedRequest(auth_info=VALID_API_KEYS[api_key])
        else:
            # Authentication failed.
            return Error(
                scope=ErrorScope.REQUEST,
                message="Invalid API Key.",
                auth_error=True,
            )


# --- 3. Define the AgentCard ---

# This describes the agent's capabilities and how to authenticate with it.
agent_card = AgentCard(
    name="A2A ReAct Weather Agent",
    description="An agent that uses LangGraph's ReAct agent to answer questions about weather.",
    url="http://localhost:8000/",
    version="1.0.0",
    capabilities=AgentCapabilities(streaming=False),
    skills=[
        AgentSkill(
            id="get_weather_and_chat",
            name="Get Weather and Chat",
            description="Answers questions about weather.",
            examples=["what is the weather in san francisco?"],
        )
    ],
    # Define the security scheme. This tells clients they need to provide an API key.
    security_schemes={
        "api_key_auth": SecurityScheme(
            type=SecuritySchemeType.APIKEY,
            description="API Key in 'x-api-key' header.",
            name="x-api-key",
            in_location="header",
        )
    },
    # Specify which security schemes protect the agent.
    security=[{"api_key_auth": []}],
)


# --- 4. Assemble and Run the Application ---

async def main():
    """
    Main function to set up and run the Uvicorn server.
    """
    # 1. Instantiate our custom executor
    agent_executor = LangGraphAgentExecutor()

    # 2. Instantiate our custom request handler
    request_handler = CustomAuthRequestHandler(
        agent_executor=agent_executor,
        task_store=InMemoryTaskStore(),
    )

    # 3. Create the A2A Starlette Application
    a2a_app = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    # 4. Configure and run the Uvicorn server programmatically
    config = uvicorn.Config(
        app=a2a_app.build(),
        host="127.0.0.1",
        port=8000,
        log_level="info",
    )
    server = uvicorn.Server(config)

    print("Starting A2A LangGraph Agent on http://127.0.0.1:8000")
    await server.serve()


if __name__ == "__main__":
    # Ensure you have a running asyncio event loop
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stopped.")

```

### Setup and Execution

**1. Create `requirements.txt`**

Create a file named `requirements.txt` in the same directory with the following content:

```text
langgraph
langchain
langchain-openai
uvicorn
a2a-python-sdk
```

**2. Install Dependencies**

Open your terminal and install the required packages:

```bash
pip install -r requirements.txt
```

**3. Set Your API Key**

**Important**: Open `a2a_agent_server.py` and replace `"your-openai-api-key-here"` with your actual OpenAI API key.

**4. Run the Server**

Execute the Python script from your terminal:

```bash
python a2a_agent_server.py
```

You should see output indicating the server has started on `http://127.0.0.1:8000`.

### Testing the Agent

You can now interact with your secured A2A agent using `curl`.

**Test 1: Successful Request with a Valid API Key**

This request should succeed because it provides a valid key in the `x-api-key` header.

```bash
curl -X POST http://127.0.0.1:8000/v1/tasks \
-H "Content-Type: application/json" \
-H "x-api-key: secret-key-123" \
-d '{
  "skill": "get_weather_and_chat",
  "input": {
    "mime_type": "text/plain",
    "data": "what is the weather in san francisco?"
  }
}'
```

**Expected Successful Response:**

You will receive a JSON object representing the A2A task, and the final response will be in the `output` field.

```json
{
  "id": "...",
  "status": "COMPLETED",
  "input": { "...": "..." },
  "output": {
    "mime_type": "text/plain",
    "data": "It's foggy and 60 degrees in San Francisco."
  },
  "...": "..."
}
```

**Test 2: Failed Request with an Invalid API Key**

This request should be rejected by our custom authentication handler.

```bash
curl -X POST http://127.0.0.1:8000/v1/tasks \
-H "Content-Type: application/json" \
-H "x-api-key: invalid-key" \
-d '{
  "skill": "get_weather_and_chat",
  "input": {
    "mime_type": "text/plain",
    "data": "what is the weather in san francisco?"
  }
}'
```

**Expected Error Response (HTTP 401 Unauthorized):**

```json
{
  "error": {
    "scope": "REQUEST",
    "message": "Invalid API Key.",
    "auth_error": true
  }
}
```

Citations:
[1] selected_image_5844974845981638607.jpg https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/images/81513745/af421ce1-17bb-4c04-a8e3-da7ed79072f3/selected_image_5844974845981638607.jpg
[2] create_react_agent — LangChain documentation https://python.langchain.com/api_reference/langchain/agents/langchain.agents.react.agent.create_react_agent.html
[3] Start with a prebuilt agent - GitHub Pages https://langchain-ai.github.io/langgraph/agents/agents/
[4] ReAct agent from scratch with Gemini 2.5 and LangGraph https://ai.google.dev/gemini-api/docs/langgraph-example
[5] How to create a ReAct agent from scratch - GitHub Pages https://langchain-ai.github.io/langgraph/how-tos/react-agent-from-scratch/
[6] langchain-ai/react-agent: LangGraph template for a simple ... - GitHub https://github.com/langchain-ai/react-agent
[7] How to add custom lifespan events https://docs.langchain.com/langgraph-platform/custom-lifespan
[8] enso-labs/a2a-langgraph: Agent-to-Agent (A2A Protocol ... - GitHub https://github.com/enso-labs/a2a-langgraph
[9] Build an Agent - LangChain https://python.langchain.com/docs/tutorials/agents/
[10] How to add custom middleware https://langchain-ai.github.io/langgraph/how-tos/http/custom_middleware/
[11] How the Agent2Agent (A2A) protocol enables seamless AI agent ... https://wandb.ai/byyoung3/Generative-AI/reports/How-the-Agent2Agent-A2A-protocol-enables-seamless-AI-agent-collaboration--VmlldzoxMjQwMjkwNg
[12] langchain-ai/langgraph: Build resilient language agents as graphs. https://github.com/langchain-ai/langgraph
[13] Multi-Agent Communication with the A2A Python SDK https://towardsdatascience.com/multi-agent-communication-with-the-a2a-python-sdk/
[14] Building an A2A Currency Agent with LangGraph https://a2aprotocol.ai/blog/a2a-langraph-tutorial-20250513
[15] How to migrate from legacy LangChain agents to LangGraph https://python.langchain.com/docs/how_to/migrate_agent/
[16] Build a Full Stack Python Chatbot with LangGraph Platform https://www.youtube.com/watch?v=GTXx7CBxuz8
[17] Secure A2A Authentication with Auth0 and Google Cloud https://auth0.com/blog/auth0-google-a2a/
[18] ReAct agent from scratch with Gemini 2.5 and LangGraph - Philschmid https://www.philschmid.de/langgraph-gemini-2-5-react-agent
[19] Getting Started with Agent-to-Agent (A2A) Protocol https://codelabs.developers.google.com/intro-a2a-purchasing-concierge
[20] A2A/samples/python/agents/langgraph/README.md at main - GitHub https://github.com/google/A2A/blob/main/samples/python/agents/langgraph/README.md
[21] langgraph/tutorials/langgraph-platform/local-server/ #2527 https://github.com/langchain-ai/langgraph/discussions/2527
