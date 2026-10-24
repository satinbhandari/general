
For Tachyon SDK 3.0, I recommend implementing this as a Decision-First AgentMiddleware, registered before your existing awrap_model_call middleware.

The implementation will follow these rules:

* The Decisions API receives the complete conversation history available in the agent’s checkpointed state, including user messages, assistant messages, tool calls, and tool responses.
* The decision middleware executes before your existing model-call middleware.
* If the decision can be resolved through an approved action, it returns the result without calling the primary LLM.
* If it cannot resolve the request, it delegates to your existing awrap_model_call through handler(request).
* It evaluates the decision only once per incoming user turn, not after every tool response.
* Existing authentication, entitlement checks, observability, and tool middleware remain intact.

One important limitation: OpenAI’s Decisions API returns structured decisions, not arbitrary generated responses or executable tool calls. Therefore, the implementation needs an action registry to map a decision to a safe, executable operation.

1. Complete middleware implementation

The following implementation uses native Decisions API conversation messages, including function-call IDs. It also uses a checkpointed state marker so the decision is not repeatedly evaluated during a tool-calling loop.

The initial example supports two outcomes: a registered deterministic response or fallback to the normal LangChain agent.

# tachyon_decision_middleware.py
import json
import logging
from typing import Any, Callable
from openai import AsyncOpenAI
from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    ModelRequest,
    ModelResponse,
)
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.types import Command
from typing_extensions import NotRequired
logger = logging.getLogger(__name__)
class DecisionState(AgentState):
    decision_turn_id: NotRequired[str]
def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False, default=str)
def to_decision_input(messages):
    """Convert LangChain history to native Decisions input.
    Supports text messages and completed function-call pairs.
    Fail closed to fallback for unsupported multimodal content.
    """
    output = []
    for message in messages:
        if isinstance(message, SystemMessage):
            output.append({
                "role": "developer",
                "content": [
                    {"type": "input_text", "text": _text(message.content)}
                ],
            })
        elif isinstance(message, HumanMessage):
            output.append({
                "role": "user",
                "content": [
                    {"type": "input_text", "text": _text(message.content)}
                ],
            })
        elif isinstance(message, AIMessage):
            if message.content:
                output.append({
                    "role": "assistant",
                    "content": [
                        {"type": "output_text", "text": _text(message.content)}
                    ],
                })
            for call in message.tool_calls:
                output.append({
                    "type": "function_call",
                    "call_id": call["id"],
                    "name": call["name"],
                    "arguments": json.dumps(
                        call["args"], ensure_ascii=False
                    ),
                })
            if message.invalid_tool_calls:
                raise ValueError("Invalid tool calls in history")
        elif isinstance(message, ToolMessage):
            output.append({
                "type": "function_call_output",
                "call_id": message.tool_call_id,
                "output": _text(message.content),
            })
        else:
            raise ValueError(
                f"Unsupported message type: {type(message).__name__}"
            )
    return output
class TachyonDecisionMiddleware(AgentMiddleware):
    state_schema = DecisionState
    def __init__(
        self,
        responses: dict[str, str],
        *,
        client: AsyncOpenAI | None = None,
        model: str = "gpt-6-luna",
        confidence_threshold: float = 0.90,
    ):
        self.client = client or AsyncOpenAI()
        self.model = model
        self.responses = responses
        self.confidence_threshold = confidence_threshold
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable,
    ) -> ModelResponse:
        messages = request.state["messages"]
        # After a tool call, use the existing model chain.
        if not messages or not isinstance(
            messages[-1], HumanMessage
        ):
            return await handler(request)
        current_turn = messages[-1].id
        if not current_turn:
            # Do not risk repeated evaluations without a stable ID.
            return await handler(request)
        # Avoid re-evaluating the same user turn.
        if request.state.get("decision_turn_id") == current_turn:
            return await handler(request)
        # Build options from trusted application configuration.
        choices = [
            {
                "value": key,
                "description": f"Use the approved response: {key}",
            }
            for key in self.responses
        ]
        choices.append({
            "value": "fallback",
            "description": (
                "The request requires generative reasoning, "
                "external data, tool execution, or cannot be "
                "fully answered by an approved response."
            ),
        })
        try:
            history = to_decision_input(messages)
            decision = await self.client.decisions.create(
                model=self.model,
                input=history,
                questions=[{
                    "type": "choice",
                    "name": "execution_route",
                    "instructions": (
                        "Evaluate the latest user request using "
                        "the complete conversation. Select an "
                        "approved response only if it completely "
                        "satisfies the latest request in context. "
                        "Otherwise select fallback. Do not "
                        "assume missing facts."
                    ),
                    "choices": choices,
                }],
            )
            answer = decision.answers[0]
            if (
                answer.type == "choice"
                and answer.choice in self.responses
                and answer.confidence >= self.confidence_threshold
            ):
                response = AIMessage(
                    content=self.responses[answer.choice],
                    response_metadata={
                        "tachyon_source": "decisions",
                        "decision_confidence": answer.confidence,
                    },
                )
                return ModelResponse(
                    result=[response],
                    command=Command(update={
                        "decision_turn_id": current_turn,
                    }),
                )
        except Exception:
            logger.exception(
                "Decision evaluation failed; using primary model"
            )
        # The primary LLM and all downstream model middleware
        # execute only on fallback.
        return await handler(request)

Implementation note: The example deliberately handles text and function-call history, not every LangChain content-block type. Images, custom tools, reasoning blocks, and other multimodal messages need additional converters. Unsupported types should trigger fallback rather than being silently discarded.

The native conversation format and matching call_id requirements are documented by OpenAI.

2. Register it before your existing awrap_model_call

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
decision_middleware = TachyonDecisionMiddleware(
    responses={
        "greeting": "Hello! How can I assist you?",
        "capabilities": (
            "I can assist with document retrieval, "
            "database queries, and general questions."
        ),
    },
    confidence_threshold=0.90,
)
agent = create_agent(
    model=ChatOpenAI(model="gpt-5.4"),
    tools=[sql_tool, rag_tool, web_tool],
    middleware=[
        decision_middleware,          # First model-call wrapper
        ExistingModelMiddleware(),    # Your existing wrapper
        ExistingToolMiddleware(),     # Your existing tool wrapper
    ],
    checkpointer=InMemorySaver(),
)
config = {
    "configurable": {
        "thread_id": "tachyon-session-123"
    }
}
# First turn
result = await agent.ainvoke(
    {"messages": [
        {"role": "user", "content": "Hello"}
    ]},
    config=config,
)
# Second turn: same thread, history restored
result = await agent.ainvoke(
    {"messages": [
        {"role": "user", "content": "What can you do?"}
    ]},
    config=config,
)

The same thread_id allows LangGraph to restore previous messages through the checkpointer. In production, replace InMemorySaver with your Redis checkpointer and ensure thread IDs are isolated by agent and conversation.

3. How the middleware interact

Execution stage	Decision resolves	Decision falls back
Decision awrap_model_call	Runs	Runs
Existing awrap_model_call	Skipped	Runs
Primary ChatOpenAI	Skipped	Runs
Existing awrap_tool_call	Skipped	Runs if a tool is requested
Agent checkpointing	Continues	Continues

There are two refinements I would make before deploying this implementation.

First: once-per-turn state management. The code illustrates storing a decision_turn_id with a Command, but you should verify the exact ModelResponse command support in your installed LangChain version. More importantly, the fallback branch must also persist the evaluated turn ID. Otherwise, retries could call Decisions again. A before_model state-update hook or a dedicated state-management component is preferable to an instance-level variable, especially with concurrent requests.

Second: preserve your complete effective context. request.state["messages"] contains checkpointed conversation messages, but it does not necessarily include system prompts added through create_agent(system_prompt=...), middleware-injected instructions, or external long-term memory. If the Decisions API needs those too, merge them explicitly into the decision input. Keep security-sensitive system instructions and tool results subject to your normal data-handling controls.

4. Expected Decisions API payload

For a conversation involving tools, the final input should conceptually resemble:

{
  "model": "gpt-6-luna",
  "input": [
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "What is my account balance?"
        }
      ]
    },
    {
      "type": "assistant",
      "content": [
        {
          "type": "output_text",
          "text": "Your account balance is ₹50,000."
        }
      ]
    },
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "What was the balance you just mentioned?"
        }
      ]
    }
  ],
  "questions": [
    {
      "type": "choice",
      "name": "execution_route",
      "instructions": "Determine whether an approved deterministic response can fully satisfy the latest request using conversation history. Otherwise choose fallback.",
      "choices": [
        {
          "value": "approved_response",
          "description": "A trusted application response fully answers the request."
        },
        {
          "value": "fallback",
          "description": "The primary agent is required."
        }
      ]
    }
  ]
}

This example illustrates the structure; the choice names and descriptions must correspond to your actual response registry. For this balance follow-up, a generic approved response would not suffice unless your application also implements a deterministic way to retrieve the specific balance from history.

5. My recommendation for your production design

For Tachyon SDK, I would keep the following interfaces:

Component	Responsibility
TachyonDecisionMiddleware	Intercept model calls and short-circuit
TachyonDecisionClient	Call /v1/decisions
DecisionHistoryConverter	Convert full LangChain message history
DecisionActionRegistry	Map choices to approved responses/actions
DecisionTurnState	Guarantee at-most-once evaluation per turn
Existing model middleware	Handle normal primary LLM execution
Existing tool middleware	Handle tool authorization and execution

The code above is a foundation rather than a fully production-validated implementation. In particular, I would test the ModelResponse state-update contract and message serialization against your installed LangChain/OpenAI SDK versions before rollout.

The most valuable next enhancement is dynamic answer reuse. For example, when the user asks, “What was the balance you mentioned earlier?”, the Decisions API could select a trusted history-lookup action, and Tachyon could retrieve that value without another generative LLM call. That is a more useful decision-first optimization than simply bypassing the LLM for greetings.

It also keeps the responsibilities clear: Decisions selects the action; Tachyon executes it; the primary agent handles everything else.