import json
import os
from pathlib import Path

def approximate_tokens(text):
    """Roughly approximate tokens: 1 word ~ 1.3 tokens"""
    if not text:
        return 0
    return int(len(text.split()) * 1.3)

def run_live_audit(transcript_path):
    print("==================================================")
    print(" LIVE TOKEN AUDIT: CURRENT ANTIGRAVITY SESSION")
    print("==================================================\n")
    
    if not os.path.exists(transcript_path):
        print(f"Transcript not found at {transcript_path}")
        return

    raw_tokens_per_turn = []
    
    with open(transcript_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                step = json.loads(line)
                content = step.get('content', '')
                if content:
                    tokens = approximate_tokens(content)
                    raw_tokens_per_turn.append(tokens)
            except json.JSONDecodeError:
                continue

    total_turns = len(raw_tokens_per_turn)
    
    # 1. Standard API Calculation (O(N^2) Bloat)
    # A standard chat sends the entire history every single turn.
    standard_cumulative = 0
    history_size = 0
    for tokens in raw_tokens_per_turn:
        history_size += tokens
        standard_cumulative += history_size
        
    # 2. ULM Bounded Calculation 
    # ULM sends a fixed system prompt + sliding window (e.g., last 3 turns)
    ulm_cumulative = 0
    ulm_base_system_tokens = 1500 # Approx size of rules, playbooks, taboos
    
    for i in range(total_turns):
        # Sliding window of last 3 turns + base rules
        window_start = max(0, i - 3)
        window_tokens = sum(raw_tokens_per_turn[window_start:i+1])
        ulm_cumulative += (ulm_base_system_tokens + window_tokens)

    print(f"Total conversational turns analyzed: {total_turns}")
    print(f"Raw isolated tokens generated: {sum(raw_tokens_per_turn):,}\n")
    
    print("--- SCENARIO A: STANDARD CLOUD AI (Unmanaged Context) ---")
    print("Behavior: Re-reads the entire chat history on every single turn.")
    print(f"Cumulative API Tokens Billed: {standard_cumulative:,}\n")
    
    print("--- SCENARIO B: ULM ARCHITECTURE (Bounded Context) ---")
    print("Behavior: Injects fixed system rules + recent sliding window.")
    print(f"Cumulative API Tokens Billed: {ulm_cumulative:,}\n")
    
    if standard_cumulative > 0:
        savings = ((standard_cumulative - ulm_cumulative) / standard_cumulative) * 100
        print(f"-> LIVE TOKEN SAVINGS: {savings:.2f}%\n")
    
    print("==================================================")

if __name__ == "__main__":
    # Pointing exactly to your active session transcript
    transcript_file = r"C:\Users\boben\.gemini\antigravity\brain\206635a9-dc5b-4e12-a078-4e4a895eba9b\.system_generated\logs\transcript.jsonl"
    run_live_audit(transcript_file)
