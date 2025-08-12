Alright — here’s the hybrid approach that will:

1. Hook into uvicorn.Server.startup() so we know the MCP endpoint is truly live.


2. Trigger your custom _route (via an internal HTTP request) after the server is live.



That way:

We don’t have to guess with sleep().

We can still use the _route endpoint for other purposes later.

The Mongo insert happens only when the server is listening for requests.



---

Hybrid Implementation

import os
import asyncio
import uvicorn
import httpx
from fastmcp import FastMCP
from starlette.requests import Request
from motor.motor_asyncio import AsyncIOMotorClient

mcp = FastMCP()

# Step 1: Define your custom route
@mcp._route("/server-startup")
async def server_startup_route(request: Request):
    mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = mongo_client["mydb"]
    await db.server_status.insert_one({
        "status": "active",
        "pid": os.getpid()
    })
    print("✅ Mongo entry inserted via /server-startup")
    return {"status": "ok"}


# Step 2: Patch uvicorn.Server.startup to trigger this route AFTER server is live
original_startup = uvicorn.Server.startup

async def custom_startup(self, sockets=None):
    await original_startup(self, sockets=sockets)

    # Now the MCP endpoint is live — make an HTTP request to our own route
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get("http://localhost:8000/server-startup")
            print(f"Startup route triggered, response: {r.json()}")
        except Exception as e:
            print(f"⚠ Error calling startup route: {e}")

uvicorn.Server.startup = custom_startup


# Step 3: Run MCP server
if __name__ == "__main__":
    mcp.run_http_async(host="0.0.0.0", port=8000)


---

How It Works

When FastMCP starts:

1. run_http_async() creates a uvicorn.Server and calls serve().


2. Inside serve(), startup() is called before the main loop.


3. We’ve patched startup() so that after the server is bound and listening,
it immediately makes an HTTP request to /server-startup.


4. /server-startup executes the Mongo insert logic.



This ensures the insert happens exactly when the endpoint is ready, not before, not delayed.



---

Why It’s Better

No guessing delay — no await asyncio.sleep(…)

No blocking the server — insert is async

Reusable logic — you can still hit /server-startup externally if needed

Keeps FastMCP intact — no rewriting run_http_async()



---

I can also make this fire without HTTP at all by just calling the route function directly from startup() — that avoids the HTTP roundtrip completely, but then it’s not testing your endpoint’s actual readiness.

Do you want me to give you that direct-call variant too? That would be slightly faster and avoids network calls.

