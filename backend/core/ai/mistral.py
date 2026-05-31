import os
import requests
import json
from .base import AIProvider

class MistralProvider(AIProvider):
    def __init__(self, model_name: str = "mistral-small-latest", api_key: str = None):
        self.model_name = model_name
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY not configured in environment and not provided.")
            
    def generate(self, prompt: str, is_json: bool = False):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 8000
        }
        
        if is_json:
            data["response_format"] = {"type": "json_object"}
            
        response = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        
        content = result["choices"][0]["message"]["content"].strip()
        
        if is_json:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                raise ValueError(f"Failed to parse JSON from Mistral response: {content}")
        return content
