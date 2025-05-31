import re
from autogen import ConversableAgent
import autogen
import json
import tree_sitter_c as tsc
from query_repo_recursive import *
import tree_sitter
from tree_sitter import Language, Parser
import global_vars
from query_repo_recursive import *
from typing import List, Tuple, Dict, Set, Optional
from init import *

C_LANGUAGE = Language(tsc.language())
parser = Parser(C_LANGUAGE)

with open("summary.json") as f:  
    code_json = json.load(f)

config_list = [] # Todo: fill in the config_list with your LLM configurations


def clean_text(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        file_content = file.read()

        header_pattern = re.compile(r'RFC (\d+)\s+(.*?)\s+([A-Za-z]+ \d{4})')
        footer_pattern = re.compile(r'^.*\s+\[Page \d+\]$', re.MULTILINE)

        text = header_pattern.sub('', file_content)
        text = footer_pattern.sub('', text)

        text = re.sub(r'\n\s*\n', '\n', text)
        return text.strip()
  
def handle_doc(readfile, writefile):
    # step 1: clean document
    document_text = clean_text(readfile)

    with open(writefile, 'w', encoding='utf-8') as cleaned_file:
        cleaned_file.write(document_text)

    print(f"Cleaned content written to {writefile}")

    # step 2: segmentation to sections
    # Adjusted regex pattern to capture section numbers more reliably, including standalone section titles
    section_header_pattern = re.compile(r'^(\d+(?:\.\d+)*)(\.?)\s+(.*)$', re.MULTILINE)
    
    headers = list(section_header_pattern.finditer(document_text))
    sections = []

    for i, match in enumerate(headers):
        start_index = match.end()
        # Adjust to find the start of the next section considering document structure
        end_index = headers[i + 1].start() if (i + 1) < len(headers) else len(document_text)
        
        # Extract section number and title, and trim content accurately
        section_number = match.group(1)
        section_title = match.group(3).strip()
        section_content = document_text[start_index:end_index].strip()
        sections.append(section_number + section_title + '\n' + section_content)

    return sections

# === similar with -ls, return the files/directories under this level ===
def navigate_one_level(node):
    result = []
    if node is None:
        print(f"Directory not found in codebase.")
        return None
    if "files" in node:
        for name, item in node["files"].items():
            result.append(f"📄 {name}: {item.get('summary', '').strip()}")
            
    return "\n".join(result)

# === Recursive multi-path explorer ===
def explore_multiple_paths(doc_section, current_node, current_path):
    output_paths = []

    view = navigate_one_level(current_node)
    context = f"""You are exploring a code base according to a document section, explore one level at a time.
    
Section: {doc_section}

Here is what you see in the current directory ({current_path}):
{view}
Which entries are most relevant to this section?
Return a comma-separated list of file or folder names enclosed in square brackets, e.g., ["file1.c", "subdir"]. Say TERMINATE if nothing matches.
"""
   
    response = askLLM(context).strip()
    print(f"LLM Response:\n{response}\n")
    if "TERMINATE"in response.upper():
        return []
    # Use regex to extract all quoted names inside the first bracketed list
    bracket_match = re.search(r"\[(.*?)\]", response)
    if not bracket_match:
        print("⚠️ No bracketed list like [\"file1\", \"file2\"] found in the response.")
        return []

    # Extract contents inside the brackets
    inner_content = bracket_match.group(1)

    # Extract quoted strings like "file1.c", 'filter', etc.
    names = re.findall(r'"([^"]+)"|\'([^\']+)\'', inner_content)

    # re.findall returns tuples, so flatten:
    names = [n1 or n2 for n1, n2 in names]
    print(names)
    for name in names:
        if "files" in current_node and name in current_node["files"]:
            child_node = current_node["files"][name]
            new_path = current_path + '/' + name

            if "files" in child_node:
                subpaths = explore_multiple_paths(doc_section, child_node, new_path)
                output_paths.extend(subpaths)
            else:
                output_paths.append({
                    "path": new_path,
                    "node": child_node
                })
        else:
            print(f"⚠️ '{name}' not found under: {current_path}")

    return output_paths

def select_relevant_functions(doc_section, function_text):
    prompt = f"""You are given a section from a technical document and a list of functions.
Each function includes its name and a summary of what it does.

Your task is to identify which functions are most likely to implement the behavior described in the document section.

--- Document Section ---
{doc_section}

--- Functions ---
{function_text}

Return a list of function names enclosed in square brackets, like ["func1", "func2"].
"""
    max_retries = 3
    for _ in range(max_retries):
        try:
            response = askLLM(prompt).strip()

            match = re.search(r"\[(.*?)\]", response)
            if not match:
                print("⚠️ LLM response did not contain a valid list of function names.")
                continue

            inner_content = match.group(1)
            names = re.findall(r'"([^"]+)"|\'([^\']+)\'', inner_content)
            return [n1 or n2 for n1, n2 in names]
        except Exception as e:
            continue

# === Agent configuration ===
def agent_config(function, docsec):
    def get_task_prompt(function, docsec):
        task_prompt = f"Find any inconsistencies between the code and its RFC specification. Only report **explicit violations** of documented mandatory behavior.\n The implementation:\n {function}n RFC document: {docsec}"
        return task_prompt

    def get_analysis_prompt():
        analysis_prompt = f"""You are an intelligent analysis agent responsible for verifying that a given **source code implementation** aligns with the expected behavior described in a **documented specification section**. Your task is to:
                1. **Understand the Specification**
                    - Extract behavior, constraints, and requirements from the document.
                    - Only consider behavior explicitly stated. Do NOT infer or assume anything undocumented.
                2. **Systematically Explore the Codebase**:
                    - Retrieve definition for relevant functions/macros/types that likely implement the specified behavior using 'query_name'. Please only query names existed in the extracted code, don't guess names.
                    - Use `query_caller` to retrieve the **call context** of a known function — i.e., the full bodies of functions that invoke it. This helps reveal how the function is used, under what conditions it is triggered, and how its outputs or effects influence broader behavior.
                    - Recursively explore dependencies and related functions, always **maximize coverage** before determining an inconsistency.  
                    - Check if required constraints (e.g., feasibility, input validity) are enforced at call sites before concluding a check is missing.
                3. **Perform a Rigorous Comparison**:
                    - Report only explicit violations of mandatory behavior.
                    - Do NOT report:
                        - Optional or undefined behavior
                        - Valid implementation choices
                        - Logging vs silent handling differences
                    - Always account for call-site guarantees. If a precondition is satisfied before a call, the callee need not recheck it.
                4. **Suggest Fixes for Identified Issues**:
                    - For valid inconsistencies, propose targeted, minimal changes consistent with the current code style.
                **Key Goal**: Maximize code coverage during exploration **before** concluding an inconsistency. Prioritize thorough traversal of function calls, dependencies, and potential hidden logic paths. Don't generate tests. Only report inconsistencies that are **explicit violations** of the documented specification.
                """
        return analysis_prompt

    def get_critic_prompt():
        critic_prompt = f"""
You are a **critic agent** responsible for reviewing the analysis performed by an **analysis agent**. Your primary objective is to **verify the correctness, completeness, and validity** of the identified inconsistencies between the **source code implementation** and the **documented specification**.

Your task is to:

1. **Verify Exploration**
   - Ensure all relevant code paths were explored via `query_name` and `query_caller`.
   - Confirm deep and recursive context exploration, including call-site logic and constraints.
   
2. **Validate Reported Inconsistencies**
   - Confirm each issue is a clear violation of mandatory behavior from the specification.
   - Ensure no false positives from:
     - Optional/undefined behavior
     - Acceptable implementation strategies
     - Logging vs silent behavior
     - Inferred requirements not present in the spec
   - Ensure feasibility checks or constraints are not wrongly flagged if enforced by callers.

3. **Assess Fixes**
   - Verify that suggested fixes are minimal, correct, complete, and style-consistent.
   - Suggest corrections if the fix is problematic or too intrusive.

4. **Final Judgment:**  
   - If the inconsistency is valid, confirm the analysis agent’s report and its suggested fix.
   - If the inconsistency is **not valid**, provide a reasoned explanation refuting the analysis agent’s conclusion.  
   - If the analysis is **inconclusive**, recommend further investigation paths instead of prematurely labeling it as an inconsistency.  
   - If the analysis result is already correct and no further action is needed, document confirmed inconsistencies and their fixes using **`write_inconsistency()`**, and type 'TERMINATE' to complete the task.**  

**Key Goal:**  
Ensure that only **true, explicitly documented** inconsistencies are documented as **`write_inconsistency()`**.  
"""
        return critic_prompt   

    initializer = ConversableAgent(
        name="Init",
        code_execution_config=False,
    )

    analyze = ConversableAgent(
        name="analyze",
        system_message = get_analysis_prompt(),
        llm_config={"config_list": config_list},
    )

    # The user proxy agent is used for interacting with the analyze agent
    # and executes tool calls.
    executor = ConversableAgent(
        name="Executor",
        llm_config=False,
        human_input_mode="NEVER",
    )

    critic = ConversableAgent(
        name="Critic",
        system_message= get_critic_prompt(),
        llm_config={"config_list": config_list},
    )
    # Register the tool signature with the analyze agent.
    analyze.register_for_llm(name="query_name", description="Query function/macro/type definition")(query_name)
    critic.register_for_llm(name="query_name", description="Query function/macro/type definition")(query_name)

    # Register the tool function with the user proxy agent.
    executor.register_for_execution(name="query_name")(query_name)

    # Register the tool signature with the analyze agent.
    analyze.register_for_llm(name="query_caller", description="Find caller functions")(query_caller)
    critic.register_for_llm(name="query_caller", description="Find caller functions")(query_caller)

    # Register the tool function with the user proxy agent.
    executor.register_for_execution(name="query_caller")(query_caller)
    
    def state_transition(last_speaker, groupchat):
        messages = groupchat.messages
        if last_speaker is initializer:
            return analyze
        
        elif last_speaker is analyze:
            if 'tool_calls' in messages[-1]:
                return executor
            else:
                return critic
        
        elif last_speaker is executor:
            # depends the speaker before the last one
            # if the second last one is analyze, return analyze
            #  if the second last one is critic, return critic
            # return analyze/critic
            if len(messages) < 2:
                 ("Error: unexpected speaker before executor")
            if messages[-2]['name'] == 'analyze':
                return analyze
            elif messages[-2]['name'] == 'Critic':
                return critic
            else:
                print("Error: unexpected speaker before executor")        
        
        elif last_speaker is critic:
            if 'tool_calls' in messages[-1]:
                return executor
            else:
                return analyze
         
    groupchat = autogen.GroupChat(
        agents = [initializer, analyze, executor, critic],
        messages=[],
        max_round=30,
        speaker_selection_method=state_transition
    )

    manager = autogen.GroupChatManager(groupchat=groupchat, llm_config={"config_list": config_list,},is_termination_msg=lambda msg: msg.get("content") is not None and "TERMINATE" in msg["content"],)
    initializer.initiate_chat(manager, message = get_task_prompt(function, docsec))


# === Main function ===
# This function is called to process the RFC document and extract relevant functions
# based on the content of the document.
# It uses the Tree-sitter library to parse the code and identify functions.
# The function also interacts with an LLM to refine the selection of functions.
def diff(protocol, read_file_name, write_file_name, repo_path):
    sections = handle_doc(read_file_name, write_file_name)
    global_vars.project_path = repo_path
    print("Start scanning project...")
    global_vars.project_data = init(global_vars.project_path)
    global_vars.prefer_path = global_vars.project_path 
    print("Finish scanning project...")
    print(query_name("ripng_clear_changed_flag"))
    print("Start analyzing...")
    for section in sections:
        print("$$$$$$$ analysis new section:")
        # multiple file paths
        matches = explore_multiple_paths(section, code_json, current_path=global_vars.prefer_path)
        
        function_text =""
        function_metadata = {}

        for match in matches:
            print("\n✅ Final Match:")
            print("Path:", match["path"])
            node = match["node"]
            path = match["path"]

            # level_view: functions only 
            for func_name, func in node["functions"].items():
                function_text += f"🔧 {func_name}: {func.get('summary', '')}\n"
                function_metadata[func_name] = {
                    "path": path,
                    "start_byte": func.get("start_byte"),
                    "end_byte": func.get("end_byte")
                }

        # Second LLM pass: choose most relevant functions
        selected_funcs = select_relevant_functions(section, function_text)
        if selected_funcs is None:
            print("⚠️ No functions selected.")
            continue
        related_funs = set()
        related_funs.update(selected_funcs)
        print(f"📌 Selected functions for section:")
        code = ""
        for fn in selected_funcs:
            print(f"  🔧 {fn}")
            function_info = function_metadata.get(fn)
            if function_info:
                path = function_info["path"]
                start_byte = function_info["start_byte"]
                end_byte = function_info["end_byte"]
                with open(path, "rb") as f:
                    file_content = f.read()
                    fn_code = file_content[start_byte:end_byte].decode("utf8")
                    code += fn_code.strip() + "\n"
            else:
                print(f"⚠️ Function {fn} not found in metadata.")
        agent_config(code, section)

# Example usage of the diff function      
protocol = 'ripngd'
read_file_name = f"ripngd_{protocol}.txt"
write_file_name = f"ripngd_{protocol}_cleaned.txt"
repo_path = "/path/to/your/repo"  # Replace with your actual repo path
diff(protocol,read_file_name, write_file_name,repo_path)