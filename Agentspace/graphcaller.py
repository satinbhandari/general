import types
import json

from graphfromjson import generate_langgraph_code_from_json
 
# Load your JSON spec
with open("test.json") as f:
    json_spec = json.load(f)
    
# Assume this contains the generated class code from your JSON
generated_code_str = generate_langgraph_code_from_json(json_spec)

# Define the class name (based on the graph name)
class_name = ''.join(word.capitalize() for word in json_spec["name"].replace("-", "_").split('_'))

# Create a new module
graph_module = types.ModuleType("generated_graph")

# Execute the code inside the module's namespace
exec(generated_code_str, graph_module.__dict__)

# Get the class by name
GraphClass = getattr(graph_module, class_name)

# Instantiate the class
graph_instance = GraphClass()

# Build the LangGraph
compiled_graph = graph_instance.build()

# Prepare initial state (all required fields must be set)
initial_state = GraphClass.State(
    # Set your actual state values here
    user_query="Give me tech news",
    news_list=[],
    news_summary=""
)

# Invoke the graph
output = compiled_graph.invoke(initial_state)
print(output)
