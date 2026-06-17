import json
import requests
import re
import os
import time
from pathlib import Path
from typing import List, Tuple

OLLAMA_GENERATE_ENDPOINT = "http://localhost:11434/api/generate"
OLLAMA_EMBED_ENDPOINT = "http://localhost:11434/api/embeddings"
TARGET_EMBED_MODEL = "nomic-embed-text"
QUOTA_LOCK_FILE = Path(__file__).resolve().parent / "quota_lock.txt"


def _check_quota_lock() -> bool:
    """Check if quota lock file exists and is less than 24 hours old."""
    if not QUOTA_LOCK_FILE.exists():
        return False
    
    try:
        mtime = os.path.getmtime(QUOTA_LOCK_FILE)
        return (time.time() - mtime) < 86400  # 24 hours in seconds
    except Exception:
        return False


def _write_quota_lock() -> None:
    """Create or update the quota lock file with current timestamp."""
    try:
        with open(QUOTA_LOCK_FILE, 'w') as f:
            f.write(str(time.time()))
    except Exception as e:
        print(f"[-] Failed to write quota lock: {e}")


def extract_and_embed_facts(messages: List[dict], llm_model: str) -> Tuple[List[str], List[List[float]], List[dict]]:
    documents = []
    embeddings = []
    metadatas = []
    
    # Pre-filter catch: If adapters dropped everything, return stub immediately
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
    
    payload = {
        "model": llm_model,
        "prompt": f"Analyze this conversation:\n{compiled_text}",
        "system": system_prompt,
        "stream": False,
        "format": "json"
    }

    try:
        response = requests.post(OLLAMA_GENERATE_ENDPOINT, json=payload, timeout=120)
        response.raise_for_status()
        
        raw_output = response.json().get("response", "[]").strip()
        
        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            data = []

        facts = data.get("facts", data) if isinstance(data, dict) else data
        
        # THE STUB STRATEGY: Fallback if LLM found nothing
        if not isinstance(facts, list) or not facts:
            facts = [{"fact": "System log recorded", "category": "Technical"}]
            
        for item in facts:
            fact_text = item.get("fact", "System log recorded")
            category = item.get("category", "Technical")
            
            if fact_text:
                embed_payload = {"model": TARGET_EMBED_MODEL, "prompt": fact_text}
                try:
                    embed_response = requests.post(OLLAMA_EMBED_ENDPOINT, json=embed_payload, timeout=30)
                    embed_response.raise_for_status()
                    vector = embed_response.json().get("embedding")
                except Exception as e:
                    print(f"[-] Embedding API Failed: {e}")
                    vector = [0.0] * 768 # Fallback zero-vector to prevent ChromaDB crash
                
                if vector:
                    documents.append(fact_text)
                    embeddings.append(vector)
                    metadatas.append({"category": category, "source": "antigravity_ulm"})

        return documents, embeddings, metadatas

    except Exception as e:
        print(f"[-] Fact Extraction Failed: {e}")
        # THE STUB STRATEGY: Fallback on critical LLM timeout/failure
        return ["System log recorded"], [[0.0] * 768], [{"category": "Technical", "source": "antigravity_ulm"}]
import json
import requests
import re
from typing import List, Tuple

OLLAMA_GENERATE_ENDPOINT = "http://localhost:11434/api/generate"
OLLAMA_EMBED_ENDPOINT = "http://localhost:11434/api/embeddings"
TARGET_EMBED_MODEL = "nomic-embed-text"

def extract_and_embed_facts(messages: List[dict], llm_model: str) -> Tuple[List[str], List[List[float]], List[dict]]:
    documents = []
    embeddings = []
    metadatas = []
    
    # Pre-filter catch: If adapters dropped everything, return stub immediately
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
    
    payload = {
        "model": llm_model,
        "prompt": f"Analyze this conversation:\n{compiled_text}",
        "system": system_prompt,
        "stream": False,
        "format": "json"
    }

    try:
        response = requests.post(OLLAMA_GENERATE_ENDPOINT, json=payload, timeout=120)
        response.raise_for_status()
        
        raw_output = response.json().get("response", "[]").strip()
        
        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            data = []

        facts = data.get("facts", data) if isinstance(data, dict) else data
        
        # THE STUB STRATEGY: Fallback if LLM found nothing
        if not isinstance(facts, list) or not facts:
            facts = [{"fact": "System log recorded", "category": "Technical"}]
            
        for item in facts:
            fact_text = item.get("fact", "System log recorded")
            category = item.get("category", "Technical")
            
            if fact_text:
                embed_payload = {"model": TARGET_EMBED_MODEL, "prompt": fact_text}
                try:
                    embed_response = requests.post(OLLAMA_EMBED_ENDPOINT, json=embed_payload, timeout=30)
                    embed_response.raise_for_status()
                    vector = embed_response.json().get("embedding")
                except Exception as e:
                    print(f"[-] Embedding API Failed: {e}")
                    vector = [0.0] * 768 # Fallback zero-vector to prevent ChromaDB crash
                
                if vector:
                    documents.append(fact_text)
                    embeddings.append(vector)
                    metadatas.append({"category": category, "source": "antigravity_ulm"})

        return documents, embeddings, metadatas

    except Exception as e:
        print(f"[-] Fact Extraction Failed: {e}")
        # THE STUB STRATEGY: Fallback on critical LLM timeout/failure
        return ["System log recorded"], [[0.0] * 768], [{"category": "Technical", "source": "antigravity_ulm"}]