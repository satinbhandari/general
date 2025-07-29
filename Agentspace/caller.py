import json
from graphfromjson import generate_langgraph_code_from_json
 
# Load your JSON spec
with open("test.json") as f:
    spec = json.load(f)

# Generate code
code = generate_langgraph_code_from_json(spec)

# Save it to file
with open("generated_langgraph.py", "w") as f:
    f.write(code)
