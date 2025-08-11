Got it — you basically want to “stack” your own decorator on top of FastMCP’s @mcp.tool and have its metadata automatically appear in the List Tools response when the MCP server returns the tool list.

The good news is that MCP tools in fastmcp are just Python callables with some metadata stored as attributes (usually on .__mcp_metadata__ or .__annotations__), so we can extend the tool metadata at definition time without touching FastMCP internals.

Here’s a minimal pattern to achieve what you’re asking:


---

1. Custom decorator that adds extra metadata

We’ll create a decorator that:

Wraps @tool from fastmcp

Adds our custom metadata to the function (e.g., entitlement details)

Ensures that the list_tools output includes this extra data


from fastmcp import tool

def tachyon_entitlement(entitlement_name: str):
    """
    Decorator to attach entitlement metadata to MCP tools.
    """
    def decorator(func):
        # Attach entitlement metadata
        setattr(func, "__tachyon_entitlement__", entitlement_name)
        return func
    return decorator


def entitlement_tool(entitlement_name: str, *tool_args, **tool_kwargs):
    """
    Combines FastMCP's @tool with entitlement metadata.
    """
    def wrapper(func):
        # First apply fastmcp.tool
        mcp_wrapped = tool(*tool_args, **tool_kwargs)(func)

        # Then attach entitlement metadata
        setattr(mcp_wrapped, "__tachyon_entitlement__", entitlement_name)

        return mcp_wrapped
    return wrapper


---

2. Example tool definition

@entitlement_tool("read_customer_data", name="get_customer", description="Fetch customer details by ID")
async def get_customer(customer_id: str) -> dict:
    return {"customer_id": customer_id, "name": "John Doe"}


---

3. Modifying list_tools to include entitlement data

FastMCP’s server has a list_tools method that’s called to send back tool metadata.
We can subclass the FastMCP server (or override its list handler) to also include our decorator info:

from fastmcp import FastMCP

class EntitlementAwareFastMCP(FastMCP):
    async def list_tools(self):
        tools = await super().list_tools()
        for tool in tools:
            # tool["name"] corresponds to function name registered
            func = self._tool_registry.get(tool["name"])
            if func and hasattr(func, "__tachyon_entitlement__"):
                tool["entitlement"] = getattr(func, "__tachyon_entitlement__")
        return tools


---

4. Running the server

app = EntitlementAwareFastMCP()

# Register your tool
app.register_tool(get_customer)

if __name__ == "__main__":
    import asyncio
    asyncio.run(app.run_http_async("localhost", 8000))


---

✅ How this works:

When you decorate with @entitlement_tool, both FastMCP’s @tool metadata and your __tachyon_entitlement__ attribute get attached to the function.

In list_tools, we intercept the default behavior and augment each tool entry with the extra metadata from your decorator.

Now, when your MCP client calls list_tools, it will also see the entitlement data in the JSON output.



---

If you want, I can also make a version where the decorator directly injects into FastMCP’s internal __mcp_metadata__, so you don’t need to override list_tools at all — the entitlement will just magically appear in the MCP protocol response without subclassing.

Do you want me to make that version? That would make it totally transparent.

