Yes—use ClientFactory with a custom httpx.AsyncClient and inject per-request headers via an event hook or a transport wrapper so each send_message call gets fresh headers computed at call time ���.Pattern 1: httpx event hooks (per-call)httpx supports request hooks that run before each request, letting you compute and attach new headers every time �.Provide this client to ClientFactory (or to get_client_from_agent_card_url) so all A2A operations, including send_message, use those dynamic headers ��.import asyncio
import httpx
from uuid import uuid4
from a2a.client.client import A2AClient
from a2a.types import SendMessageRequest, MessageSendParams

async def per_request_headers(request: httpx.Request):
    # Compute unique headers for this specific call
    request.headers["X-Request-ID"] = uuid4().hex
    request.headers["X-Tenant"] = pick_tenant_from_context()  # your logic
    token = await get_fresh_token()                            # rotate per call
    request.headers["Authorization"] = f"Bearer {token}"

async def main():
    async with httpx.AsyncClient(event_hooks={"request": [per_request_headers]}) as httpx_client:
        client = await A2AClient.get_client_from_agent_card_url(
            httpx_client=httpx_client,
            base_url="https://agent.example"  # auto-resolves agent card
        )
        req = SendMessageRequest(params=MessageSendParams(
            message={
                "role": "user",
                "parts": [{"type": "text", "text": "hello"}],
                "messageId": uuid4().hex,
            }
        ))
        resp = await client.send_message(req)
        print(resp)

asyncio.run(main())Each send_message call triggers the request hook, ensuring different headers per call while staying within the A2A client factory flow that takes an external httpx client ��.Pattern 2: Custom ClientFactory subclassOverride ClientFactory to supply a preconfigured AsyncClient with per-request hooks; create clients through this factory so per-call headers are always applied ��.import httpx
from uuid import uuid4
from a2a.client.client_factory import ClientFactory, ClientConfig
from a2a.client.client import A2AClient

async def per_request_headers(request: httpx.Request):
    request.headers["X-Request-ID"] = uuid4().hex
    request.headers["Authorization"] = f"Bearer {await get_fresh_token()}"

class MyClientFactory(ClientFactory):
    def __init__(self, config: ClientConfig):
        super().__init__(config)
        # Lazily create an AsyncClient with hooks; stored in config or on self
        self._httpx = httpx.AsyncClient(event_hooks={"request": [per_request_headers]})

    def create(self, card, consumers=None, interceptors=None):
        # Ensure the factory’s httpx client is used by produced A2A clients
        self._config.httpx_client = self._httpx
        return super().create(card, consumers, interceptors)

# Usage: resolve card then build client via factory
# card = await A2ACardResolver(...).resolve(...)
# client = MyClientFactory(ClientConfig()).create(card)This approach mirrors patterns used to inject auth into httpx clients for A2A factories and remote agents, ensuring headers are set per request at the transport layer used by send_message ��.Pattern 3: Transport wrapper for maximum controlWrap httpx.AsyncBaseTransport to inject headers right before sending, which also computes values per request; pass the client with this transport to the factory �.This is useful if you prefer not to rely on event hooks and want transport-level control similar to other SDK interceptor patterns �.import httpx
from uuid import uuid4

class HeaderInjectingTransport(httpx.AsyncBaseTransport):
    def __init__(self, wrapped: httpx.AsyncBaseTransport):
        self._wrapped = wrapped

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        request.headers["X-Request-ID"] = uuid4().hex
        request.headers["Authorization"] = f"Bearer {await get_fresh_token()}"
        return await self._wrapped.handle_async_request(request)

transport = HeaderInjectingTransport(httpx.AsyncHTTPTransport())
httpx_client = httpx.AsyncClient(transport=transport)
# Hand this httpx_client into A2AClient factory/get_client_from_agent_card_urlTransport wrappers ensure new headers are applied per call, and they work cleanly with A2AClient’s use of the provided httpx client under ClientFactory or the class factory method ��.When to use whichEvent hooks: simplest, idiomatic httpx per-request mutation and easy async token refresh �.ClientFactory subclass: centralize client creation and keep the A2A wiring encapsulated, commonly used where factories also configure auth and retries ��.Transport wrapper: strongest guarantees and easy testability if you need to enforce headers regardless of call site �.