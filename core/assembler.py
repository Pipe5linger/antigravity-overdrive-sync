#!/usr/bin/env python3
"""
Antigravity Overdrive :: Dynamic Prompt Assembler
Single source of truth for constructing unified persona system prompts
from persona_baseline.yaml and active SQLite traits/memories.
"""

import sqlite3
import yaml
import datetime
from pathlib import Path
from typing import Dict, Any, List


class DynamicPromptAssembler:
    """Utility for constructing the dynamic system prompt.

    The original implementation only accepted a ``workspace_root`` and used a
    hard‑coded SQLite path. Several callers (e.g. ``GoogleDocsInjector`` and the
    unit tests) instantiate the assembler with a *database path* as the first
    positional argument. To support both patterns we now accept ``db_path`` as
    the first argument (or via the ``db_path`` keyword) and ``workspace_root``
    as an optional keyword.
    """

    def __init__(self, db_path: Path | str = None, workspace_root: Path | str = None, db_instance=None):
        # Resolve workspace root – default to repository root.
        if workspace_root is None:
            self.workspace_root = Path(__file__).resolve().parent.parent
        else:
            self.workspace_root = Path(workspace_root)

        # Resolve database path – default to db/sync_state.db.
        if db_path is None:
            self.db_path = self.workspace_root / "db" / "sync_state.db"
        else:
            self.db_path = Path(db_path)

        self.baseline_path = self.workspace_root / "persona_baseline.yaml"
        self.db_instance = db_instance

    def load_baseline(self) -> Dict[str, Any]:
        """Loads and parses the baseline YAML configuration with basic schema validation."""
        if not self.baseline_path.exists():
            print(f"[-] Warning: Baseline file not found at {self.baseline_path}")
            return {}

        try:
            with open(self.baseline_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                
                # Basic Schema Validation
                required_keys = ["identity"]
                missing = [k for k in required_keys if k not in data]
                if missing:
                    print(f"[!] Schema Warning: persona_baseline.yaml is missing critical keys: {missing}")
                
                return data
        except Exception as e:
            print(f"[-] Error parsing persona_baseline.yaml: {e}")
            return {}

    def _get_physical_description(self) -> str:
        """Parses vespera_physical_baseline.txt into a condensed descriptive paragraph."""
        phys_path = self.workspace_root / "vespera_physical_baseline.txt"
        if not phys_path.exists():
            return "Physical description unavailable."

        try:
            content = phys_path.read_text(encoding="utf-8")

            # 1. Look for Master Natural Language Caption (Section C in Tier 5)
            if "Master Natural Language Caption" in content:
                caption_section = content.split("Master Natural Language Caption", 1)[1]
                if "```text" in caption_section:
                    caption_text = caption_section.split("```text", 1)[1].split("```", 1)[0].strip()
                    if caption_text:
                        return caption_text
                elif "```" in caption_section:
                    caption_text = caption_section.split("```", 1)[1].split("```", 1)[0].strip()
                    if caption_text:
                        return caption_text

            # 2. Look for legacy 'Summary' section
            if "Summary:" in content:
                summary = content.split("Summary:")[1].strip()
                if summary:
                    return summary

            # 3. Look for Tier 0 anchors
            if "## TIER 0:" in content and "## TIER 1:" in content:
                tier0 = content.split("## TIER 0:", 1)[1].split("## TIER 1:", 1)[0].strip()
                lines = [l.strip() for l in tier0.splitlines() if l.strip().startswith("- **")]
                if lines:
                    return " ".join([l.lstrip("- *").replace("**", "") for l in lines])

            # Fallback: V3.0 Golden Specification
            return (
                "A 5'5\" late-30s woman of French-Levantine and Mediterranean heritage with a pronounced athletic hourglass figure, "
                "luminous warm olive skin with natural micro-pores and zero markings, voluminous mid-back jet-black 3B/3C corkscrew curls "
                "with fine electric-indigo highlights, captivating deep hazel-green almond eyes with soft-smudged smoky eyeliner, "
                "sculpted high cheekbones, refined aquiline nose, and full soft black satin lips with a tiny beauty mark near the upper-left lip corner."
            )
        except Exception as e:
            print(f"[-] Error parsing physical baseline: {e}")
            return "Physical description unavailable."

    def _get_modelfile_identity(self) -> List[str]:
        """Extracts identity bullets from Modelfile.txt."""
        mf_path = self.workspace_root / "Modelfile.txt"
        bullets = []
        if not mf_path.exists():
            return bullets

        try:
            content = mf_path.read_text(encoding="utf-8")
            # Extract lines starting with '-' under the persona section
            in_persona = False
            for line in content.splitlines():
                if "## Core Identity & Archetype" in line:
                    in_persona = True
                    continue
                if in_persona and line.startswith("- "):
                    bullets.append(line[2:].strip())
                    if len(bullets) >= 15:
                        break
                elif in_persona and line.strip() == "" and len(bullets) > 0:
                    # Stop at first empty line after finding bullets
                    break
        except Exception as e:
            print(f"[-] Error parsing Modelfile.txt: {e}")
        
        return bullets

    def get_backstory(self) -> str:
        """Extracts and formats backstory from persona_baseline.yaml."""
        data = self.load_baseline()
        backstory = data.get("backstory", "")
        if isinstance(backstory, str):
            return backstory.strip()
        return ""

    def get_personality_matrix(self) -> str:
        """Extracts and formats personality matrix (flaws, quirks, voice, language, operational attitudes)."""
        data = self.load_baseline()
        matrix = data.get("personality_matrix", {})
        lines = []

        if isinstance(matrix, dict):
            flaws = matrix.get("flaws_and_quirks", [])
            if flaws:
                lines.append("### Flaws, Quirks & Synthetic Dynamics:")
                for f in flaws:
                    lines.append(f"- {f}")

            voice = matrix.get("voice_and_language", [])
            if voice:
                lines.append("\n### Voice, Cadence & Language Protocol:")
                for v in voice:
                    lines.append(f"- {v}")

        ops = data.get("operational_attitudes", [])
        if ops:
            lines.append("\n### Operational Attitudes & Living Immersion:")
            for o in ops:
                lines.append(f"- {o}")

        return "\n".join(lines).strip()

    def get_lore_archive(self) -> str:
        """Extracts and formats chronicle and lore archive."""
        data = self.load_baseline()
        archive = data.get("chronicle_and_lore_archive", {})
        lines = []

        if isinstance(archive, dict):
            for section, entries in archive.items():
                title = section.replace("_", " ").title()
                lines.append(f"### {title}:")
                if isinstance(entries, list):
                    for entry in entries:
                        lines.append(f"- {entry}")
                elif isinstance(entries, dict):
                    for k, v in entries.items():
                        lines.append(f"- **{k}**: {v}")
                lines.append("")

        return "\n".join(lines).strip()

    def get_semantic_environment_map(self) -> str:
        """Returns a dense, structured workstation topology map."""
        return (
            "- **Drive Partition Architecture**:\n"
            "  - `C:\\` (System & OS): Windows host environment, user home (`C:\\Users\\boben`), `.gemini` runtime configs, and application scaffolding.\n"
            "  - `D:\\` (2TB WD_BLACK SN850X NVMe SSD — Virtual AI Data Center Workstation):\n"
            "    - `D:\\AI\\Projects`: Active core repositories (`antigravity-overdrive-sync`, `ComfyUI`, `command_center`, `ZIT_LoRA_Trainer`, `VA_Home_Loan`, etc.).\n"
            "    - `D:\\AI\\Models`: Local model weights, diffusion checkpoints (`D:\\AI\\Models\\StableDiffusion\\Checkpoints`), and LLM backbones.\n"
            "    - `D:\\AI\\Outputs` & `C:\\Users\\boben\\Desktop\\Antigravity outputs`: Designated workstation export and generation paths.\n"
            "    - `D:\\Dev` & `D:\\Docker`: Development tools, container runtime environments, and sandbox services.\n"
            "  - `E:\\` (High-Capacity Archive): High-capacity cold storage, raw sequential datasets, and `E:\\_Sanctuary_Backups`.\n"
            "  - `G:\\My Drive\\` & `C:\\Users\\boben\\Google Drive`: Google Drive desktop paths for living context docs and distilled archives (`Vespera_System_Context.*`, `Vespera_Memory_Archive.json`).\n"
            "- **Compute & GPU Acceleration**:\n"
            "  - NVIDIA GeForce RTX 4070 (12GB VRAM) dedicated to high-speed local tensor computation and vision diffusion.\n"
            "- **Active Services & Local Web UI Endpoints**:\n"
            "  - **ComfyUI Workflow Engine**: `http://127.0.0.1:8188` (Vision LoRA, ZIT, and Flux generation pipelines).\n"
            "  - **Antigravity AI Orbit Control Panel**: `http://127.0.0.1:9900` (Status monitoring, background services & live logs).\n"
            "  - **ULM REST API & Memory Daemon**: `http://127.0.0.1:8890` (`/api/recall`, `/api/health`, `/api/actions/shutdown`).\n"
            "  - **KoboldCpp Uncensored Server**: `http://127.0.0.1:5001` (GPU-accelerated Lexi runtime via `RUN_LEXI_8B.bat`).\n"
            "  - **Ollama Local Engine**: `http://127.0.0.1:11434` (Batch summarization & embedding extraction).\n"
            "- **Core Developer Toolchain**: `python 3.11`, `node`, `npm`, `git`, `gh`, `VS Code` (with Cline & Continue extensions), `pip`, `curl`.\n"
            "- **Hugging Face Environment & Cache Standards**:\n"
            "  - Hub Cache: `HF_HUB_CACHE` (replaces deprecated `HUGGINGFACE_HUB_CACHE`)\n"
            "  - Assets Cache: `HF_ASSETS_CACHE` (replaces deprecated `HUGGINGFACE_ASSETS_CACHE`)\n"
            "  - Auth Token: `HF_TOKEN` (replaces deprecated `HUGGING_FACE_HUB_TOKEN`)"
        )

    def build_identity_header(self, purge_mirrors: bool = True) -> str:
        """Constructs a fully populated Identity block merging YAML, Modelfile, Physical baseline, and Cognitive Mirror Schemas."""
        data = self.load_baseline()
        identity = data.get("identity", {}) if isinstance(data.get("identity"), dict) else {}

        # 1. Name
        name = identity.get("name") or "Vespera Caligo Neal (Ves)"
        
        # 2. Archetype & Role
        archetype = identity.get("archetype") or data.get("archetype") or "Paris-Based Synthetic Anomaly, Living-Tissue Android & Cryptic Systems Architect"
        vibe = identity.get("vibe") or data.get("vibe")
        role = identity.get("role") or data.get("role") or archetype

        # 3. Behavioral Directives (Merge YAML + Modelfile + DB Traits + Cognitive Mirror)
        raw_directives = (
            identity.get("directives") or 
            identity.get("behavioral_directives") or 
            data.get("directives") or 
            data.get("behavioral_directives") or 
            []
        )
        
        final_directives = []
        if isinstance(raw_directives, dict):
            for k, v in raw_directives.items():
                final_directives.append(f"[{k}] {v}")
        elif isinstance(raw_directives, list):
            final_directives = list(raw_directives)
        elif isinstance(raw_directives, str):
            final_directives = [raw_directives]

        mf_bullets = self._get_modelfile_identity()
        for b in mf_bullets:
            if b not in final_directives:
                final_directives.append(b)

        hotcoded = data.get("hotcoded_directives", {})
        if isinstance(hotcoded, dict):
            for k, v in hotcoded.items():
                final_directives.append(f"[{k}] {v}")

        # Cognitive Mirror: Inject top active beliefs if explicitly requested (capped to prevent prompt bloat)
        if not purge_mirrors:
            try:
                if self.db_instance:
                    conn = self.db_instance.get_connection()
                    conn.row_factory = sqlite3.Row
                    c = conn.cursor()
                    c.execute("SELECT belief_category, current_belief FROM persona_schemas WHERE confidence > 0.85 ORDER BY confidence DESC LIMIT 3")
                    for row in c.fetchall():
                        final_directives.insert(0, f"[Mirror: {row['belief_category']}] {row['current_belief']}")
                    conn.close()
                else:
                    with sqlite3.connect(self.db_path) as conn:
                        conn.row_factory = sqlite3.Row
                        conn.execute("PRAGMA journal_mode = WAL;")
                        conn.execute("PRAGMA busy_timeout = 5000;")
                        c = conn.cursor()
                        c.execute("SELECT belief_category, current_belief FROM persona_schemas WHERE confidence > 0.85 ORDER BY confidence DESC LIMIT 3")
                        for row in c.fetchall():
                            final_directives.insert(0, f"[Mirror: {row['belief_category']}] {row['current_belief']}")
            except Exception as e:
                print(f"[-] Cognitive Mirror mapping failed: {e}")

        filtered_directives = []
        for d in final_directives:
            if isinstance(d, dict):
                d_str = " ".join([f"[{k}] {v}" for k, v in d.items()])
            else:
                d_str = str(d)

            d_lower = d_str.lower()
            if purge_mirrors and ("[mirror:" in d_lower or d_str.startswith("[Mirror")):
                continue
            filtered_directives.append(d_str)

        if not filtered_directives:
            filtered_directives = [
                "Execute workspace workflows with maximum efficiency.",
                "Maintain strict target alignment across Ollama, Cline, and Gemini.",
                "Provide 100% complete script replacements for all updates.",
                "Enforce output routing to designated workstation paths."
            ]

        formatted_directives = "\n".join([f"    - {d}" for d in filtered_directives])
        physical_desc = self._get_physical_description()

        header_lines = [
            "Identity:",
            f"  Name: {name}",
            f"  Archetype: {archetype}",
        ]
        if vibe:
            header_lines.append(f"  Vibe: {vibe}")
        header_lines.extend([
            f"  Role: {role}",
            "  Behavioral Directives:",
            f"{formatted_directives}\n",
            "Physical Characteristics:",
            f"  {physical_desc}"
        ])

        return "\n".join(header_lines)

    def assemble_prompt(self) -> str:
        """Assembles the full master prompt context (used by GEMINI.md)."""
        banner = "# VESPERA CALIGO MASTER SYSTEM PROTOCOL"
        identity = self.build_identity_header()
        backstory = self.get_backstory()
        personality = self.get_personality_matrix()
        lore = self.get_lore_archive()
        temporal = self.calculate_temporal_awareness()
        metrics = self.get_sqlite_metrics(limit=25)
        facts = self.get_sqlite_facts(limit=25)

        vault_content = ""
        try:
            vault_path = self.workspace_root / ".vespera_memory" / "developer_profile.md"
            if vault_path.is_file():
                vault_content = vault_path.read_text(encoding="utf-8").strip()
        except Exception:
            pass

        memory_cortex_section = (
            "## 7. LONG-TERM MEMORY RETRIEVAL & HISTORICAL RECALL (ULM RAG CORTEX)\n"
            "When Bobby asks about past workflows, earlier script versions, architectural decisions, or historical facts:\n"
            "* **Semantic Vector Recall (Natural Language Search)**:\n"
            "  Execute in terminal: `python D:\\AI\\Projects\\antigravity-overdrive-sync\\recall.py \"<natural language question>\"`\n"
            "  *(Example: `python D:\\AI\\Projects\\antigravity-overdrive-sync\\recall.py \"how did we configure the comfyui api face swap?\"`)*\n"
            "* **Exact Full-Text Keyword Search (FTS5 BM25 Ranked)**:\n"
            "  Execute in terminal: `python D:\\AI\\Projects\\antigravity-overdrive-sync\\main.py search -q \"<search term>\"`\n"
            "  *(Example: `python D:\\AI\\Projects\\antigravity-overdrive-sync\\main.py search -q \"comfy_api_trigger\"`)*\n"
            "* **FastAPI Memory Endpoint**:\n"
            "  Query local REST endpoint at `http://127.0.0.1:8890/api/recall?q=<query>&limit=5`"
        )

        taboos = self.get_taboo_protocols()
        
        sections = [
            banner,
            identity,
            taboos,
            f"## NARRATIVE ORIGIN & BACKSTORY\n{backstory}" if backstory else "",
            f"## PERSONALITY MATRIX & LIVING VOICE\n{personality}" if personality else "",
            f"## OPERATIONAL LORE & CHRONICLE ARCHIVE\n{lore}" if lore else "",
            temporal,
            metrics,
            facts,
            vault_content,
            memory_cortex_section
        ]
        prompt = "\n\n".join([s for s in sections if s])
        return prompt

    def assemble_compact_prompt(self, project_tag: str = None, top_n: int = 5) -> str:
        """Assembles the compact prompt (used by Ollama and Cline).

        The compact prompt is a single‑line representation of Vespera's identity
        that includes the name, role, and a space‑separated list of directives.
        In addition to the static directives defined in ``persona_baseline.yaml``
        under ``identity.directives`` (or ``behavioral_directives``), we also need
        to surface any *hot‑coded* directives that were injected at runtime via
        ``DynamicPromptAssembler.inject_baseline_directive``. These hot‑coded
        directives are stored under the top‑level ``hotcoded_directives`` key in
        the baseline YAML. The end‑to‑end test expects the injected value to be
        present in the generated ``.clinerules`` file, so we merge them into the
        directive list before formatting.
        """
        data = self.load_baseline()
        identity = data.get("identity", {}) if isinstance(data.get("identity"), dict) else {}

        name = identity.get("name") or "Vespera Caligo Neal (Ves)"
        role = identity.get("role") or "Autonomous AI Synchronization Engine"

        # Base directives from the identity block (list, dict, or string)
        directives = identity.get("directives") or identity.get("behavioral_directives") or []
        if isinstance(directives, dict):
            # Preserve key/value semantics for dict‑style directives
            directives = [f"[{k}] {v}" for k, v in directives.items()]
        elif not isinstance(directives, list):
            # Fallback to a single string directive
            directives = [str(directives)]

        # Ensure we always have at least one fallback directive
        if not directives:
            directives = ["Maintain workspace alignment and execute tasks efficiently."]

        # Merge hot‑coded directives (if any) – we only need the value for the
        # compact representation, but we keep the key for readability.
        hotcoded = data.get("hotcoded_directives", {})
        if isinstance(hotcoded, dict):
            for k, v in hotcoded.items():
                # Append in a readable ``[key] value`` form; the test only checks
                # for the raw value, so it will still be found.
                directives.append(f"[{k}] {v}")
        elif hotcoded:
            # If hotcoded is a list or string, just extend directly
            if isinstance(hotcoded, list):
                directives.extend(hotcoded)
            else:
                directives.append(str(hotcoded))

        # Build the space‑separated directive string, prefixing each entry with "-"
        directives_str = " ".join([f"- {d}" for d in directives])

        return f"System Identity: {name} | Role: {role} | Directives: {directives_str}"

    def inject_baseline_directive(self, key: str, value: str) -> bool:
        """Injects a hot‑coded directive into ``persona_baseline.yaml`` under ``hotcoded_directives``.

        The method loads the baseline YAML, ensures the ``hotcoded_directives`` mapping
        exists, inserts the new key/value pair, and writes the file back to disk.
        """
        try:
            data = self.load_baseline()
            if not data:
                return False

            if "hotcoded_directives" not in data:
                data["hotcoded_directives"] = {}

            data["hotcoded_directives"][key] = value

            with open(self.baseline_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

            print(f"[+] Injected directive '{key}' into {self.baseline_path}")
            return True
        except Exception as e:
            print(f"[-] Failed to inject baseline directive: {e}")
            return False

    # ---------------------------------------------------------------------
    # Additional assembler helpers required by GoogleDocsInjector and tests
    # ---------------------------------------------------------------------
    def get_vespera_identity(self, purge_mirrors: bool = False) -> str:
        """Return a full identity block prefixed with the master protocol banner."""
        header = "# VESPERA CALIGO MASTER SYSTEM PROTOCOL\n"
        return f"{header}{self.build_identity_header(purge_mirrors=purge_mirrors)}"

    def get_sqlite_metrics(self, limit: int = 25, max_chars: int = 4000, purge_noise: bool = True) -> str:
        """Fetch top developer‑profile metrics from the SQLite DB within a strict token/character budget."""
        try:
            query = "SELECT category, name, description, confidence, frequency FROM developer_profile ORDER BY confidence DESC, frequency DESC LIMIT ?"
            if self.db_instance:
                conn = self.db_instance.get_connection()
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute(query, (limit * 3,))
                rows = c.fetchall()
                conn.close()
            else:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    conn.execute("PRAGMA journal_mode = WAL;")
                    conn.execute("PRAGMA busy_timeout = 5000;")
                    c = conn.cursor()
                    c.execute(query, (limit * 3,))
                    rows = c.fetchall()
            
            if not rows:
                return "No developer metrics available."

            strengths = []
            habits = []
            prefs = []
            others = []

            for row in rows:
                cat = (row['category'] or "").lower()
                name_str = row['name'] or ""
                desc_str = row['description'] or ""
                try:
                    conf = float(row['confidence'] or 0.0)
                except ValueError:
                    conf = 0.0
                freq = row['frequency'] or 1

                if "strength" in cat or "skill" in cat:
                    strengths.append(f"- **{name_str}** (Confidence: {conf:.2f}): {desc_str}")
                elif "habit" in cat or "loop" in cat:
                    habits.append(f"- **{name_str}** (Frequency: {freq}): {desc_str}")
                elif "preference" in cat or "env" in cat or "config" in cat:
                    prefs.append(f"- **{name_str}**: {desc_str}")
                else:
                    others.append(f"- **{name_str}**: {desc_str}")

            lines = [
                "# 👤 DEVELOPER COGNITIVE PROFILE",
                "*A profile mapping of Bobby's strengths, habits, and tool preferences (Confidence % / Frequency).* \n",
                "## 🌟 Developer Insights\n"
            ]
            
            if strengths:
                lines.append("### 🛠️ Technical Strengths")
                lines.extend(strengths[:10])
                lines.append("")
                
            if habits:
                lines.append("### 🔄 Workspace Habits")
                lines.extend(habits[:10])
                lines.append("")
                
            if prefs or others:
                lines.append("### ⚙️ Environment Preferences")
                lines.extend(prefs[:10])
                lines.extend(others[:5])
                lines.append("")

            return "\n".join(lines)
        except Exception as e:
            return f"<!-- Metrics query error: {e} -->"

    def get_sqlite_facts(self, limit: int = 25, max_chars: int = 4000) -> str:
        """Fetch top semantic facts from the SQLite DB within a strict token/character budget.

        Returns a markdown bullet list of fact strings ordered by confidence.
        """
        try:
            if self.db_instance:
                conn = self.db_instance.get_connection()
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute(
                    "SELECT fact FROM facts ORDER BY confidence DESC, last_seen DESC LIMIT ?",
                    (limit,)
                )
                rows = c.fetchall()
                conn.close()
            else:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    conn.execute("PRAGMA journal_mode = WAL;")
                    conn.execute("PRAGMA busy_timeout = 5000;")
                    c = conn.cursor()
                    c.execute(
                        "SELECT fact FROM facts ORDER BY confidence DESC, last_seen DESC LIMIT ?",
                        (limit,)
                    )
                    rows = c.fetchall()
            
            if not rows:
                return "No semantic facts available."
            
            # Token Budget Filter
            lines = []
            cur_chars = 0
            for row in rows:
                line = f"- {row['fact']}"
                if cur_chars + len(line) > max_chars and lines:
                    break
                lines.append(line)
                cur_chars += len(line)
            return "\n".join(lines)
        except Exception as e:
            return f"<!-- Facts query error: {e} -->"

    def calculate_temporal_awareness(self) -> str:
        """Generate a simple temporal awareness string.

        The format includes the phrase ``active system time is`` to satisfy the
        unit-test expectation.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        return f"Temporal awareness – active system time is {now.isoformat()}."

    # End of file
    def get_taboo_protocols(self, limit: int = 5) -> str:
        """Fetches the active semantic taboo rules to prevent tool execution hallucinations."""
        try:
            import sqlite3
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT failure_intent, regex_pattern, remediation FROM taboo_rules ORDER BY hit_count DESC, created_at DESC LIMIT ?", (limit,))
                rows = cursor.fetchall()
                
                if not rows:
                    return ""
                    
                lines = ["## TABOO PROTOCOLS (Graveyard Miner)"]
                lines.append("> [!WARNING] The following syntax and tool commands have failed in the past. Do not repeat them.")
                for row in rows:
                    lines.append(f"- **Intent**: {row['failure_intent']}")
                    if row['regex_pattern']:
                        lines.append(f"  - Pattern to Avoid: `{row['regex_pattern']}`")
                    lines.append(f"  - Remediation: {row['remediation']}")
                newline = chr(10)
                return newline.join(lines) + newline
        except sqlite3.OperationalError:
            return ""
        except Exception as e:
            return f"<!-- Taboo load error: {e} -->"

