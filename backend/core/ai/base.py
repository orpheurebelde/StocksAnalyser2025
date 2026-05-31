from abc import ABC, abstractmethod
from typing import Dict, Any, Union

class AIProvider(ABC):
    """
    Abstract base class for all AI Providers (Mistral, Ollama, etc.)
    """
    
    @abstractmethod
    def generate(self, prompt: str, is_json: bool = False) -> Union[str, Dict[str, Any]]:
        """
        Generates text or JSON based on the provided prompt.
        
        Args:
            prompt (str): The prompt to send to the LLM.
            is_json (bool): If True, requests JSON output and parses it.
            
        Returns:
            Union[str, Dict[str, Any]]: The text response or parsed JSON.
        """
        pass
