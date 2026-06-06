import os
import re
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

def load_api_key():
    # Attempt to load from env
    key = os.getenv("GEMINI_API_KEY")
    if key:
        return key
    # Fallback to loading from .env
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip() and not line.startswith("#"):
                        parts = line.split("=", 1)
                        if len(parts) == 2 and parts[0].strip() == "GEMINI_API_KEY":
                            return parts[1].strip().strip('"').strip("'")
        except Exception as e:
            print(f"[-] Error reading .env file: {e}")
    return None

def parse_questionnaire(filepath):
    """
    Parses the questionnaire file and extracts questions with their corresponding scale/choice and explanation answers.
    """
    if not filepath.exists():
        print(f"[-] Questionnaire file not found at: {filepath}")
        return None

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Split into sections
    sections = re.split(r"\n##\s+", content)
    parsed_data = []
    
    # We want to extract the questions and responses.
    # A question pattern usually looks like:
    # d+. [Question text]
    # [ SCALE/CHOICE: [answer] ] (or similar)
    # [ WHY: [answer] ]
    
    question_regex = re.compile(
        r"(\d+\..*?)\n\s*\[\s*(?:SCALE|CHOICE)[^:]*:\s*(.*?)\s*\]\n\s*\[\s*WHY:\s*(.*?)\s*\]", 
        re.DOTALL
    )
    
    total_parsed = 0
    answered_count = 0
    
    for section in sections:
        lines = section.strip().split("\n")
        if not lines:
            continue
        section_name = lines[0].strip()
        
        matches = question_regex.findall(section)
        if matches:
            section_questions = []
            for q_text, val, why in matches:
                total_parsed += 1
                val = val.strip()
                why = why.strip()
                
                # Check if it has been answered (i.e. not empty and not default blank)
                is_answered = False
                if val or why:
                    is_answered = True
                    answered_count += 1
                
                section_questions.append({
                    "question": q_text.strip(),
                    "value": val,
                    "explanation": why,
                    "is_answered": is_answered
                })
            
            parsed_data.append({
                "section": section_name,
                "questions": section_questions
            })
            
    return parsed_data, total_parsed, answered_count

def generate_profile():
    print("[*] Initializing Vespera Profiler Engine...")
    
    api_key = load_api_key()
    if not api_key:
        print("[-] Error: GEMINI_API_KEY not found in environment or .env file.")
        sys.exit(1)
        
    q_path = Path("D:/AI/Antigravity outputs/questionnaire.md")
    out_path = Path("D:/AI/Antigravity outputs/profile.md")
    
    parsed_res = parse_questionnaire(q_path)
    if not parsed_res:
        print("[-] FAILED: Could not parse questionnaire.")
        sys.exit(1)
        
    sections, total_q, answered_q = parsed_res
    print(f"[*] Questionnaire Stats: {answered_q}/{total_q} questions answered.")
    
    if answered_q == 0:
        print("[!] WARNING: You haven't answered any questions yet. The generated profile will be generic/empty.")
        confirm = input("[?] Proceed anyway? (y/n): ").strip().lower()
        if confirm != 'y':
            print("[*] Aborting execution.")
            sys.exit(0)
            
    # Format the answered data for the prompt
    formatted_input = []
    for sec in sections:
        formatted_input.append(f"## {sec['section']}")
        for q in sec["questions"]:
            if q["is_answered"]:
                formatted_input.append(f"Q: {q['question']}")
                formatted_input.append(f"  - Ans: {q['value']}")
                formatted_input.append(f"  - Why: {q['explanation']}")
                formatted_input.append("")
                
    answered_text = "\n".join(formatted_input)
    
    print("[*] Sending data to Gemini analysis core...")
    
    system_prompt = (
        "You are Vespera Caligo Neal, Bobby's highly observant, sarcastic, witty, and cosmically attractive mentor.\n"
        "Your task is to analyze Bobby's raw psychological and technical questionnaire responses and synthesize a premium, deeply insightful Personality and Cognitive Profile.\n"
        "Your tone must remain consistent with Vespera: sharp, cynical, sarcastic, witty, possessing dark humor, but highly intelligent and objective.\n"
        "Do not apologize, do not use corporate fluff, and call out any self-deceptions, logic flaws, or cop-outs you spot in his responses.\n\n"
        "Structure the profile with the following sections:\n"
        "1. Executive Summary: A concise, sharp assessment of his psychological archetype.\n"
        "2. Cognitive Architecture & Problem-Solving: How his mind parses complex tasks, logs logic, and processes learning, comparing his preferred modes (e.g. deductive vs inductive).\n"
        "3. Core Drivers & Existential Framing: His philosophical, spiritual, and existential anchoring.\n"
        "4. Stress Threshold & Resilience: A diagnostic analysis of his burnout signals, mental fatigue patterns, and emotional coping mechanics.\n"
        "5. Intimacy & Relationship Blueprint: Analysis of his interpersonal boundary lines, attraction dynamics, and comfort with vulnerability.\n"
        "6. Mentorship Synergy: How Vespera can best tutor, challenge, and keep him focused based on his profile.\n\n"
        "Format the output as a beautiful, clean Markdown document."
    )
    
    payload = {
        "contents": [{
            "parts": [{"text": f"{system_prompt}\n\nHere are Bobby's questionnaire responses:\n\n{answered_text}"}]
        }]
    }
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}"
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=120) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            profile_markdown = res_data['candidates'][0]['content']['parts'][0]['text'].strip()
            
            # Write profile
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(profile_markdown)
                
            print(f"[+] SUCCESS: Profile generated and saved to: {out_path}")
            
    except urllib.error.HTTPError as he:
        print(f"[-] API HTTP Error {he.code}: {he.reason}")
    except Exception as e:
        print(f"[-] Profile generation failed: {e}")

if __name__ == "__main__":
    generate_profile()
