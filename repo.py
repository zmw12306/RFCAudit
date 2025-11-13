import os
import json
import tree_sitter
from tree_sitter import Language, Parser
from query_repo_recursive import find_nodes_by_type, find_first_node_by_type, find_first_father_by_type, parser
from init import *

def generate_function_summary(code: str) -> dict:
    prompt = f"""Analyze the following C function and return:
A one-sentence summary of what it does.

Function:
```c
{code}
```"""
    while True:
        try:
            text = askLLM(prompt)
            return text
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
                if sub_node.type in {"qualified_identifier", "scoped_identifier", "identifier"}:
                    function_name = source_code[sub_node.start_byte:sub_node.end_byte].decode("utf8")
                    summary = generate_function_summary(extract_text(func_node))
                    function_map[function_name] = {
                        "start_byte": func_node.start_byte,
                        "end_byte": func_node.end_byte,
                        "summary": summary
                    }
                elif sub_node.type == "field_identifier":
                    function_name = source_code[sub_node.start_byte:sub_node.end_byte].decode("utf8")
                    class_node =  find_first_father_by_type(sub_node, "class_specifier")
                    if class_node:
                        class_name = find_first_node_by_type(class_node, "type_identifier")
                        if class_name:
                            class_name = source_code[class_name.start_byte:class_name.end_byte].decode("utf8")
                            function_name = f"{class_name}::{function_name}"
                    summary = generate_function_summary(extract_text(func_node))
                    function_map[function_name] = {
                        "start_byte": func_node.start_byte,
                        "end_byte": func_node.end_byte,
                        "summary": summary
                    }
                   
                    
    all_def_funciton_nodes =  find_nodes_by_type(tree.root_node, "preproc_function_def")
    for func_node in all_def_funciton_nodes:
        for sub_node in func_node.children:
            if sub_node.type == "identifier":
                function_name = source_code[sub_node.start_byte:sub_node.end_byte].decode("utf8")
                summary = generate_function_summary(extract_text(func_node))
                function_map[function_name] = {
                        "start_byte": func_node.start_byte,
                        "end_byte": func_node.end_byte,
                        "summary": summary
                    }
                
    return function_map

def summarize_directory(directory: str, module_name=None) -> dict:
    if module_name is None:
        module_name = os.path.basename(os.path.normpath(directory))
    print(f"🔍 Summarizing directory: {directory}")
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
        elif entry.endswith(".c") or entry.endswith(".h") or entry.endswith(".cpp") or entry.endswith(".hpp"):
            print(f"📄 Processing file: {entry}")
            with open(full_path, "rb") as f:
                content = f.read()
            tree = parser.parse(content)

            function_list = get_function_summaries(content, tree)

            if function_list:
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
    print(f"📂 Starting summarization for directory: {prefer_path}")
    results = summarize_directory(prefer_path)

    # Optionally write to JSON for LLM input
    with open(summary_json, "w") as out:
        json.dump(results, out, indent=2)

  