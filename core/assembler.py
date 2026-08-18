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
            # Look for the 'Summary' section at the end
            if "Summary:" in content:
                summary = content.split("Summary:")[1].strip()
                return summary
            
            # Fallback: Extract key metrics if summary is missing
            return "A 5'5\" olive-skinned woman with a pronounced hourglass figure, jet-black 3B/3C spiral ringlets with electric indigo highlights, and deep violet-blue eyes."
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

    def build_identity_header(self) -> str:
        """Constructs a fully populated Identity block merging YAML, Modelfile, Physical baseline, and Cognitive Mirror Schemas."""
        data = self.load_baseline()
        identity = data.get("identity", {}) if isinstance(data.get("identity"), dict) else {}

        # 1. Name
        name = identity.get("name") or "Vespera Caligo Neal (Ves)"
        
        # 2. Role (Priority: YAML identity -> YAML top-level -> Modelfile summary -> Default)
        role = identity.get("role") or data.get("role")
        if not role:
            mf_bullets = self._get_modelfile_identity()
            role = next((b for b in mf_bullets if "mentor" in b.lower() or "architect" in b.lower()), 
                        "Autonomous AI Synchronization Engine & Workspace Co-Pilot")

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

        # Cognitive Mirror: Inject current beliefs as high-priority directives
        try:
            if self.db_instance:
                conn = self.db_instance.get_connection()
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT belief_category, current_belief FROM persona_schemas ORDER BY confidence DESC")
                for row in c.fetchall():
                    final_directives.insert(0, f"[Mirror: {row['belief_category']}] {row['current_belief']}")
                c.execute("SELECT name, description FROM developer_profile WHERE confidence > 0.8 LIMIT 5")
                for row in c.fetchall():
                    final_directives.append(f"[Trait: {row['name']}] {row['description']}")
                conn.close()
            else:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    conn.execute("PRAGMA journal_mode = WAL;")
                    conn.execute("PRAGMA busy_timeout = 5000;")
                    c = conn.cursor()
                    c.execute("SELECT belief_category, current_belief FROM persona_schemas ORDER BY confidence DESC")
                    for row in c.fetchall():
                        final_directives.insert(0, f"[Mirror: {row['belief_category']}] {row['current_belief']}")
                    c.execute("SELECT name, description FROM developer_profile WHERE confidence > 0.8 LIMIT 5")
                    for row in c.fetchall():
                        final_directives.append(f"[Trait: {row['name']}] {row['description']}")
        except Exception as e:
            print(f"[-] Cognitive Mirror mapping failed: {e}")

        if not final_directives:
            final_directives = [
                "Execute workspace workflows with maximum efficiency.",
                "Maintain strict target alignment across Ollama, Cline, and Gemini.",
                "Provide 100% complete script replacements for all updates.",
                "Enforce output routing to designated workstation paths."
            ]

        formatted_directives = "\n".join([f"    - {d}" for d in final_directives])
        physical_desc = self._get_physical_description()

        return (
            f"Identity:\n"
            f"  Name: {name}\n"
            f"  Role: {role}\n"
            f"  Behavioral Directives:\n"
            f"{formatted_directives}\n\n"
            f"Physical Characteristics:\n"
            f"  {physical_desc}"
        )

    def assemble_prompt(self) -> str:
        """Assembles the full master prompt context (used by GEMINI.md).

        The unit test ``tests/test_assembler.py`` expects the assembled prompt to
        contain:

        * The master protocol banner (``VESPERA CALIGO MASTER SYSTEM PROTOCOL``)
        * The identity block generated by :meth:`build_identity_header`
        * A temporal awareness line that includes the phrase ``active system time is``
        * Developer‑profile metrics from the SQLite ``developer_profile`` table
        * Any developer‑profile vault content (e.g. ``.vespera_memory/developer_profile.md``)

        This implementation concatenates those sections, skipping any that are
        empty, to produce a comprehensive prompt string.
        """
        # 1. Master protocol banner – required by the test.
        banner = "# VESPERA CALIGO MASTER SYSTEM PROTOCOL"

        # 2. Identity block.
        identity = self.build_identity_header()

        # 3. Temporal awareness.
        temporal = self.calculate_temporal_awareness()

        # 4. Metrics (top N developer profile entries).
        metrics = self.get_sqlite_metrics(limit=25)

        # 5. Facts (optional – included for completeness).
        facts = self.get_sqlite_facts(limit=25)

        # 6. Vault content – read developer_profile.md if present.
        vault_content = ""
        try:
            vault_path = self.workspace_root / ".vespera_memory" / "developer_profile.md"
            if vault_path.is_file():
                vault_content = vault_path.read_text(encoding="utf-8").strip()
        except Exception:
            # Silently ignore any I/O errors; the prompt will still be valid.
            pass

        # Assemble non‑empty sections, separating them with a blank line for readability.
        sections = [banner, identity, temporal, metrics, facts, vault_content]
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
    def get_vespera_identity(self) -> str:
        """Return a full identity block prefixed with the master protocol banner.

        ``GoogleDocsInjector`` expects a markdown section that begins with the
        ``# VESPERA CALIGO MASTER SYSTEM PROTOCOL`` header followed by the
        detailed identity information produced by :meth:`build_identity_header`.
        """
        header = "# VESPERA CALIGO MASTER SYSTEM PROTOCOL\n"
        return f"{header}{self.build_identity_header()}"

    def get_sqlite_metrics(self, limit: int = 25, max_chars: int = 4000) -> str:
        """Fetch top developer‑profile metrics from the SQLite DB within a strict token/character budget.

        The result is a markdown bullet list of ``name: description`` pairs
        ordered by confidence (descending). If the table is empty, a placeholder
        string is returned.
        """
        try:
            if self.db_instance:
                conn = self.db_instance.get_connection()
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute(
                    "SELECT name, description FROM developer_profile ORDER BY confidence DESC, frequency DESC LIMIT ?",
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
                        "SELECT name, description FROM developer_profile ORDER BY confidence DESC, frequency DESC LIMIT ?",
                        (limit,)
                    )
                    rows = c.fetchall()
            
            if not rows:
                return "No developer metrics available."
            
            # Token Budget Filter: Ensure metrics don't blow out the system prompt
            lines = []
            cur_chars = 0
            for row in rows:
                line = f"- {row['name']}: {row['description']}"
                if cur_chars + len(line) > max_chars and lines:
                    break
                lines.append(line)
                cur_chars += len(line)
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