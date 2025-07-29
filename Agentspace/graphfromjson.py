import json
import textwrap

def generate_langgraph_code_from_json(json_spec: dict) -> str:
    graph_name = json_spec["name"]
    class_name = ''.join(word.capitalize() for word in graph_name.replace("-", "_").split('_'))

    # Step 1: State class attributes
    state_keys = json_spec.get("state_keys", [])
    state_lines = [f"        {key['key_name']}: {key['key_type']}" for key in state_keys]

    # Step 2: Models in __init__
    model_lines = []
    for model in json_spec.get("models", []):
        model_id = model["model_id"]
        model_name = model["model_name"]
        other_params = ', '.join([f"{k}={json.dumps(v)}" for k, v in model.items() if k not in {"model_name", "model_id"}])
        model_lines.append(f'        self.llm_{model_id} = CustomClient("{model_name}", {other_params})')

    # Step 3: Python tool methods
    python_tool_lines = []
    for tool in json_spec.get("python_tools", []):
        func = f"""    def {tool['tool_id']}(self):\n{textwrap.indent(tool['tool_definition'].strip(), '        ')}\n"""
        python_tool_lines.append(func)

    # Step 4: MCP tool methods
    mcp_tool_lines = []
    for tool in json_spec.get("mcp_tools", []):
        method = f"""    def create_{tool['mcp_server_id']}_server(self):
        params = StdioServerParams(**{json.dumps(tool['mcp_server_params'], indent=8)})
        return ClientSession(command="{tool['mcp_start_command']}", params=params)\n"""
        mcp_tool_lines.append(method)

    # Step 5: Node methods
    node_methods = []
    node_id_to_name = {}
    for node in json_spec["nodes"]:
        node_id = node["id"]
        node_name = node["name"]
        node_id_to_name[node_id] = node_name
        tools = node.get("tools", []) + node.get("mcp_tools", [])
        tool_list = "[" + ", ".join(tools) + "]" if tools else "[]"
        system_instruction = node["system_instruction"].replace('"', '\\"')
        model_ref = f"self.llm_{node['model_id']}"
        method = f"""    def {node_name}(self, state):
        # Node ID: {node_id}
        tools = {tool_list}
        agent = create_react_agent({model_ref}, "{system_instruction}", tools)
        return agent.invoke(state)\n"""
        node_methods.append(method)

    # Step 6: Graph build method
    node_adds = [f'        builder.add_node("{node["name"]}", self.{node["name"]})' for node in json_spec["nodes"]]

    edge_adds = []
    for edge in json_spec.get("normal_edges", []):
        from_node = node_id_to_name[edge["from"]]
        to_node = node_id_to_name[edge["to"]]
        edge_adds.append(f'        builder.add_edge("{from_node}", "{to_node}")')

    for edge in json_spec.get("conditional_edges", []):
        from_node = node_id_to_name[edge["from"]]
        to_node = node_id_to_name[edge["to"]]
        key = edge["key"]
        value = edge["value"]
        edge_adds.append(
            f'        builder.add_conditional_edge("{from_node}", "{key}", '
            f'lambda x: x["{key}"] == "{value}", "{to_node}")'
        )

    # Step 7: Full class assembly
    class_def = f"""
from langgraph.graph import StateGraph
from mcp import StdioServerParams, ClientSession
from myclient import CustomClient
from myagents import create_react_agent

class {class_name}:
    class State:
{chr(10).join(state_lines)}

    def __init__(self):
{chr(10).join(model_lines)}

{chr(10).join(python_tool_lines)}
{chr(10).join(mcp_tool_lines)}
{chr(10).join(node_methods)}

    def build(self):
        builder = StateGraph(self.State)
{chr(10).join(node_adds)}
{chr(10).join(edge_adds)}
        return builder.compile()
"""
    return class_def.strip()
