import os
import tree_sitter_c as tsc
import tree_sitter
import json,sys
from collections import deque
from tree_sitter import Language, Parser
from contextlib import redirect_stdout
from typing import List, Tuple, Dict, Set, Optional
from init import *

C_LANGUAGE = Language(tsc.language())
parser = Parser(C_LANGUAGE)

def find_nodes_by_type(
        root_node: tree_sitter.Node, node_type: str
    ) -> List[tree_sitter.Node]:
        """
        Find all the nodes with the specific type in the parse tree
        :param root_node: the root node of the parse tree
        :param node_type: the type of the nodes to be found
        """
        nodes = []
        if root_node.type == node_type:
            nodes.append(root_node)
        for child_node in root_node.children:
            nodes.extend(find_nodes_by_type(child_node, node_type))
        return nodes

def find_first_node_by_type(root_node: tree_sitter.Node, node_type: str) -> tree_sitter.Node:
    # Initialize the queue with the root node
    queue = deque([root_node])
    # Perform BFS
    while queue:
        # Get the next node in the queue
        current_node = queue.popleft()

        # Check if the current node matches the target type
        if current_node.type == node_type:
            return current_node

        # Add the children of the current node to the queue
        for child_node in current_node.children:
            queue.append(child_node)

    # Return None if no node of the specified type was found
    return None

def generate_function_summary(code: str) -> dict:
    prompt = f"""Analyze the following C function and return:
1. A one-sentence summary of what it does.
2. The function's input parameters and their types.
3. The function's return type.

Respond in this JSON format:
{{
  "summary": "...",
  "input": "...",
  "output": "..."
}}

Function:
```c
{code}
```"""
    while True:
        try:
            text = askLLM(prompt)
            # print(f"🔁 LLM Response:\n{text}\n")
            result = json.loads(text)
            if all(k in result for k in ("summary", "input", "output")):
                return result
        except Exception as e:
            continue

def generate_file_summary(function_map: dict) -> str:
    fn_summaries = "\n".join(
        f"- {fn_name}: {fn_info['summary']}" for fn_name, fn_info in function_map.items()
    )

    file_prompt = f"""Here is a list of functions and what they do:

{fn_summaries}

Write a paragraph summary of this file based on the above functions.
"""
    return askLLM(file_prompt).strip()

def get_function_summaries(source_code, tree: tree_sitter.Tree):
    function_map = {}
    
    def extract_text(node):
        return source_code[node.start_byte:node.end_byte].decode("utf8")
    
    all_function_nodes = find_nodes_by_type(tree.root_node, "function_definition")
    for func_node in all_function_nodes:
        dec_node = find_first_node_by_type(func_node, "function_declarator") 
        if dec_node:           
            for sub_node in dec_node.children:
                if sub_node.type == "identifier":
                    function_name = source_code[sub_node.start_byte:sub_node.end_byte].decode("utf8")
                    function_map[function_name] = {
                        "start_byte": func_node.start_byte,
                        "end_byte": func_node.end_byte,
                        "input": generate_function_summary(extract_text(func_node))['input'],
                        "output": generate_function_summary(extract_text(func_node))['output'],
                        "summary": generate_function_summary(extract_text(func_node))['summary']
                    }
                    
    all_def_funciton_nodes =  find_nodes_by_type(tree.root_node, "preproc_function_def")
    for func_node in all_def_funciton_nodes:
        for sub_node in func_node.children:
            if sub_node.type == "identifier":
                function_name = source_code[sub_node.start_byte:sub_node.end_byte].decode("utf8")
                function_map[function_name] = {
                        "start_byte": func_node.start_byte,
                        "end_byte": func_node.end_byte,
                        "input": generate_function_summary(extract_text(func_node))['input'],
                        "output": generate_function_summary(extract_text(func_node))['output'],
                        "summary": generate_function_summary(extract_text(func_node))['summary']
                    }
                
    return function_map

def summarize_directory(directory: str, module_name=None) -> dict:
    if module_name is None:
        module_name = os.path.basename(os.path.normpath(directory))

    folder_summary = {
        "summary": "",  # will be filled later
        "files": {}
    }

    all_file_summaries = []

    for entry in sorted(os.listdir(directory)):
        full_path = os.path.join(directory, entry)

        # 📁 Subdirectory — recurse
        if os.path.isdir(full_path) and not entry.startswith("."):
            print(f"📁 Entering folder: {full_path}")
            sub_summary = summarize_directory(full_path, module_name)
            folder_summary["files"][entry] = sub_summary
            all_file_summaries.append(f"{entry}/: {sub_summary['summary']}")

        # 📄 Source file
        elif entry.endswith(".c") or entry.endswith(".h"):
            print(f"📄 Processing file: {entry}")
            with open(full_path, "rb") as f:
                content = f.read()
            tree = parser.parse(content)

            function_list = get_function_summaries(content, tree)

            file_summary = generate_file_summary(function_list)
            folder_summary["files"][entry] = {
                "summary": file_summary,
                "functions": function_list
            }
            all_file_summaries.append(f"{entry}: {file_summary}")

    # 🧠 Generate summary of this folder (file or module)
    prompt = f"""Here are the summaries of items in the folder "{os.path.basename(directory)}":

{chr(10).join(f"- {s}" for s in all_file_summaries)}

Write a 1-2 sentence summary of this folder's purpose based on its contents.
"""
    folder_summary["summary"] = askLLM(prompt).strip()

    return folder_summary

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python repo.py /path/to/repo/")
        exit(1)

    directory = sys.argv[1]
    results = summarize_directory(directory)

    # Optionally write to JSON for LLM input
    with open("summary.json", "w") as out:
        json.dump(results, out, indent=2)