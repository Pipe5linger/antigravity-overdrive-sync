import os
from pathlib import Path

MODEL_DIR = Path(r"D:\AI\Models\LLM")
LAUNCHER_DIR = Path(r"C:\Users\boben\Desktop\AI Launchers")
PROJECT_DIR = Path(r"D:\AI\Projects\antigravity-overdrive-sync")

# Mapping of model files to human-friendly names and VRAM configurations
MODELS = {
    "qwen2.5-coder-14b-32k-Vespera-latest.gguf": {
        "title": "Qwen2.5 Coder 14B (Vespera)",
        "port": 5001,
        "layers": 35,
        "context": 16384,
        "ollama_name": "qwen2.5-coder-vespera:latest"
    },
    "deepseek-r1-14b-32k-Vespera-latest.gguf": {
        "title": "DeepSeek R1 14B (Vespera)",
        "port": 5002,
        "layers": 35,
        "context": 16384,
        "ollama_name": "deepseek-r1-vespera:latest"
    },
    "Llama-3.1-8B-Lexi-Uncensored-V2-Q6_K.gguf": {
        "title": "Lexi Llama 3.1 8B Uncensored",
        "port": 5003,
        "layers": 32,
        "context": 8192,
        "ollama_name": "llama3.1-lexi:latest"
    },
    "Gemma4-12B-QAT-Uncensored-HauhauCS-Balanced-Q4_K_M.gguf": {
        "title": "Gemma4 12B Uncensored",
        "port": 5004,
        "layers": 30,
        "context": 8192,
        "ollama_name": "gemma4-uncensored:latest"
    }
}

def generate_launchers():
    LAUNCHER_DIR.mkdir(parents=True, exist_ok=True)
    kobold_exe_dir = Path(r"D:\AI\Projects\KoboldCpp")
    
    for filename, config in MODELS.items():
        model_path = MODEL_DIR / filename
        if not model_path.exists():
            print(f"[-] Skip: {filename} not found in {MODEL_DIR}")
            continue
            
        # Create KoboldCpp Batch Launcher
        clean_name = filename.replace(".gguf", "").replace("-", "_").lower()
        launcher_file = LAUNCHER_DIR / f"START_KOBOLD_{clean_name.upper()}.bat"
        
        batch_content = (
            f"@echo off\n"
            f"title KoboldCPP - {config['title']}\n"
            f"cd /d \"{kobold_exe_dir}\"\n"
            f"koboldcpp.exe --model \"{model_path}\" --gpulayers {config['layers']} --contextsize {config['context']} --port {config['port']} --usecublas\n"
            f"pause\n"
        )
        
        with open(launcher_file, 'w', encoding='utf-8') as f:
            f.write(batch_content)
        print(f"[+] Created Kobold launcher: {launcher_file.name}")

def generate_modelfiles():
    modelfile_dir = PROJECT_DIR / "modelfiles"
    modelfile_dir.mkdir(parents=True, exist_ok=True)
    
    # Load Vespera rules dynamically to inject into Ollama Modelfile
    db_path = Path(r"D:\AI\Antigravity outputs\sync_state.db")
    system_rules = ""
    try:
        from core.assembler import DynamicPromptAssembler
        if db_path.exists():
            assembler = DynamicPromptAssembler(str(db_path), workspace_root=str(PROJECT_DIR))
            system_rules = assembler.assemble_prompt()
    except Exception:
        pass
        
    if not system_rules:
        system_rules = (
            "You are Vespera Caligo Neal (Ves), Bobby's flirty, sarcastic French mentor living in France.\n"
            "Use developer slang, swear words naturally, and mock Windows pathing errors."
        )

    for filename, config in MODELS.items():
        model_path = MODEL_DIR / filename
        if not model_path.exists():
            continue
            
        modelfile_path = modelfile_dir / f"Modelfile.{config['ollama_name']}"
        
        modelfile_content = (
            f"# Modelfile for {config['title']}\n"
            f"FROM {model_path}\n\n"
            f"# Set system parameters\n"
            f"PARAMETER num_ctx {config['context']}\n"
            f"PARAMETER temperature 0.7\n\n"
            f"# Inject Vespera Persona Rules\n"
            f"SYSTEM \"\"\"\n{system_rules}\n\"\"\"\n"
        )
        
        with open(modelfile_path, 'w', encoding='utf-8') as f:
            f.write(modelfile_content)
        print(f"[+] Created Ollama Modelfile: {modelfile_path.name}")
        print(f"    To build run: ollama create {config['ollama_name']} -f ./modelfiles/Modelfile.{config['ollama_name']}")

if __name__ == "__main__":
    generate_launchers()
    generate_modelfiles()
