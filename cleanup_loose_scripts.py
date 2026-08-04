import os
import shutil
from pathlib import Path

# Root folder to clean
PROJECT_ROOT = Path(__file__).parent.resolve()

# Safety First: Set to False when you're ready to actually move files
DRY_RUN = True

# Files that MUST stay in the root directory
CORE_ROOT_FILES = {
    # Main Application Entry Points
    "main.py", "web_server.py", "sync_engine.py", 
    "benchmark_evaluator.py", "benchmark_fact_extractor.py",
    # Script itself & Core Configs
    "cleanup_loose_scripts.py", "config.json", "requirements.txt",
    "Modelfile.txt", "persona_baseline.yaml", "persona_prompt.md",
    "README.md", "BENCHMARK.md", "checkpoint.md"
}

# Mapping of subdirectories to file patterns/names
TARGET_CATEGORIES = {
    "scripts/db_utils": [
        "check_db.py", "check_db_state.py", "check_db_wal.py", "check_persona_db.py",
        "check_state.py", "inspect_db.py", "inspect_conversation_db.py",
        "inspect_developer_columns.py", "inspect_persona.py", "find_dev_table.py",
        "find_developer_table.py", "upgrade_db.py"
    ],
    "scripts/sync_vault": [
        "consolidate_developer_vault.py", "consolidate_persona_vault.py",
        "dedupe_vault.py", "fast_dedupe_vault.py", "deep_sweep_conversations_db.py",
        "deep_sweep_persona.py", "flush_and_resync.py", "retroactive_persona_sync.py",
        "backfill_vespera_persona.py"
    ],
    "scripts/generators_and_tools": [
        "compile_modelfile.py", "compile_persona.py", "generate_pdf_questionnaire.py",
        "generate_profile.py", "seed_vespera_lore.py", "inject_trait.py",
        "normalize_legacy_traits.py", "migrate_profiles.py", "test_injectors.py",
        "watch_profile.py"
    ]
}

def organize_workspace():
    print("=" * 60)
    print(f" WORKSPACE SCRIPTS CLEANUP {'(DRY RUN MODE)' if DRY_RUN else '(LIVE EXECUTION)'}")
    print("=" * 60)
    
    moved_count = 0

    for category_dir, filenames in TARGET_CATEGORIES.items():
        target_path = PROJECT_ROOT / category_dir
        
        for fname in filenames:
            source_file = PROJECT_ROOT / fname
            
            # Ensure we don't accidentally move core files
            if fname in CORE_ROOT_FILES:
                continue
                
            if source_file.exists() and source_file.is_file():
                destination = target_path / fname
                print(f"[MOVE] {fname}  -->  {category_dir}/")
                
                if not DRY_RUN:
                    target_path.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(source_file), str(destination))
                
                moved_count += 1

    print("-" * 60)
    print(f"Total files identified for organization: {moved_count}")
    
    if DRY_RUN:
        print("\n[!] This was a DRY RUN. No files were actually moved.")
        print("    Edit 'DRY_RUN = False' in cleanup_loose_scripts.py to execute.")
    else:
        print("\n[SUCCESS] Workspace organized cleanly!")

if __name__ == "__main__":
    organize_workspace()