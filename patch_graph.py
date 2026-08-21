import os
import re

def patch_graph():
    filepath = "backend/services/orchestrator/app/graph.py"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    if "get_tracer" in content:
        print("Graph already patched.")
        return

    import_statement = """from observability import get_tracer

tracer = get_tracer("orchestrator_graph")
"""
    # Insert after StateGraph, START, END
    content = content.replace("from langgraph.graph import StateGraph, START, END", "from langgraph.graph import StateGraph, START, END\n" + import_statement)

    # We need to wrap the body of retrieve_node, plan_node, generate_sql_node, execute_sql_node, visualization_node, repair_node
    nodes = ["retrieve_node", "plan_node", "generate_sql_node", "execute_sql_node", "visualization_node", "repair_node"]

    for node in nodes:
        # Find the function definition
        pattern = r"def " + node + r"\(state: ConversationState\) \-\> dict:\n(.*?)(\n\n|$)"
        
        # It's tricky to use regex for multi-line function bodies due to indentation.
        # Let's do it line by line.

    lines = content.split('\n')
    new_lines = []
    in_node = False
    current_node = ""
    for line in lines:
        if line.startswith("def ") and "_node(state: ConversationState) -> dict:" in line:
            in_node = True
            current_node = line.split("def ")[1].split("(")[0]
            new_lines.append(line)
            new_lines.append(f'    with tracer.start_as_current_span("{current_node}"):')
            continue
            
        if in_node:
            if line.startswith("def ") or line.startswith("# ──"):
                in_node = False
                new_lines.append(line)
            elif len(line.strip()) > 0:
                new_lines.append("    " + line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))

    print("Patched graph.py")

if __name__ == "__main__":
    patch_graph()
