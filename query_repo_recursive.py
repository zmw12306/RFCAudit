import os
import tree_sitter_c as tsc
import tree_sitter_cpp as tscpp
import tree_sitter
from collections import deque
from tree_sitter import Language, Parser
from typing import List
from init import *

if programming_language == "c":
    C_LANGUAGE = Language(tsc.language())
    parser = Parser(C_LANGUAGE)
elif programming_language == "cpp":
    CPP_LANGUAGE = Language(tscpp.language())
    parser = Parser(CPP_LANGUAGE)
    print("Using C++ parser")

project_data = {
    "functions": {},
    "function_calls": {},
    "types": {},
    "defines": {}
}

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

def find_first_father_by_type(
        current_node: tree_sitter.Node, node_type: str
    ) -> tree_sitter.Node:
    """Find the first parent node with the specific type in the parse tree
    :param current_node: the current node in the parse tree
    :param node_type: the type of the parent node
    """
    current_node = current_node.parent
    while current_node:
        if current_node.type == node_type:
            return current_node
        current_node = current_node.parent
    return None

def parse_all_function_info(source_code, tree: tree_sitter.Tree):
    fun_info = {} # Maps function name -> function AST node
    fun_call_info = {} # Maps called function name -> set of caller names
    
    all_function_nodes = find_nodes_by_type(tree.root_node, "function_definition")
    for node in all_function_nodes:
        dec_node = find_first_node_by_type(node, "function_declarator") 
        if not dec_node:     
            continue  
        function_name = None    
        for sub_node in dec_node.children:
            if sub_node.type in {"qualified_identifier", "scoped_identifier", "identifier"}:
                function_name = source_code[sub_node.start_byte:sub_node.end_byte].decode("utf8")
                fun_info[function_name] = node
                break
            elif sub_node.type == "field_identifier":
                function_name = source_code[sub_node.start_byte:sub_node.end_byte].decode("utf8")
                class_node =  find_first_father_by_type(sub_node, "class_specifier")
                if class_node:
                    class_name = find_first_node_by_type(class_node, "type_identifier")
                    if class_name:
                        class_name = source_code[class_name.start_byte:class_name.end_byte].decode("utf8")
                        function_name = f"{class_name}::{function_name}"
                fun_info[function_name] = node
                break
        if function_name:
            call_nodes = find_nodes_by_type(node, "call_expression")
            for call_node in call_nodes:
                call_fun = call_node.child_by_field_name("function")
                called_name = None
                if call_fun.type == "field_identifier":
                    call_indent = call_fun.child_by_field_name("field")
                    if call_indent:
                        called_name = call_indent.text.decode("utf8")
                elif call_fun.type == "identifier":
                    called_name = call_fun.text.decode("utf8")
                    
                if called_name:
                    if called_name not in fun_call_info:
                        fun_call_info[called_name] = set()
                    fun_call_info[called_name].add(function_name)
  
                    
    all_def_funciton_nodes =  find_nodes_by_type(tree.root_node, "preproc_function_def")
    for node in all_def_funciton_nodes:
        for sub_node in node.children:
            if sub_node.type == "identifier":
                function_name = source_code[sub_node.start_byte:sub_node.end_byte].decode("utf8")
                fun_info[function_name] = node
                
    return fun_info, fun_call_info

def parse_all_type_info(source_code, tree: tree_sitter.Tree):
    type_info = {}
    
    all_type_nodes = find_nodes_by_type(tree.root_node, "type_definition")
    all_type_nodes.extend(find_nodes_by_type(tree.root_node, "struct_specifier"))

    for node in all_type_nodes:
        if node.child_by_field_name('body') and node.child_by_field_name('body').type == 'field_declaration_list':
            for sub_node in node.children:
                if sub_node.type == "type_identifier":
                    type_name = source_code[sub_node.start_byte:sub_node.end_byte].decode("utf8")
                    type_info[type_name] = node
        if node.child_by_field_name('type') and node.child_by_field_name('declarator') and node.child_by_field_name('declarator').type == 'type_identifier':  
            sub_node = node.child_by_field_name('declarator')   
            type_name = source_code[sub_node.start_byte:sub_node.end_byte].decode("utf8")
            type_info[type_name] = node                                
    return type_info

def parse_all_define_info(source_code, tree: tree_sitter.Tree):
    define_info = {}
    all_define_nodes = find_nodes_by_type(tree.root_node, "preproc_def")
    for node in all_define_nodes:
        for sub_node in node.children:
            if sub_node.type == "identifier":
                type_name = source_code[sub_node.start_byte:sub_node.end_byte].decode("utf8")
                define_info[type_name] = node
                                
    return define_info

############# Init
def init(project_path):

    for root, dirs, files in os.walk(project_path):
        for file in files:
            if not (file.endswith(".c") or file.endswith(".h")):
                continue

            file_path = os.path.join(root, file)
            with open(file_path, "rb") as c_file:
                c_file_content = c_file.read()
                tree = parser.parse(c_file_content)

            project_data["functions"][file_path], project_data["function_calls"][file_path] = parse_all_function_info(c_file_content, tree)
            project_data["types"][file_path] = parse_all_type_info(c_file_content, tree)
            project_data["defines"][file_path] = parse_all_define_info(c_file_content, tree)

############# Query
def query_function(function_name: str) -> str:
    file_to_fundef = project_data["functions"]

    for file_path, fun_info in file_to_fundef.items():
        if prefer_path in file_path and function_name in fun_info:
            node = fun_info[function_name]
            with open(file_path, "rb") as f:
                source_code = f.read()
            return source_code[node.start_byte:node.end_byte].decode("utf8")
        
    for file_path, fun_info in file_to_fundef.items():
        if prefer_path not in file_path and function_name in fun_info:
            node = fun_info[function_name]
            with open(file_path, "rb") as f:
                source_code = f.read()
            return source_code[node.start_byte:node.end_byte].decode("utf8")            

def query_caller(function_name: str) -> str:
    file_to_fun_call = project_data["function_calls"]

    caller_set = set()
    # First pass: prefer matching files
    for file_path, fun_calls in file_to_fun_call.items():
        if prefer_path in file_path and function_name in fun_calls:
            caller_set.update(fun_calls[function_name])
   
     # Second pass: fallback to other files
    if not caller_set:
        for file_path, fun_calls in file_to_fun_call.items():
            if prefer_path not in file_path and function_name in fun_calls:
                caller_set.update(fun_calls[function_name])
    
     # Now extract source code for all caller functions
    
    code = ""
    for caller in caller_set:
        code += query_function(caller).strip() + "\n"
      
    return code

def query_type(type_name: str) -> str:
    file_to_typedef = project_data["types"]

    for file_path, type_info in file_to_typedef.items():
        if prefer_path in file_path and type_name in type_info:
            node = type_info[type_name]
            with open(file_path, "rb") as f:
                source_code = f.read()
            return source_code[node.start_byte:node.end_byte].decode("utf8")
    
    for file_path, type_info in file_to_typedef.items():
        if prefer_path not in file_path and type_name in type_info:     
            node = type_info[type_name]
            with open(file_path, "rb") as f:
                source_code = f.read()
            return source_code[node.start_byte:node.end_byte].decode("utf8")
            
def query_def(def_name:str) -> str:
    file_to_def = project_data["defines"]

    for file_path, define_info in file_to_def.items():
        if prefer_path in file_path and def_name in define_info:
            node = define_info[def_name]
            with open(file_path, "rb") as f:
                source_code = f.read()
            return source_code[node.start_byte:node.end_byte].decode("utf8")
        
    for file_path, define_info in file_to_def.items():
        if prefer_path not in file_path and def_name in define_info:
            node = define_info[def_name]
            with open(file_path, "rb") as f:
                source_code = f.read()
            return source_code[node.start_byte:node.end_byte].decode("utf8")
        
def query_name(name:str) -> str:
    fun = query_function(name)
    if fun:
        return fun
    if name.startswith("struct "):
        type_name = name[7:]
        type = query_type(type_name)
    else:
        type = query_type(name)
    if type:
        return type
    else:
        return query_def(name)
    