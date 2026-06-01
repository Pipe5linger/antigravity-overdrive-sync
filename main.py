import sys
import argparse

# Enforce UTF-8 terminal piping on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Import core elements
from core.engine import ULMEngine

# Registry of plugins
PARSERS = {}
INJECTORS = {}

# Lazy load plugins to prevent circular imports and allow modular dependency structures
def register_plugins():
    try:
        from parsers.antigravity import AntigravityParser
        PARSERS["antigravity"] = AntigravityParser
    except Exception as e:
        print(f"[-] Failed to register AntigravityParser: {e}")

    try:
        from injectors.gemini_md import GeminiMdInjector
        INJECTORS["gemini_md"] = GeminiMdInjector
    except Exception as e:
        print(f"[-] Failed to register GeminiMdInjector: {e}")

    try:
        from injectors.ollama_modelfile import OllamaInjector
        INJECTORS["ollama"] = OllamaInjector
    except Exception as e:
        print(f"[-] Failed to register OllamaInjector: {e}")

def main():
    register_plugins()
    
    parser = argparse.ArgumentParser(description="Universal Local Memory (ULM) Agent Pipeline")
    parser.add_argument("--parser", choices=list(PARSERS.keys()), default="antigravity",
                        help="Select the log extraction parser plugin")
    parser.add_argument("--injector", choices=list(INJECTORS.keys()), default="gemini_md",
                        help="Select the memory reinjection injector plugin")
    parser.add_argument("--dry-run", action="store_true",
                        help="Verify payload generation without mutating target prompt files")
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print(f"🚀 INITIALIZING UNIVERSAL LOCAL MEMORY (ULM) PIPELINE")
    print(f"[*] Active Parser: {args.parser.upper()}")
    print(f"[*] Active Injector: {args.injector.upper()}")
    print(f"[*] Mode: {'DRY RUN (MUTATIONS BLOCKED)' if args.dry_run else 'PRODUCTION COMMIT'}")
    print("="*60)
    
    # 1. Initialize core ETL engine and load database state
    engine = ULMEngine()
    current_state = engine.load_existing_state()
    
    # 2. Instantiate and run selected parser
    parser_class = PARSERS[args.parser]
    log_parser = parser_class()
    
    print(f"[*] Running parser Stage 1 (Extract & Transform)...")
    new_logs = log_parser.fetch_new_logs()
    
    # 3. Merge logs into master database state
    updated_state, mutations = engine.merge_and_reconfigure(current_state, new_logs)
    
    if mutations > 0:
        if args.dry_run:
            print(f"[+] Dry run: ETL stage successfully staged {mutations} session modifications.")
        else:
            success = engine.commit_atomic_write(updated_state)
            if success:
                print(f"[+] ETL Stage Complete: Monolithic YAML database updated with {mutations} sessions.")
            else:
                print("[-] Critical Error: Atomic write commit failed.")
                sys.exit(1)
    else:
        print("[*] ETL Stage Complete: No new session modifications detected.")
        
    # 4. Instantiate and run selected injector
    injector_class = INJECTORS[args.injector]
    memory_injector = injector_class()
    
    print(f"[*] Running injector Stage 2 (Load & Reinject)...")
    injection_success = memory_injector.inject(updated_state, dry_run=args.dry_run)
    
    if injection_success:
        print("="*60)
        print("[+] ULM Pipeline Execution completed successfully!")
        print("="*60 + "\n")
    else:
        print("[-] Pipeline halted during Reinjection Stage.")
        sys.exit(1)

if __name__ == "__main__":
    main()
