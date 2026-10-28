import os
import sys
import json
import hashlib
import subprocess
import datetime
from pathlib import Path

# Enforce UTF-8 terminal piping on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True, errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', line_buffering=True, errors='replace')
    except AttributeError:
        pass

from core.database import ULMDatabase, get_canonical_db_path
from core.engine import ULMEngine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = Path(os.environ.get("ULM_DB_PATH", str(get_canonical_db_path())))
DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "config" / "playbooks_manifest.json"

class ProceduralRunner:
    def __init__(self, db_path=None, manifest_path=None):
        self.manifest_path = Path(manifest_path) if manifest_path else DEFAULT_MANIFEST_PATH
        if isinstance(db_path, ULMDatabase):
            self.db = db_path
            self.db_path = str(db_path.db_path)
        else:
            if not db_path:
                self.db_path = str(DEFAULT_DB_PATH)
            else:
                self.db_path = str(db_path)
            self.db = ULMDatabase(self.db_path)
            self.db.initialize_db()

    def execute_node(self, node_id, dry_run=False):
        """Executes a single procedure node and records its status in SQLite."""
        proc = self.db.get_procedure(node_id)
        if not proc:
            print(f"[-] Node not found in procedural graph: {node_id}")
            return False, -1, f"Node {node_id} not found"

        action = proc.get("action_name", "")
        target = proc.get("target_script_path", "")
        print(f"\n▶ [Executing Node: {node_id}] {action}")
        print(f"  Target: {target}")

        if dry_run:
            print(f"  [DRY RUN] Would execute: {target}")
            return True, 0, "[DRY RUN] Simulated execution success"

        if not target:
            print("  [*] No execution command specified. Marking as PASS.")
            self.db.update_procedure_status(node_id, "SUCCESS")
            return True, 0, "No command executed"

        # Determine how to run target safely
        import shlex
        cmd = target.strip().replace(r'\"', '"')
        cwd = PROJECT_ROOT

        try:
            tokens = shlex.split(cmd, posix=False)
            if not tokens:
                return True, 0, "Empty command"

            # Strict Binary Allowlist: Only approved Python runtimes are permitted
            first_token = tokens[0].lower()
            if first_token.endswith(".exe"):
                first_token = first_token[:-4]

            if first_token not in ("python", "python3", "py"):
                err_msg = f"Security sandbox violation: Execution of non-Python binary '{tokens[0]}' is prohibited."
                print(f"  [-] {err_msg}")
                self.db.update_procedure_status(node_id, "ERROR: Security Sandbox Rejection")
                return False, -1, err_msg

            # Target must specify a script argument
            if len(tokens) < 2:
                err_msg = "Security sandbox violation: No script target provided."
                print(f"  [-] {err_msg}")
                self.db.update_procedure_status(node_id, "ERROR: Security Sandbox Rejection")
                return False, -1, err_msg

            # Inline code execution or interpreter flags (-c, -m, etc.) are prohibited; target must be an audited file on disk
            if tokens[1].startswith("-"):
                err_msg = f"Security sandbox violation: Flag '{tokens[1]}' is prohibited. Target must be an audited script file under project root."
                print(f"  [-] {err_msg}")
                self.db.update_procedure_status(node_id, "ERROR: Security Sandbox Rejection")
                return False, -1, err_msg

            tokens[0] = sys.executable
            script_candidate = Path(tokens[1])
            if not script_candidate.is_absolute():
                script_candidate = (PROJECT_ROOT / script_candidate).resolve()
            else:
                script_candidate = script_candidate.resolve()
            
            # Ensure script is strictly inside project root and inspected relative to it
            try:
                rel_parts = script_candidate.relative_to(PROJECT_ROOT).parts
            except ValueError:
                err_msg = f"Security sandbox violation: Script path '{script_candidate}' is outside project root."
                print(f"  [-] {err_msg}")
                self.db.update_procedure_status(node_id, "ERROR: Security Sandbox Rejection")
                return False, -1, err_msg

            # Ensure script is strictly inside vetted procedural script directories
            approved_dirs = [
                (PROJECT_ROOT / "scripts" / "playbooks").resolve(),
            ]
            disallowed_names = {"scratch", "tmp", "temp", "node_modules", ".git"}
            
            if any(part.lower() in disallowed_names for part in rel_parts):
                err_msg = f"Security sandbox violation: Execution from unvetted directory '{script_candidate}' is prohibited."
                print(f"  [-] {err_msg}")
                self.db.update_procedure_status(node_id, "ERROR: Security Sandbox Rejection")
                return False, -1, err_msg

            is_in_approved = False
            for app_dir in approved_dirs:
                try:
                    script_candidate.relative_to(app_dir)
                    is_in_approved = True
                    break
                except ValueError:
                    continue

            if not is_in_approved:
                err_msg = f"Security sandbox violation: Script path '{script_candidate}' is not in an approved procedural playbook directory."
                print(f"  [-] {err_msg}")
                self.db.update_procedure_status(node_id, "ERROR: Security Sandbox Rejection")
                return False, -1, err_msg
            
            if not script_candidate.exists() or not script_candidate.is_file():
                err_msg = f"Procedure target script not found: '{script_candidate}'"
                print(f"  [-] {err_msg}")
                self.db.update_procedure_status(node_id, "FAILED: Script Not Found")
                return False, -1, err_msg

            # Cryptographic SHA-256 manifest verification (strictly fail-closed)
            manifest_path = getattr(self, "manifest_path", None) or DEFAULT_MANIFEST_PATH
            if not manifest_path.exists():
                err_msg = f"Security sandbox violation: Playbooks manifest '{manifest_path}' is missing (fail-closed)."
                print(f"  [-] {err_msg}")
                self.db.update_procedure_status(node_id, "ERROR: Security Sandbox Rejection")
                return False, -1, err_msg

            try:
                with open(manifest_path, "r", encoding="utf-8") as mf:
                    manifest = json.load(mf)
                with open(script_candidate, "rb") as sf:
                    actual_hash = hashlib.sha256(sf.read()).hexdigest()
                expected_hash = manifest.get(script_candidate.name) or manifest.get(str(script_candidate.relative_to(PROJECT_ROOT)).replace("\\", "/"))
                if not expected_hash or expected_hash != actual_hash:
                    err_msg = f"Security sandbox violation: Cryptographic checksum mismatch for script '{script_candidate.name}'."
                    print(f"  [-] {err_msg}")
                    self.db.update_procedure_status(node_id, "ERROR: Security Sandbox Rejection")
                    return False, -1, err_msg
            except Exception as me:
                if "Security sandbox violation" in str(me):
                    return False, -1, str(me)
                err_msg = f"Security sandbox violation: Failed verifying script manifest: {me}"
                print(f"  [-] {err_msg}")
                self.db.update_procedure_status(node_id, "ERROR: Security Sandbox Rejection")
                return False, -1, err_msg
            
            # Execute command safely without shell invocation, enforcing -I (Isolated mode) to prevent sys.path stdlib shadowing
            exec_tokens = [sys.executable, "-I", str(script_candidate)] + tokens[2:]
            proc_exec = subprocess.run(
                exec_tokens,
                shell=False,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300
            )
            success = (proc_exec.returncode == 0)
            status_str = "SUCCESS" if success else f"FAILED (Exit {proc_exec.returncode})"
            self.db.update_procedure_status(node_id, status_str)

            if proc_exec.stdout:
                for line in proc_exec.stdout.strip().splitlines()[-5:]:
                    print(f"    {line}")
            if proc_exec.stderr and not success:
                for line in proc_exec.stderr.strip().splitlines()[-5:]:
                    print(f"    [ERR] {line}")

            print(f"  Result: {status_str}")
            return success, proc_exec.returncode, proc_exec.stdout or proc_exec.stderr
        except Exception as e:
            err_msg = f"Execution exception: {e}"
            print(f"  [-] {err_msg}")
            self.db.update_procedure_status(node_id, f"ERROR: {e}")
            return False, -1, err_msg

    def execute_chain(self, start_node_id, max_steps=10, dry_run=False):
        """Traverses procedural triplets from start_node_id following dynamic conditions."""
        current_node_id = start_node_id
        visited = []
        step = 1

        print(f"\n⚡ Initiating Procedural Execution Chain from '{start_node_id}'")
        print("=" * 70)

        while current_node_id and step <= max_steps:
            visited.append(current_node_id)
            success, code, out = self.execute_node(current_node_id, dry_run=dry_run)

            # Look up relations for the next step
            rel_type = "ON_SUCCESS_TRIGGER" if success else "ON_FAILURE_FALLBACK"
            next_procs = self.db.get_next_procedures(current_node_id, relation_type=rel_type)

            if not next_procs:
                # Try generic edge if no explicit success/failure edge
                next_procs = self.db.get_next_procedures(current_node_id)

            chosen_node = None
            if next_procs:
                for candidate in next_procs:
                    cond = candidate.get("condition_logic")
                    if cond:
                        cond_clean = cond.strip().lower()
                        if cond_clean == "on_success":
                            if not success:
                                continue
                        elif cond_clean == "on_failure":
                            if success:
                                continue
                        elif "exit_code" in cond_clean:
                            try:
                                if "==" in cond_clean and int(cond_clean.split("==")[-1].strip()) != code:
                                    continue
                                elif "!=" in cond_clean and int(cond_clean.split("!=")[-1].strip()) == code:
                                    continue
                                else:
                                    continue  # Fail closed on unknown syntax
                            except Exception:
                                continue  # Fail closed on parse error
                        elif "==" in cond_clean:
                            target_val = cond_clean.split("==")[-1].strip()
                            if target_val == "true" and not success:
                                continue
                            elif target_val == "false" and success:
                                continue
                        else:
                            # Fail closed on unparseable conditions
                            continue
                    chosen_node = candidate
                    break

            if chosen_node:
                next_node = chosen_node
                edge_label = next_node.get("relation_type", "TRANSITION")
                print(f"\n  🔀 Traversal Edge: [{current_node_id}] --({edge_label})--> [{next_node['node_id']}]")
                current_node_id = next_node["node_id"]
                step += 1
            else:
                print(f"\n🏁 End of procedural branch reached at [{current_node_id}].")
                break

        print("=" * 70)
        print(f"[+] Procedural Chain Complete. Steps executed: {len(visited)} ({' -> '.join(visited)})\n")
        return visited

    def seed_production_workflows(self):
        """Seeds the 3 core production workflows into SQLite using strictly audited script files."""
        print("[*] Seeding Core Production Workflows into Procedural Graph...")

        # ---------------------------------------------------------------------
        # Workflow 1: ComfyUI Batch Sweep & VRAM Governor
        # ---------------------------------------------------------------------
        self.db.add_procedure(
            node_id="comfyui_vram_guard",
            action_name="Pre-Flight VRAM & Workload Guard",
            target_script_path=r"python scripts/playbooks/procedure_helpers.py vram_guard",
            expected_outcome="Verify ComfyUI readiness & ensure Ollama VRAM is evacuated",
            last_execution_status="READY"
        )
        self.db.add_procedure(
            node_id="comfyui_queue_inject",
            action_name="Inject Batch to ComfyUI API",
            target_script_path=r"python scripts/playbooks/procedure_helpers.py comfyui_vram",
            expected_outcome="Confirm 127.0.0.1:8188 responds and has VRAM headroom",
            last_execution_status="READY"
        )
        self.db.add_procedure(
            node_id="comfyui_recovery_fallback",
            action_name="ComfyUI VRAM Recovery & Zombie Cleanup",
            target_script_path=r"python scripts/playbooks/procedure_helpers.py evict_ollama",
            expected_outcome="Purge Ollama VRAM and reset GPU memory for RTX 4070",
            last_execution_status="READY"
        )

        # Relations for Workflow 1
        self.db.add_relation("comfyui_vram_guard", "ON_SUCCESS_TRIGGER", "comfyui_queue_inject", "vram_ok == True")
        self.db.add_relation("comfyui_vram_guard", "ON_FAILURE_FALLBACK", "comfyui_recovery_fallback", "oom_or_conflict == True")
        self.db.add_relation("comfyui_recovery_fallback", "ON_SUCCESS_TRIGGER", "comfyui_vram_guard", "retry_guard == True")

        # ---------------------------------------------------------------------
        # Workflow 2: Render Harvest Curation & Sorter
        # ---------------------------------------------------------------------
        self.db.add_procedure(
            node_id="harvest_poll_renders",
            action_name="Poll Dataset Image Output Directory",
            target_script_path=r"python scripts/playbooks/procedure_helpers.py check_render_dir",
            expected_outcome="Confirm existence of output dataset folder",
            last_execution_status="READY"
        )
        self.db.add_procedure(
            node_id="harvest_run_organizer",
            action_name="Run Harvest Curation & Aspect Ratio Audit",
            target_script_path=r"python scripts/playbooks/procedure_helpers.py curate_harvest",
            expected_outcome="Validate image integrity, resolutions, and quarantine anomalies",
            last_execution_status="READY"
        )
        self.db.add_procedure(
            node_id="harvest_quarantine_fallback",
            action_name="Harvest Anomaly Quarantine Notification",
            target_script_path=r"python scripts/playbooks/procedure_helpers.py notify_quarantine",
            expected_outcome="Quarantine flagged files without halting downstream jobs",
            last_execution_status="READY"
        )
        self.db.add_procedure(
            node_id="harvest_stage_complete",
            action_name="Harvest Curation Complete & Staged",
            target_script_path=r"python scripts/playbooks/procedure_helpers.py notify_complete",
            expected_outcome="Confirm clean dataset ready for training or review",
            last_execution_status="READY"
        )

        # Relations for Workflow 2
        self.db.add_relation("harvest_poll_renders", "ON_SUCCESS_TRIGGER", "harvest_run_organizer", "dir_exists == True")
        self.db.add_relation("harvest_run_organizer", "ON_SUCCESS_TRIGGER", "harvest_stage_complete", "valid_renders > 0")
        self.db.add_relation("harvest_run_organizer", "ON_FAILURE_FALLBACK", "harvest_quarantine_fallback", "corrupt_renders > 0")

        # ---------------------------------------------------------------------
        # Workflow 3: Autonomous ULM Sync & Context Lifecycle
        # ---------------------------------------------------------------------
        self.db.add_procedure(
            node_id="ulm_sync_ingest",
            action_name="ULM Sync Log Ingestion",
            target_script_path=r"python scripts/playbooks/procedure_helpers.py sync_ingest",
            expected_outcome="Parse newly modified transcripts into SQLite with WAL mode",
            last_execution_status="READY"
        )
        self.db.add_procedure(
            node_id="ulm_profile_facts",
            action_name="Memory Fact Consolidation & Profile Evaluation",
            target_script_path=r"python scripts/playbooks/procedure_helpers.py count_facts",
            expected_outcome="Extract active profile metrics and deduplicate facts",
            last_execution_status="READY"
        )
        self.db.add_procedure(
            node_id="ulm_vram_evict",
            action_name="Post-Sync Ollama VRAM Eviction",
            target_script_path=r"python scripts/playbooks/procedure_helpers.py evict_ollama",
            expected_outcome="Purge Ollama VRAM models to release GPU back to ComfyUI",
            last_execution_status="READY"
        )

        # Relations for Workflow 3
        self.db.add_relation("ulm_sync_ingest", "ON_SUCCESS_TRIGGER", "ulm_profile_facts", "ingest_success == True")
        self.db.add_relation("ulm_profile_facts", "ON_SUCCESS_TRIGGER", "ulm_vram_evict", "profile_complete == True")

        # ---------------------------------------------------------------------
        # Workflow 4: ComfyUI Workflow Integrity & Link Audit
        # ---------------------------------------------------------------------
        self.db.add_procedure(
            node_id="wf_integrity_scan",
            action_name="ComfyUI Workflow Integrity & Link Audit",
            target_script_path=r"python scripts/playbooks/procedure_helpers.py audit_workflow_json",
            expected_outcome="Scan workflow JSONs for duplicate link IDs and missing nodes",
            last_execution_status="READY"
        )
        self.db.add_procedure(
            node_id="wf_stage_validated",
            action_name="Stage Validated ComfyUI Workflows",
            target_script_path=r"python scripts/playbooks/procedure_helpers.py notify_wf_staged",
            expected_outcome="Confirm zero link collision risks before dispatching queues",
            last_execution_status="READY"
        )
        self.db.add_procedure(
            node_id="wf_repair_warning",
            action_name="Workflow Link Corruption Alert",
            target_script_path=r"python scripts/playbooks/procedure_helpers.py notify_wf_repair",
            expected_outcome="Halt queue dispatch if JSON corruption detected",
            last_execution_status="READY"
        )

        # Relations for Workflow 4
        self.db.add_relation("wf_integrity_scan", "ON_SUCCESS_TRIGGER", "wf_stage_validated", "issues == 0")
        self.db.add_relation("wf_integrity_scan", "ON_FAILURE_FALLBACK", "wf_repair_warning", "issues > 0")

        # ---------------------------------------------------------------------
        # Workflow 5: Sanctuary Multi-Service Health & Orchestration
        # ---------------------------------------------------------------------
        self.db.add_procedure(
            node_id="sanctuary_port_audit",
            action_name="Sanctuary Multi-Service Mesh Audit",
            target_script_path=r"python scripts/playbooks/procedure_helpers.py sanctuary_health",
            expected_outcome="Audit live state of ComfyUI, ULM, KoboldCpp, and Ollama ports",
            last_execution_status="READY"
        )
        self.db.add_procedure(
            node_id="sanctuary_ready_signal",
            action_name="Sanctuary Service Mesh Operational",
            target_script_path=r"python scripts/playbooks/procedure_helpers.py notify_sanctuary_ready",
            expected_outcome="Confirm operational readiness of the local AI center",
            last_execution_status="READY"
        )

        # Relations for Workflow 5
        self.db.add_relation("sanctuary_port_audit", "ON_SUCCESS_TRIGGER", "sanctuary_ready_signal", "audit_complete == True")

        # ---------------------------------------------------------------------
        # Workflow 6: Render Metadata Extraction & Recipe Archiver
        # ---------------------------------------------------------------------
        self.db.add_procedure(
            node_id="render_meta_extract",
            action_name="Extract Latest Render Generation Metadata",
            target_script_path=r"python scripts/playbooks/procedure_helpers.py notify_render_archived",
            expected_outcome="Read PNG metadata, seed, and active LoRA stack strengths",
            last_execution_status="READY"
        )
        self.db.add_procedure(
            node_id="render_meta_archived",
            action_name="Log Generation Recipe to Cortex",
            target_script_path=r"python scripts/playbooks/procedure_helpers.py notify_render_archived",
            expected_outcome="Archive prompt parameters for reproducible training bakes",
            last_execution_status="READY"
        )

        # Relations for Workflow 6
        self.db.add_relation("render_meta_extract", "ON_SUCCESS_TRIGGER", "render_meta_archived", "meta_extracted == True")

        print("[+] Successfully seeded all 3 workflows into Procedural Graph tables!")

    def list_graph(self):
        """Displays all registered procedures and relational edges."""
        procs = self.db.list_procedures(limit=100)
        edges = self.db.list_relations(limit=100)

        print("\n🗺️  VESPERA PROCEDURAL GRAPH TOPOLOGY")
        print("=" * 80)
        print(f"Registered Procedures ({len(procs)} nodes):")
        print("-" * 80)
        for p in procs:
            status = p.get("last_execution_status") or "UNSET"
            print(f"  • [{p['node_id']}] {p['action_name']}")
            print(f"      Status:  {status} | Target: {p['target_script_path']}")
        
        print("\n" + "-" * 80)
        print(f"Relational Edges ({len(edges)} triplets):")
        print("-" * 80)
        for e in edges:
            cond = f" [Condition: {e['condition_logic']}]" if e.get("condition_logic") else ""
            print(f"  ({e['source_node_id']}) ──[{e['relation_type']}]──▶ ({e['target_node_id']}){cond}")
        print("=" * 80 + "\n")
