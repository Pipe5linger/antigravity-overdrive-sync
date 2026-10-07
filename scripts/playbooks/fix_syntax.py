import re
with open('injectors/google_docs.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace all literal newlines inside string quotes with \n
# I'll just rewrite the compile function entirely
new_compile = """    def compile_google_docs_payload(self, db) -> str:
        \"\"\"Builds an exhaustive, streamlined markdown summary for Google Docs / Gemini Browser edition.\"\"\"
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
        return "\\n\\n".join(payload_sections)"""

text = re.sub(r'    def compile_google_docs_payload\(self, db\) -> str:.*?        return .*?\.join\(payload_sections\)', new_compile, text, flags=re.DOTALL)

with open('injectors/google_docs.py', 'w', encoding='utf-8') as f:
    f.write(text)
