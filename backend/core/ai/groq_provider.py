import os
import requests
import json
from .base import AIProvider

class GroqProvider(AIProvider):
    def __init__(self, model_name: str = "llama3-70b-8192"):
        self.model_name = os.getenv("GROQ_MODEL", model_name)
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not configured in environment")
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    def generate(self, prompt: str, is_json: bool = False) -> dict | str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if is_json:
            messages.append({
                "role": "system",
                "content": "You are an AI assistant that only outputs valid JSON."
            })
            
        messages.append({
            "role": "user",
            "content": prompt
        })

        data = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.5
        }
        
        if is_json:
            data["response_format"] = {"type": "json_object"}

        response = requests.post(self.base_url, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        content = result["choices"][0]["message"]["content"].strip()
        
        if is_json:
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse JSON from Groq: {e}\nContent: {content}")
        return content
