For your Tachyon Routing Agent, I would implement the Decisions API middleware as a decision-first router that chooses between the Text-to-SQL Agent and RAG Agent using the complete available conversation history.

There is one important change from our earlier implementation: instead of returning a final natural-language answer, the Decisions API should return a structured routing choice, such as text_to_sql, rag, or fallback.

The routing middleware can then produce a tool call for the selected agent, allowing LangChain’s existing wrap_tool_call middleware to handle authorization, execution, and observability.

1. Target architecture

User Query

Current message + previous conversation

Tachyon Decision Middleware

awrap_model_call · OpenAI Decisions API

Text-to-SQL

Structured data queries

RAG

Document retrieval

Fallback

Existing ChatOpenAI routing agent

For example:

Latest query	Relevant history	Decision
“Show my last 10 transactions”	None required	Text-to-SQL
“Summarize the loan policy”	None required	RAG
“What about the previous month?”	Earlier transaction query	Text-to-SQL
“What does the policy say about that?”	Earlier policy discussion	RAG
Ambiguous or unsupported query	Insufficient context	Fallback

The crucial requirement is that the middleware should not classify only the latest user message. It should classify the latest request in the context of the full conversation.

2. Reference implementation

The code below uses three components:

* A history converter that prepares the full retained conversation.
* A Decisions API client that chooses the agent.
* A wrap_model_call middleware that emits a LangChain tool call or falls back to your existing model middleware.

The OpenAI Decisions SDK response fields can vary by SDK release, so I have isolated the endpoint-specific parsing in one adapter. The example assumes the client.decisions.create() interface discussed earlier; verify its request and response schema against your installed SDK before deploying.

Step A — Convert the conversation history

import json
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
)
def as_text(content):
    if isinstance(content, str):
        return content
    # Avoid silently losing images or attachments.
    if not isinstance(content, (str, list, dict)):
        raise ValueError("Unsupported message content")
    return json.dumps(content, ensure_ascii=False)
def prepare_decision_history(messages):
    history = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            history.append({
                "role": "developer",
                "content": as_text(msg.content),
            })
        elif isinstance(msg, HumanMessage):
            history.append({
                "role": "user",
                "content": as_text(msg.content),
            })
        elif isinstance(msg, AIMessage):
            if msg.content:
                history.append({
                    "role": "assistant",
                    "content": as_text(msg.content),
                })
            for call in msg.tool_calls:
                if not call.get("id"):
                    raise ValueError("Missing tool call ID")
                history.append({
                    "type": "function_call",
                    "call_id": call["id"],
                    "name": call["name"],
                    "arguments": json.dumps(call["args"]),
                })
        elif isinstance(msg, ToolMessage):
            history.append({
                "type": "function_call_output",
                "call_id": msg.tool_call_id,
                "output": as_text(msg.content),
            })
        else:
            raise ValueError(
                f"Unsupported message: {type(msg).__name__}"
            )
    return history

This converts the complete history available in request.state["messages"]. The text-message shape shown is a reference representation; adapt it to the exact native input schema accepted by your Decisions SDK.

Step B — Create the routing decision client

from dataclasses import dataclass
from openai import AsyncOpenAI
@dataclass
class RouteDecision:
    route: str
    confidence: float
class TachyonRoutingDecisionClient:
    def __init__(self, model="gpt-6-luna"):
        self.client = AsyncOpenAI()
        self.model = model
    async def decide(self, messages):
        response = await self.client.decisions.create(
            model=self.model,
            input=messages,
            questions=[{
                "type": "choice",
                "name": "agent_route",
                "instructions": (
                    "You are a routing decision engine. "
                    "Evaluate the latest user request using "
                    "the entire conversation history. "
                    "Choose text_to_sql for database records, "
                    "balances, transactions, numeric reports, "
                    "and structured queries. "
                    "Choose rag for policies, documents, "
                    "knowledge articles, explanations, "
                    "and document-based questions. "
                    "Resolve references such as 'that', "
                    "'previous month', and 'same policy' "
                    "using earlier conversation turns. "
                    "If the request is ambiguous, requires "
                    "both agents, or cannot be confidently "
                    "routed, choose fallback."
                ),
                "choices": [
                    {
                        "value": "text_to_sql",
                        "description": (
                            "Questions requiring structured "
                            "database queries."
                        ),
                    },
                    {
                        "value": "rag",
                        "description": (
                            "Questions requiring document "
                            "retrieval or knowledge search."
                        ),
                    },
                    {
                        "value": "fallback",
                        "description": (
                            "Ambiguous, mixed, or unsupported "
                            "requests."
                        ),
                    },
                ],
            }],
        )
        # Isolate SDK-specific parsing here.
        answer = response.answers[0]
        return RouteDecision(
            route=answer.choice,
            confidence=answer.confidence,
        )

The decision instructions explicitly describe what each agent is responsible for. For production, make these descriptions configurable and include the actual data sources available to each agent. For example, if Text-to-SQL can access only a transaction database, do not describe it as capable of querying all structured enterprise data.

Step C — Implement the middleware

The key design choice is to return an AIMessage containing a tool call, rather than executing the SQL or RAG agent inside the middleware.

This lets LangChain continue into its standard tool execution node, where your existing wrap_tool_call hooks still apply.

import json
import uuid
import logging
from langchain.agents.middleware import AgentMiddleware, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage
logger = logging.getLogger(__name__)
class TachyonRoutingMiddleware(AgentMiddleware):
    def __init__(
        self,
        decision_client,
        confidence_threshold=0.85,
    ):
        self.decision_client = decision_client
        self.confidence_threshold = confidence_threshold
    async def awrap_model_call(self, request, handler):
        messages = request.state["messages"]
        # Route only when the latest message is from user.
        # After tool execution, use the normal model chain.
        if (
            not messages
            or not isinstance(messages[-1], HumanMessage)
        ):
            return await handler(request)
        try:
            history = prepare_decision_history(messages)
            decision = await self.decision_client.decide(
                history
            )
            if (
                decision.confidence
                < self.confidence_threshold
            ):
                return await handler(request)
            tool_names = {
                "text_to_sql": "text_to_sql_agent",
                "rag": "rag_agent",
            }
            tool_name = tool_names.get(decision.route)
            if not tool_name:
                return await handler(request)
            # Only use tools available to this model call.
            available_tools = {
                getattr(tool, "name", None)
                if not isinstance(tool, dict)
                else tool.get("function", {}).get("name")
                     or tool.get("name")
                for tool in request.tools
            }
            if tool_name not in available_tools:
                return await handler(request)
            # Pass the original question to the selected agent.
            # The subagent can receive additional history
            # through a trusted context mechanism if needed.
            latest_query = as_text(messages[-1].content)
            return ModelResponse(
                result=[
                    AIMessage(
                        content="",
                        tool_calls=[{
                            "name": tool_name,
                            "args": {
                                "query": latest_query
                            },
                            "id": f"call_{uuid.uuid4().hex}",
                            "type": "tool_call",
                        }],
                        response_metadata={
                            "tachyon_route": decision.route,
                            "decision_confidence":
                                decision.confidence,
                        },
                    )
                ]
            )
        except Exception:
            logger.exception(
                "Decision routing failed; "
                "falling back to primary model"
            )
        return await handler(request)

Important: The above middleware is a reference implementation, not a concurrency-complete production implementation. The HumanMessage check avoids most tool-loop reevaluations, but a once-per-turn marker or deduplication mechanism is still needed for retries and repeated model calls.

Also, the middleware passes the original latest query to the selected tool. This preserves the user’s wording but may not be sufficient for follow-up questions. For example, “What about the previous month?” needs the SQL agent to receive relevant history or a resolved query. Do not expect the route choice alone to rewrite the user’s request.

3. Define the SQL and RAG agents as tools

from langchain_core.tools import tool
@tool
async def text_to_sql_agent(query: str) -> str:
    """Answer structured database questions."""
    result = await sql_agent.ainvoke({
        "messages": [
            {"role": "user", "content": query}
        ]
    })
    return result["messages"][-1].content
@tool
async def rag_agent(query: str) -> str:
    """Answer questions using enterprise documents."""
    result = await rag_agent_executor.ainvoke({
        "messages": [
            {"role": "user", "content": query}
        ]
    })
    return result["messages"][-1].content

These wrappers demonstrate the execution pattern. If the subagents need previous turns, pass a sanitized conversation history through your existing Tachyon request context or explicitly define a history-aware tool interface.

For your security model, the tool wrapper must also propagate the authenticated principal, tenant, entitlement context, and trace context to the selected subagent.

4. Register with your existing middleware

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
routing_middleware = TachyonRoutingMiddleware(
    decision_client=TachyonRoutingDecisionClient(),
    confidence_threshold=0.85,
)
router = create_agent(
    model=ChatOpenAI(model="gpt-5.4"),
    tools=[
        text_to_sql_agent,
        rag_agent,
    ],
    middleware=[
        routing_middleware,
        ExistingModelMiddleware(),
        ExistingToolMiddleware(),
    ],
    checkpointer=redis_checkpointer,
    system_prompt=(
        "You are a routing agent. "
        "Route database queries to text_to_sql_agent "
        "and document questions to rag_agent."
    ),
)

The routing middleware is first among the awrap_model_call hooks. If it returns a tool call, the existing model middleware and primary model are skipped for that model invocation. The tool then executes through the normal LangChain tool pipeline.

After the tool returns, create_agent normally invokes the model again to process the tool result. Because the latest message is now a ToolMessage, the decision middleware delegates to your existing model chain.

This means the implementation avoids the initial routing LLM call, but it does not guarantee zero primary-model calls for the whole request.

5. Optimization: Avoid the post-tool LLM call

If your SQL and RAG agents already return complete, user-facing answers, you can avoid the router model’s post-tool synthesis call by using LangChain’s return_direct=True tool behavior, where supported by your installed version.

For example:

@tool(return_direct=True)
async def rag_agent(query: str) -> str:
    """Answer document questions."""
    result = await rag_agent_executor.ainvoke({
        "messages": [{"role": "user", "content": query}]
    })
    return result["messages"][-1].content

With return_direct=True, the agent can finish after the tool response rather than invoking the routing model again.

This is particularly useful for your architecture because the selected subagent is responsible for generating the final answer.

6. Full history handling for follow-up requests

I would make one further adjustment before deploying this in Tachyon.

Instead of passing only the latest query to the selected agent, provide a history-aware tool contract:

@tool(return_direct=True)
async def text_to_sql_agent(
    query: str,
    conversation_history: list[dict],
) -> str:
    """Execute structured database queries."""
    ...

However, do not populate conversation_history from untrusted model-generated arguments. The middleware should inject history from trusted agent state or runtime context.

The desired flow is:

User: Show my last 10 transactions.
  → Decisions: text_to_sql
  → SQL Agent: Executes transaction query
User: What about the previous month?
  → Decisions receives both turns
  → Decisions: text_to_sql
  → SQL Agent receives:
       Latest query: What about the previous month?
       Previous query: Show my last 10 transactions.
       Previous answer: ...
  → SQL Agent resolves the follow-up correctly

If you use Redis checkpointing, the routing middleware can access the restored conversation through request.state["messages"], assuming the same thread is reused and history has not been trimmed.

7. Recommended production behavior

Requirement	Recommended implementation
Route based on full conversation	request.state[“messages”] plus history converter
SQL vs RAG classification	Decisions API choice
Low-confidence or ambiguous route	Existing awrap_model_call fallback
Preserve existing model middleware	Register decision middleware first
Preserve tool middleware	Return AIMessage with a valid tool call
Avoid unnecessary router LLM call	Use return_direct=True on subagent tools
Support contextual follow-ups	Inject trusted history into selected subagent
Prevent repeated decisions	Per-turn state marker or deduplication
Preserve entitlements	Existing wrap_tool_call and subagent authorization
Support observability	OpenTelemetry spans for decision, routing, and subagent execution

The key architectural recommendation is to make the Decisions API responsible only for choosing the agent, while the selected SQL or RAG agent handles the actual question. That allows the Decisions API to replace the routing LLM call without forcing it to generate SQL, retrieve documents, or produce the final response.

For production, I would additionally verify the installed OpenAI Decisions response schema, enforce history-size and sensitive-data limits, and test that a synthetic tool call is accepted by your LangChain version before rolling this into Tachyon SDK.