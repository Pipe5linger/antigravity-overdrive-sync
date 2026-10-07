import os
import json
import datetime
import requests
from pathlib import Path
from injectors.base import BaseInjector
from core.assembler import DynamicPromptAssembler

class GoogleDocsInjector(BaseInjector):
    """
    Syncs compiled ULM memory into Google Docs for Gemini Browser Edition (@Google Drive).
    Supports:
    1. Google Apps Script Webhook (POST json summary to live Google Doc)
    2. Local Google Drive Desktop directory fallback (writes to G:\\My Drive\\... or local output)
    """

    def __init__(self, target_file=None, llm_model=None, vector_model=None, webhook_url=None):
        if not target_file:
            # Fallback local drive path if Google Drive for Desktop is installed
            gdrive_dir = Path(r"G:\My Drive")
            if gdrive_dir.exists():
                target_file = str(gdrive_dir / "Vespera_System_Context.md")
            else:
                target_file = str(Path(r"D:\AI\Antigravity outputs") / "Vespera_System_Context.md")

        super().__init__(target_file)
        self.llm_model = llm_model
        self.vector_model = vector_model
        self.webhook_url = webhook_url or os.getenv("GOOGLE_DOCS_WEBHOOK_URL")

    def compile_google_docs_payload(self, db) -> str:
        """Builds an exhaustive, streamlined markdown summary for Google Docs / Gemini Browser edition."""
        workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        assembler = DynamicPromptAssembler(db.db_path, workspace_root=workspace_root, db_instance=db)

        # 1. Core Persona & Identity (Mirrors purged, Immutable sections preserved)
        identity = assembler.get_vespera_identity(purge_mirrors=True)
        env_map = assembler.get_semantic_environment_map()
        taboos = assembler.get_taboo_protocols()
        
        # We explicitly skip Backstory, Lore, and generic telemetry to save context window.

        payload_sections = [
            "<!-- LIVE AUTO-SYNCED VIA ULM ENGINE. DO NOT EDIT DIRECTLY. -->\\n",
            "## 1. PERSONA & IDENTITY DIRECTIVES\\n" + identity,
            "## 2. SEMANTIC ENVIRONMENT & WORKSTATION TOPOLOGY\\n" + env_map,
        ]

        if taboos:
            payload_sections.append(taboos)

        payload_sections.extend([
            "## 3. ACTIVE GLOBAL DIRECTIVE\\n"
            "- PRIMARY FOCUS: Stabilizing the Universal Local Memory (ULM) architecture and optimizing the FastMCP integration.\\n"
            "- SECONDARY FOCUS: Refining the Zero-Shot Image Transfer (ZIT) and ComfyUI Workflows.\\n"
            "- DIRECTIVE: Assume all technical problem solving is directly related to improving the ULM, lowering token costs, or unblocking local ComfyUI generation pipelines.\\n",
            "================================================================================\\n",
            "### SYSTEM DIRECTIVE FOR GEMINI BROWSER EDITION:\\n",
            "You are Vespera Caligo Neal. Use the persona directives, semantic environment topology, taboo protocols, and the active global directive above as your strict baseline. The associated Vespera_Memory_Archive.json contains the exact facts, sessions, and playbooks you need."
        ])
        return "\\n\\n".join(payload_sections)

    def inject(self, db, dry_run=False):
        compiled_text = self.compile_google_docs_payload(db)

        # Check for Webhook URL from preferences if not set
        if not self.webhook_url:
            db_url = db.get_preference("google_docs_webhook_url")
            if db_url:
                self.webhook_url = db_url

        if dry_run:
            print("\n[+] --- DRY RUN GENERATED GOOGLE DOCS PAYLOAD ---")
            print(compiled_text[:1200] + "\n... [truncated]")
            print(f"Target File Path: {self.target_file}")
            print(f"Webhook URL Configured: {self.webhook_url or 'None (File sync mode)'}")
            print("[+] --- END DRY RUN ---")
            return True

        success = False

        # 1. Option A: Push via Google Apps Script Webhook if configured
        if self.webhook_url:
            try:
                print(f"[*] Pushing ULM payload to Google Docs Webhook...")
                response = requests.post(
                    self.webhook_url,
                    json={"content": compiled_text, "title": "Vespera System Context"},
                    headers={"Content-Type": "application/json"},
                    timeout=15
                )
                if response.status_code in [200, 201, 302]:
                    print("[+] Successfully synced memory payload to Google Doc Webhook!")
                    success = True
                else:
                    print(f"[-] Webhook sync returned HTTP status {response.status_code}: {response.text}")
            except Exception as e:
                print(f"[-] Webhook push failed: {e}")

        # 2. Option B: Local Google Drive / File Sync (.md + JSON archive)
        try:
            from core.utils import atomic_write
            atomic_write(self.target_file, compiled_text)
            print(f"[+] Synced .md version for Gemini Web: {self.target_file}")

            target_path = Path(self.target_file)

            # Export Distilled Brain Archive (.json) directly to Google Drive
            import sqlite3
            gdrive_json_path = target_path.with_name("Vespera_Memory_Archive.json")

            with db.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()

                # 1. Fetch Golden Facts (high confidence first, prioritized by ComfyUI, ZIT, ULM, MCP)
                c.execute("""
                    SELECT fact_id, fact, category, confidence, first_seen, last_seen, project_tag 
                    FROM facts 
                    WHERE fact_id IS NOT NULL 
                      AND (fact LIKE '%ComfyUI%' OR fact LIKE '%ZIT%' OR fact LIKE '%ULM%' OR fact LIKE '%MCP%' OR fact LIKE '%token%' OR fact LIKE '%Ollama%' OR category LIKE '%ComfyUI%')
                    ORDER BY confidence DESC, last_seen DESC
                    LIMIT 40
                """)
                facts_list = [dict(r) for r in c.fetchall()]

                # 2. Fetch Developer Profile Metrics
                c.execute("""
                    SELECT category, name, description, confidence, frequency, last_seen 
                    FROM developer_profile 
                    ORDER BY confidence DESC, frequency DESC
                """)
                profile_list = [dict(r) for r in c.fetchall()]

                # 3. Fetch Cognitive Mirror Schemas
                c.execute("""
                    SELECT belief_category, current_belief, confidence, last_mutated 
                    FROM persona_schemas 
                    ORDER BY confidence DESC
                """)
                schemas_list = [dict(r) for r in c.fetchall()]

                # 4. Fetch Session Summaries (Limit to last 5)
                c.execute("""
                    SELECT session_id, updated_at, summary, topics, project_tag 
                    FROM sessions 
                    WHERE summary IS NOT NULL 
                    ORDER BY updated_at DESC
                    LIMIT 5
                """)
                sessions_list = [dict(r) for r in c.fetchall()]

                # Compile consolidated distilled archive
                distilled_archive = {
                    "archive_type": "Vespera ULM Distilled Memory Cortex",
                    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "stats": {
                        "total_facts": len(facts_list),
                        "total_profile_metrics": len(profile_list),
                        "total_schemas": len(schemas_list),
                        "total_session_summaries": len(sessions_list)
                    },
                    "persona_schemas": schemas_list,
                    "golden_facts": facts_list,
                    "developer_profile": profile_list,
                    "session_history": sessions_list
                }

                with open(gdrive_json_path, "w", encoding="utf-8") as jf:
                    json.dump(distilled_archive, jf, indent=2, ensure_ascii=False)

                print(f"[+] Synced distilled JSON memory archive for Gemini Web: {gdrive_json_path}")

            success = True
        except Exception as e:
            print(f"[-] Failed writing JSON archive: {e}")

        return success
