import os
import requests
import json
from .base import AIProvider

class OllamaProvider(AIProvider):
    def __init__(self, model_name: str = "llama3"):
        self.model_name = os.getenv("OLLAMA_MODEL", model_name)
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.api_key = os.getenv("OLLAMA_API_KEY", "")
        
    def generate(self, prompt: str, is_json: bool = False):
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            
        data = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2  # Keep it conservative for analysis
            }
        }
        
        if is_json:
            data["format"] = "json"
            
        # Provide a reasonable timeout for large analyses
        response = requests.post(f"{self.base_url}/api/generate", headers=headers, json=data, timeout=120)
        response.raise_for_status()
        result = response.json()
        
        content = result.get("response", "").strip()
        
        if is_json:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                raise ValueError(f"Failed to parse JSON from Ollama response: {content}")
                
        return content
