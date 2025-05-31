import json
from botocore.config import Config

import boto3
from botocore.exceptions import BotoCoreError, ClientError
import asyncio

# Create a session to access credentials
session = boto3.Session()
credentials = session.get_credentials()

# Access the credentials
current_credentials = credentials.get_frozen_credentials()

class BedrockClient:
    def __init__(self, region_name, config):
        self.client = boto3.client(
            "bedrock-runtime", region_name=region_name, config=config
        )

    def invoke_model(self, model_id, input_data, content_type="application/json"):
        try:
            response = self.client.invoke_model(
                modelId=model_id, contentType=content_type, body=input_data
            )
            return response["body"].read().decode("utf-8")
        except (BotoCoreError, ClientError) as error:
            print("Error happened calling bedrock")
            return {"error": str(error)}


async def query(prompt):
    config = Config(read_timeout=20)

    model_id = "your_model_id" # Todo: replace with your model ID  
    br_client = BedrockClient("us-west-2", config)
    body = json.dumps(
        {
            "messages": prompt,
            "max_tokens": 1600,
            "anthropic_version": "bedrock-2023-05-31",
            "temperature": 0,
            "top_k": 50,
        }
    )
    
    br_response = br_client.invoke_model(model_id=model_id, input_data=body)
    response = json.loads(br_response)  # Parse if it's a string
    return response["content"][0]["text"]

def askLLM(prompt):
    test_prompt = [
        {"role": "user", "content": prompt},
    ]
    response = asyncio.run(query(test_prompt))
    return response
