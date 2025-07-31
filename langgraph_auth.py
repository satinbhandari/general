Perfect. Since you're using A2A with Starlette, here's a clean and A2A SDK-compatible way to integrate LangGraph's @auth.authenticate and @auth.on handlers into your Starlette-based LangGraph agent.


---

✅ Goal

Integrate LangGraph auth decorators:

✅ @auth.authenticate: Validate incoming A2A requests (e.g., via Bearer token).

✅ @auth.on("unauthorized"): Define custom response when authentication fails.

✅ Pass identity (e.g., user_id, entitlements) into the LangGraph graph via configurable.



---

🧩 Working Example

1. Set up LangGraph Auth Handlers

from langgraph.auth import auth

# Authentication decorator: checks the token and attaches user info
@auth.authenticate
async def authenticate(headers: dict):
    token = headers.get("authorization", "").replace("Bearer ", "")
    if token != "my-secret-token":
        raise Exception("Unauthorized")
    return {"user_id": "demo_user", "entitlements": ["read_data", "use_tool_1"]}

# Custom response on authentication failure
@auth.on("unauthorized")
async def on_unauthorized():
    return {"error": "Unauthorized"}, 401


---

2. Create LangGraph Agent (A2A-Compatible)

from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph
from langgraph.checkpoint import MemorySaver

from my_tools import tools  # Define your tools

# Your LLM model client (e.g., from OpenAI, Anthropic, etc.)
agent = create_react_agent(
    tools=tools,
    model=your_model,
)

# Compile the graph
graph = StateGraph(agent).compile()
runner = graph.runner(saver=MemorySaver())


---

3. Define A2A-Compatible Starlette Server

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from langgraph.a2a.protocol import Message  # optional, for validation

@auth.authenticate
async def a2a_entrypoint(request: Request):
    body = await request.json()
    
    # Optional: Validate A2A message format (e.g., schema of `messages`)
    # Message.validate(body)

    identity = request.state.identity  # Populated by @auth.authenticate

    # Run the LangGraph agent with context
    result = await runner.invoke(
        input=body,
        config={
            "configurable": identity  # You can pass user_id, entitlements, etc.
        }
    )
    return JSONResponse(result)

routes = [
    Route("/a2a", endpoint=a2a_entrypoint, methods=["POST"]),
]

app = Starlette(routes=routes)


---

🔄 Example of Passing Identity into Tools

In your tool function:

from langgraph.prebuilt import tool

@tool
def get_secret_info(configurable):
    if "use_tool_1" not in configurable.get("entitlements", []):
        raise Exception("Access Denied")
    return "Here's your sensitive data."


---

✅ Summary

Integration Point	Implementation

Auth validation	@auth.authenticate on Starlette route
Custom error handler	@auth.on("unauthorized")
Identity injection	request.state.identity → configurable
A2A message handler	POST /a2a Starlette route



---

🛠️ Bonus Tips

Want to use JWTs or Ping auth instead of static token? Use a library like pyjwt in @auth.authenticate.

To inject identity deeper into the agent state, transform identity into input["state"] or embed into graph_state.



---

If you'd like, I can give you a complete boilerplate file (main.py) with your model/tool placeholders and auth already wired in. Let me know!

