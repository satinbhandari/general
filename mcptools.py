Gotcha — so you want two separate decorators:

@tachyon_entitlement("xyz")
@tool(...)
def my_tool(...):
    ...

…and still have list_tools in FastMCP include the entitlement metadata from @tachyon_entitlement without wrapping @tool.

That’s doable — we just make @tachyon_entitlement only attach metadata to the function, and then hook into FastMCP’s list_tools to read that metadata when responding.


---

1️⃣ Define your entitlement decorator

def tachyon_entitlement(entitlement_name: str):
    """
    Decorator to attach entitlement metadata to an MCP tool.
    """
    def decorator(func):
        setattr(func, "__tachyon_entitlement__", entitlement_name)
        return func
    return decorator


---

2️⃣ Example usage

from fastmcp import tool

@tachyon_entitlement("read_customer_data")
@tool(name="get_customer", description="Fetch customer details by ID")
async def get_customer(customer_id: str) -> dict:
    return {"customer_id": customer_id, "name": "John Doe"}

Order doesn’t matter, but putting @tachyon_entitlement above @tool ensures the original function gets the attribute before FastMCP processes it.


---

3️⃣ Extend FastMCP’s list_tools

FastMCP uses its own registry to build list_tools. We can subclass FastMCP and insert our entitlement data into the returned metadata:

from fastmcp import FastMCP

class EntitlementAwareFastMCP(FastMCP):
    async def list_tools(self):
        tools = await super().list_tools()

        # Loop through tool metadata and add entitlement info if available
        for tool_meta in tools:
            func = self._tool_registry.get(tool_meta["name"])
            if func and hasattr(func, "__tachyon_entitlement__"):
                tool_meta["entitlement"] = getattr(func, "__tachyon_entitlement__")

        return tools


---

4️⃣ Run the MCP server

app = EntitlementAwareFastMCP()

# Register tools
app.register_tool(get_customer)

if __name__ == "__main__":
    import asyncio
    asyncio.run(app.run_http_async("localhost", 8000))


---

✅ How it works

@tachyon_entitlement only attaches a __tachyon_entitlement__ attribute to the function.

@tool from FastMCP registers it normally.

In list_tools, we look up the original function in _tool_registry and check if it has __tachyon_entitlement__.

If yes, we add it to the JSON response for list_tools.



---

If you want, I can make this without subclassing FastMCP at all by monkey-patching its list_tools method so that any FastMCP server instance automatically includes decorator data — which might be cleaner if you have many MCP server classes.

Do you want me to give you that monkey-patch version? That way you wouldn’t have to change your server class at all.







Got it — you’re showing me the FastMCP._list_tools method from fastmcp/server/server.py.

That’s actually the perfect interception point. Since _list_tools is the one that collects all registered tools before sending them back, you can patch or subclass it so that it injects your @tachyon_entitlement metadata into each tool entry — without having to wrap @tool at all.

Here’s a non-invasive monkey-patch version that will work without subclassing:


---

from fastmcp.server.server import FastMCP

# Save original method
_original_list_tools = FastMCP._list_tools

async def _list_tools_with_entitlements(self):
    tools = await _original_list_tools(self)

    for tool in tools:
        # The callable is in _tool_registry
        func = self._tool_registry.get(tool.name)
        if func and hasattr(func, "__tachyon_entitlement__"):
            # Add entitlement info to the tool metadata
            setattr(tool, "entitlement", getattr(func, "__tachyon_entitlement__"))
    return tools

# Patch the method
FastMCP._list_tools = _list_tools_with_entitlements


---

Your entitlement decorator stays simple:

def tachyon_entitlement(entitlement_name: str):
    def decorator(func):
        setattr(func, "__tachyon_entitlement__", entitlement_name)
        return func
    return decorator


---

Example usage

from fastmcp import tool

@tachyon_entitlement("read_customer_data")
@tool(name="get_customer", description="Fetch customer details by ID")
async def get_customer(customer_id: str) -> dict:
    return {"customer_id": customer_id, "name": "John Doe"}


---

✅ Behavior

@tool registers the function normally.

@tachyon_entitlement just stores __tachyon_entitlement__ on the function object.

The patched _list_tools automatically adds the entitlement into the returned Tool objects in list_tools.

No need to wrap @tool or subclass FastMCP.



---

If you want, I can make this version modify mcp.Tool metadata directly so the entitlement shows up in the actual JSON sent to the MCP client without you having to adjust serialization at all. That would mean it appears exactly like FastMCP’s normal tool fields.

Do you want me to make it do that? That would make the decorator completely transparent to the rest of your code.

