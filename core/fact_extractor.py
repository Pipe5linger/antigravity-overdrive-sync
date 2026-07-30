import json
import requests
import os
import urllib.request
import urllib.error
from typing import List, Tuple

def extract_and_embed_facts(messages: List[dict], llm_model: str = None) -> Tuple[List[str], List[List[float]], List[dict]]:
    documents = []
    embeddings = []
    metadatas = []
    
    if not messages:
        return ["System log recorded"], [[0.0] * 768], [{"category": "Technical", "source": "antigravity_ulm"}]

    compiled_text = ""
    for msg in messages:
        sender = msg.get("sender", "Unknown")
        text = msg.get("text", "")
        if text:
            compiled_text += f"{sender}: {text}\n"

    system_prompt = (
        "You are a strict data extraction system. "
        "Your task is to extract facts from the conversation into these categories: "
        "Personality, Project Progress, Personal/Learning Progress, Daily Life, Technical, Pattern Recognition. "
        "You MUST return ONLY a valid JSON list of objects: [{'fact': 'text', 'category': 'cat'}]. "
        "Do not include any preamble, do not include any markdown, and do not explain your reasoning. "
        "If you cannot find facts, return an empty list: []"
    )

    # Detect provider and key
    api_key = os.getenv("GEMINI_API_KEY")
    kobold_endpoint = "http://localhost:5001"
    
    # Try to check if Kobold is running
    is_kobold_active = False
    try:
        res = requests.get(f"{kobold_endpoint}/api/v1/model", timeout=2)
        if res.status_code == 200:
            is_kobold_active = True
    except Exception:
        pass

    raw_output = "[]"
    
    if is_kobold_active:
        url = f"{kobold_endpoint}/v1/chat/completions"
        payload = {
            "model": "local",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this conversation:\n{compiled_text}"}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            raw_output = response.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[-] FactExtractor: Local KoboldCpp extraction failed: {e}")

    elif api_key:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [{"text": f"{system_prompt}\n\nAnalyze this conversation:\n{compiled_text}"}]
            }],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=90) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                raw_output = res_data['candidates'][0]['content']['parts'][0]['text'].strip()
        except Exception as e:
            print(f"[-] FactExtractor: Cloud Gemini extraction failed: {e}")
            
    else:
        print("[-] FactExtractor: No active LLM provider found (Kobold offline, Gemini Key missing)")

    try:
        data = json.loads(raw_output)
        if isinstance(data, str):
            data = json.loads(data)
    except Exception:
        data = []

    facts = data.get("facts", data) if isinstance(data, dict) else data
    if not isinstance(facts, list) or not facts:
        facts = [{"fact": "System log recorded", "category": "Technical"}]

    for item in facts:
        fact_text = item.get("fact", "System log recorded")
        category = item.get("category", "Technical")
        if fact_text:
            documents.append(fact_text)
            embeddings.append([0.0] * 768)  # 768-dim zero-vector fallback
            metadatas.append({"category": category, "source": "antigravity_ulm"})

    return documents, embeddings, metadatas