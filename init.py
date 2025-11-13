from openai import OpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)
import yaml
import sys

with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)


model_name = config["llm_config"]["model_name"]
OPENAI_API_KEY = config["llm_config"]["OPENAI_API_KEY"]
temperature = config["llm_config"]["temperature"]
config_list = [
    {
        "model": model_name,
        "api_key": OPENAI_API_KEY,
        "temperature": temperature
    }
]
retry_min = config["llm_config"]["retry_min"]
retry_max = config["llm_config"]["retry_max"]
max_retries = config["llm_config"]["max_retries"]

@retry(wait=wait_random_exponential(min=retry_min, max=retry_max), stop=stop_after_attempt(max_retries))
def query(prompt):
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=model_name,
        temperature=temperature,
        messages=prompt,
    )
    return response.choices[0].message.content
   

def askLLM(prompt):
    test_prompt = [
        {"role": "user", "content": prompt},
    ]
    response = query(test_prompt)
    return response

# Project Configuration
protocol = config["project"]["protocol"]
log_file = config["project"]["log_file"]
project_path = config["project"]["project_path"]
prefer_path = config["project"]["prefer_path"]
read_file_name = config["project"]["rfc_input"]
write_file_name = config["project"]["rfc_cleaned_output"]
summary_json = config["project"]["summary_json"]
JSON_FILE = f"inconsistencies_{protocol}.json"

if config["project"].get("log_or_not", False):
    # Redirect stdout and stderr to log file
    sys.stdout = open(log_file, 'w', encoding='utf-8')
    sys.stderr = sys.stdout

programming_language = config["project"].get("programming_language", "c")