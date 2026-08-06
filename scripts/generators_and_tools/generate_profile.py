import os
import re
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

def load_api_key():
    key = os.getenv("GEMINI_API_KEY")
    if key:
        return key
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

def parse_markdown_questions(filepath):
    """
    Parses the template markdown to extract section and question layouts.
    """
    if not filepath.exists():
        print(f"[-] Template file not found at: {filepath}")
        return None

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    sections = re.split(r"\n##\s+", content)
    parsed_data = []
    
    question_regex = re.compile(
        r"(\d+\..*?)\n\s*\[\s*(?:SCALE|CHOICE)[^:]*:\s*(.*?)\s*\]\n\s*\[\s*WHY:\s*(.*?)\s*\]", 
        re.DOTALL
    )
    
    for section in sections:
        lines = section.strip().split("\n")
        if not lines:
            continue
        section_name = lines[0].strip()
        
        matches = question_regex.findall(section)
        if matches:
            section_questions = []
            for q_text, val, why in matches:
                section_questions.append({
                    "question": q_text.strip(),
                    "value": val.strip(),
                    "explanation": why.strip(),
                    "is_answered": bool(val.strip() or why.strip())
                })
            
            parsed_data.append({
                "section": section_name,
                "questions": section_questions
            })
            
    return parsed_data

def merge_pdf_answers(sections, pdf_path):
    """
    Reads the interactive PDF and overrides markdown template values with filled form values.
    """
    if not pdf_path.exists():
        print("[*] No filled PDF found. Proceeding with markdown file answers.")
        return sections, sum(sum(1 for q in s["questions"] if q["is_answered"]) for s in sections)

    print(f"[*] Extracting form field data from PDF: {pdf_path}")
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        fields = reader.get_fields()
        if not fields:
            print("[-] Warning: No form fields detected in PDF.")
            return sections, 0
            
        answered_count = 0
        q_idx = 1
        
        for sec in sections:
            for q in sec["questions"]:
                val_field = fields.get(f"q_{q_idx}_val")
                why_field = fields.get(f"q_{q_idx}_why")
                
                val_val = ""
                why_val = ""
                
                if val_field and "/V" in val_field:
                    val_val = str(val_field["/V"]).strip()
                if why_field and "/V" in why_field:
                    why_val = str(why_field["/V"]).strip()
                    
                if val_val or why_val:
                    q["value"] = val_val
                    q["explanation"] = why_val
                    q["is_answered"] = True
                    answered_count += 1
                else:
                    # Keep markdown values if present, otherwise mark unanswered
                    if not q["value"] and not q["explanation"]:
                        q["is_answered"] = False
                
                q_idx += 1
                
        return sections, answered_count
    except Exception as e:
        print(f"[-] Error merging PDF values: {e}")
        # Return fallback markdown counts
        return sections, sum(sum(1 for q in s["questions"] if q["is_answered"]) for s in sections)

def generate_profile():
    print("[*] Initializing Vespera Profiler Engine...")
    
    api_key = load_api_key()
    if not api_key:
        print("[-] Error: GEMINI_API_KEY not found in environment or .env file.")
        sys.exit(1)
        
    q_path = Path("D:/AI/Antigravity outputs/questionnaire.md")
    pdf_path = Path("D:/AI/Antigravity outputs/questionnaire.pdf")
    out_path = Path("D:/AI/Antigravity outputs/profile.md")
    
    sections = parse_markdown_questions(q_path)
    if not sections:
        print("[-] FAILED: Could not parse questionnaire template.")
        sys.exit(1)
        
    # Merge PDF overrides if the PDF form is filled
    sections, answered_q = merge_pdf_answers(sections, pdf_path)
    total_q = sum(len(s["questions"]) for s in sections)
    
    print(f"[*] Questionnaire Stats: {answered_q}/{total_q} questions answered.")
    
    if answered_q == 0:
        print("[!] WARNING: You haven't answered any questions in either the markdown or PDF form.")
        confirm = input("[?] Proceed with generic profile? (y/n): ").strip().lower()
        if confirm != 'y':
            print("[*] Aborting execution.")
            sys.exit(0)
            
    # Format the data for the prompt
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
