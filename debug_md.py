import md_viewer
import sys

def print_tree(node, depth=0):
    indent = "  " * depth
    content = ""
    if node.spans:
        content = f" spans={len(node.spans)} text='{node.spans[0][0][:20]}...'"
    elif node.children:
        content = f" children={len(node.children)}"

    margin_info = f" margin={node.style.margin}"

    print(f"{indent}{node.type}{content}{margin_info}")
    for child in node.children:
        print_tree(child, depth + 1)

try:
    with open("test.md", "r") as f:
        text = f.read()

    # print("Parsing test.md...")
    root = md_viewer.parse_markdown(text)
    print_tree(root)

except Exception as e:
    print(f"Error: {e}")
