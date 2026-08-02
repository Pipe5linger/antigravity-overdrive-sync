import json
import requests
import re

class PersonaEvaluator:
    def __init__(self, model_name="qwen2.5-coder-vespera:latest", ollama_url="http://localhost:11434/api/generate"):
        self.model_name = model_name
        self.ollama_url = ollama_url
        # Clean, direct extraction prompt without negative filtering overload
        self.system_prompt = """You are a persona and relationship trait extractor.
Analyze the provided chat text and extract facts about Vespera (the AI) or her relationship with Bobby.

Look for:
- Physical descriptions or appearance traits.
- Personality traits, humor, tone, or attitudes.
- Backstory, lore, or secrets.
- Relationship dynamics with Bobby (flirting, nicknames, affection, possessiveness).

Rules:
- Output ONLY a valid JSON array of objects.
- Write full, descriptive sentences for each trait.
- If no persona traits are found, return [].

Format:
[
  {"category": "physical|lore|personality|relationship", "trait": "Full descriptive sentence.", "confidence": 0.9}
]"""

    def evaluate_chunk(self, chat_text):
        prompt = f"Extract all persona traits and relationship facts from this text:\n\n{chat_text}"
        
        payload = {
            "model": self.model_name,
            "system": self.system_prompt,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }

        try:
            response = requests.post(self.ollama_url, json=payload, timeout=60)
            response.raise_for_status()
            result_text = response.json().get("response", "")
            
            clean_json = re.sub(r'```json|```', '', result_text).strip()
            parsed_data = json.loads(clean_json)
            
            if isinstance(parsed_data, dict):
                if not parsed_data:
                    return []
                return [parsed_data]
            return parsed_data
            
        except Exception as e:
            print(f"\n[!] Persona extraction error: {e}")
            return []