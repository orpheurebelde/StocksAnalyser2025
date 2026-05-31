import json
from .mistral import MistralProvider
from .groq_provider import GroqProvider

class AnalysisOrchestrator:
    def __init__(self):
        self.primary_provider = MistralProvider()
        try:
            self.secondary_provider = GroqProvider()
            self.secondary_enabled = True
        except Exception as e:
            print(f"Groq provider failed to initialize: {e}")
            self.secondary_enabled = False

    def run_analysis(self, ticker: str, initial_prompt: str) -> dict:
        # Step 1: Run Primary Analysis (Mistral)
        primary_analysis = self.primary_provider.generate(initial_prompt, is_json=False)

        # Base response structure
        final_response = {
            "ticker": ticker,
            "primary_analysis": primary_analysis,
            "secondary_analysis": None,
            "agreement_points": [],
            "disagreement_points": [],
            "additional_risks": [],
            "additional_catalysts": [],
            "assumption_warnings": [],
            "final_rating": "hold",
            "confidence_score": 0.0,
            "final_summary": ""
        }

        if not self.secondary_enabled:
            return final_response

        # Step 2: Run Secondary Analysis (Ollama)
        ollama_prompt = f"""És um analista financeiro de segunda revisão. Vais receber a análise principal previamente gerada pela Mistral sobre a ação {ticker}. 
A tua função não é substituir a análise principal, mas sim complementá-la, validá-la e desafiá-la quando necessário. 
Identifica concordâncias, divergências, riscos em falta, catalisadores em falta e suposições frágeis. 
Responde de forma conservadora, objetiva e APENAS em JSON válido, com a seguinte estrutura exata e em Inglês:

{{
  "agreement_points": ["point 1", "point 2"],
  "disagreement_points": ["point 1"],
  "additional_risks": ["risk 1"],
  "additional_catalysts": ["catalyst 1"],
  "assumption_warnings": ["warning 1"],
  "final_rating": "buy|hold|sell",
  "confidence_score": 0.0,
  "final_summary": "short text"
}}

--- ANÁLISE PRINCIPAL DA MISTRAL ---
{primary_analysis}
"""
        
        try:
            secondary_analysis = self.secondary_provider.generate(ollama_prompt, is_json=True)
            
            # Merge results safely
            final_response["secondary_analysis"] = secondary_analysis
            final_response["agreement_points"] = secondary_analysis.get("agreement_points", [])
            final_response["disagreement_points"] = secondary_analysis.get("disagreement_points", [])
            final_response["additional_risks"] = secondary_analysis.get("additional_risks", [])
            final_response["additional_catalysts"] = secondary_analysis.get("additional_catalysts", [])
            final_response["assumption_warnings"] = secondary_analysis.get("assumption_warnings", [])
            final_response["final_rating"] = secondary_analysis.get("final_rating", "hold").lower()
            final_response["confidence_score"] = float(secondary_analysis.get("confidence_score", 0.0))
            final_response["final_summary"] = secondary_analysis.get("final_summary", "")
        except Exception as e:
            print(f"Secondary analysis failed: {e}")
            final_response["secondary_analysis"] = {"error": str(e)}

        return final_response
