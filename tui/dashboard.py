import os
import sys
import msvcrt
import sqlite3
import datetime
import time
from pathlib import Path
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.status import Status

# Import core components
from core.engine import ULMEngine
from core.database import ULMDatabase
from core.adapters import BlendedMarkdownAdapter

class ULMTUIDashboard:
    def __init__(self):
        self.console = Console()
        self.engine = ULMEngine()
        self.db_path = str(Path(self.engine.target_yaml).with_suffix(".db"))
        self.db = ULMDatabase(self.db_path)
        self.logs_buffer = ["Dashboard loaded. Ready."]

    def add_log(self, message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.logs_buffer.append(f"[{timestamp}] {message}")
        if len(self.logs_buffer) > 10:
            self.logs_buffer.pop(0)

    def get_db_stats(self):
        stats = {
            "path": self.db_path,
            "size": "0 KB",
            "journal_mode": "UNKNOWN",
            "total_sessions": 0,
            "total_messages": 0,
            "total_facts": 0,
            "total_preferences": 0
        }
        
        # Calculate database file size
        if os.path.exists(self.db_path):
            size_bytes = os.path.getsize(self.db_path)
            stats["size"] = f"{size_bytes / 1024:.2f} KB"

        try:
            with self.db.get_connection() as conn:
                c = conn.cursor()
                
                # Get journal mode
                c.execute("PRAGMA journal_mode;")
                stats["journal_mode"] = c.fetchone()[0].upper()
                
                # Get session counts
                c.execute("SELECT COUNT(*) FROM sessions;")
                stats["total_sessions"] = c.fetchone()[0]
                
                # Get message counts
                c.execute("SELECT COUNT(*) FROM messages;")
                stats["total_messages"] = c.fetchone()[0]
                
                # Get facts count
                c.execute("SELECT COUNT(*) FROM facts;")
                stats["total_facts"] = c.fetchone()[0]
                
                # Get preferences count
                c.execute("SELECT COUNT(*) FROM preferences;")
                stats["total_preferences"] = c.fetchone()[0]
        except Exception as e:
            self.add_log(f"Error querying database stats: {e}")
            
        return stats

    def draw_header(self):
        title = Text("🔮 VESPERA ULM PIPELINE CONTROL CENTER 🔮", style="bold magenta")
        subtitle = Text("Universal Local Memory Sync Engine • Interactive TUI", style="cyan")
        header_text = Text.assemble(title, "\n", subtitle)
        return Panel(Align.center(header_text), border_style="bold purple")

    def draw_stats_panel(self, stats):
        table = Table(show_header=False, expand=True, box=None)
        table.add_column("Property", style="bold yellow")
        table.add_column("Value", style="white")

        table.add_row("Database File", stats["path"])
        table.add_row("Database Size", stats["size"])
        table.add_row("SQLite Journal Mode", stats["journal_mode"])
        table.add_row("Active Sessions", str(stats["total_sessions"]))
        table.add_row("Synced Messages", str(stats["total_messages"]))
        table.add_row("Extracted Facts", str(stats["total_facts"]))
        table.add_row("Preferences Stored", str(stats["total_preferences"]))

        return Panel(table, title="[bold cyan]Database Statistics[/bold cyan]", border_style="cyan")

    def draw_menu_panel(self):
        menu_text = Text()
        menu_text.append("[S] ", style="bold green")
        menu_text.append("Trigger ULM Pipeline Sync\n", style="white")
        menu_text.append("[B] ", style="bold green")
        menu_text.append("Backup SQLite DB to YAML File\n", style="white")
        menu_text.append("[D] ", style="bold green")
        menu_text.append("List Stored Memory Facts\n", style="white")
        menu_text.append("[L] ", style="bold green")
        menu_text.append("Show Recent Synced Messages\n", style="white")
        menu_text.append("[P] ", style="bold green")
        menu_text.append("List Developer Profile Metrics\n", style="white")
        menu_text.append("[C] ", style="bold green")
        menu_text.append("Configure System Settings\n", style="white")
        menu_text.append("[H] ", style="bold green")
        menu_text.append("Rule Sync (HAMI Compile to .clinerules)\n", style="white")
        menu_text.append("[Q] ", style="bold red")
        menu_text.append("Exit Control Center", style="white")

        return Panel(menu_text, title="[bold yellow]Available Commands[/bold yellow]", border_style="yellow")

    def draw_logs_panel(self):
        logs_text = Text()
        for log in self.logs_buffer:
            logs_text.append(f"{log}\n", style="bright_black" if "Ready" in log else "green")
        return Panel(logs_text, title="[bold green]Event Terminal Logs[/bold green]", border_style="green")

    def render_dashboard(self):
        self.console.clear()
        stats = self.get_db_stats()
        
        # Draw header
        self.console.print(self.draw_header())
        
        # Display side-by-side or stacked grid depending on width
        self.console.print(self.draw_stats_panel(stats))
        self.console.print(self.draw_menu_panel())
        self.console.print(self.draw_logs_panel())
        
        self.console.print(Text("\n[Instructions] Press any option key to execute.", style="italic magenta"))

    def trigger_sync(self):
        self.console.print("\n[bold green]🚀 Launching Sync Process...[/bold green]")
        self.add_log("Starting pipeline parsing stage (Extract & Transform)...")
        
        try:
            from parsers.antigravity import AntigravityParser
            from injectors.gemini_md import GeminiMdInjector
            
            # Initialize parser/injector
            log_parser = AntigravityParser()
            memory_injector = GeminiMdInjector()
            
            with self.console.status("[bold green]Importing transcript logs...[/bold green]", spinner="dots"):
                new_logs = log_parser.fetch_new_logs()
                if new_logs:
                    synced_s, synced_m = self.db.import_raw_logs(new_logs)
                    self.add_log(f"Staged {synced_s} sessions, {synced_m} messages.")
                else:
                    self.add_log("ETL Complete: No new session modifications detected.")
                    
            with self.console.status("[bold green]Reinjecting memories...[/bold green]", spinner="dots"):
                success = memory_injector.inject(self.db, dry_run=False)
                if success:
                    self.add_log("ULM Sync pipeline executed and committed successfully!")
                else:
                    self.add_log("ULM Injector stage encountered failures.")
        except Exception as e:
            self.add_log(f"Error during sync pipeline: {e}")

    def trigger_rule_sync(self):
        self.console.print("\n[bold green]🚀 Compiling HAMI system prompt to .clinerules...[/bold green]")
        self.add_log("Starting rule compilation...")
        try:
            from injectors.cline_rules import ClineRulesInjector
            injector = ClineRulesInjector()
            if injector.inject(self.db):
                self.add_log("Successfully compiled rules to .clinerules.")
            else:
                self.add_log("Failed to compile rules.")
        except Exception as e:
            self.add_log(f"Error compiling rules: {e}")

    def trigger_backup(self):
        self.console.print("\n[bold green]📦 Backing up database state to YAML...[/bold green]")
        self.add_log("Building monolithic YAML snapshot from SQLite...")
        
        try:
            import yaml
            chats = {}
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT session_id, updated_at, topics, summary FROM sessions")
                sessions = c.fetchall()
                
                for s in sessions:
                    session_id = s["session_id"]
                    c.execute("SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,))
                    msgs = c.fetchall()
                    
                    log_entries = [{"role": m["role"], "content": m["content"], "created_at": m["created_at"]} for m in msgs]
                    chats[session_id] = {
                        "last_mutated": s["updated_at"],
                        "log": log_entries
                    }
                    if s["summary"]:
                        chats[session_id]["summary"] = s["summary"]
                        
            yaml_state = {
                "metadata": {
                    "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "total_chats": len(sessions)
                },
                "chats": chats
            }
            
            success = self.engine.commit_atomic_write(yaml_state)
            if success:
                self.add_log(f"Database backed up to YAML file successfully!")
            else:
                self.add_log("Failed to write to YAML backup.")
        except Exception as e:
            self.add_log(f"Backup failed: {e}")

    def view_facts(self):
        self.console.clear()
        self.console.print(Panel(Align.center(Text("🧠 MEMORY CORE FACTS DATABASE 🧠", style="bold yellow")), border_style="yellow"))
        
        table = Table(expand=True)
        table.add_column("Fact ID", style="cyan", width=12)
        table.add_column("Fact", style="white")
        table.add_column("Category", style="magenta")
        table.add_column("Confidence", style="green")
        table.add_column("Last Sync Time", style="blue")

        try:
            with self.db.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT fact_id, fact, category, confidence, last_seen FROM facts")
                rows = c.fetchall()
                for r in rows:
                    table.add_row(r[0], r[1], r[2], f"{r[3]:.2f}", r[4])
        except Exception as e:
            self.console.print(f"[-] Error reading facts: {e}", style="red")

        self.console.print(table)
        self.console.print("\n[bold green]Press any key to return to Dashboard...[/bold green]")
        msvcrt.getch()

    def view_messages(self):
        self.console.clear()
        self.console.print(Panel(Align.center(Text("💬 RECENT SYNCED MESSAGES 💬", style="bold green")), border_style="green"))
        
        table = Table(expand=True)
        table.add_column("Session ID", style="cyan", width=12)
        table.add_column("Role", style="magenta", width=10)
        table.add_column("Message Content", style="white")
        table.add_column("Timestamp", style="blue")

        try:
            results = self.db.get_recent_context(limit=10)
            for r in results:
                # Truncate content for readability
                content = r[2]
                if len(content) > 80:
                    content = content[:77] + "..."
                # Strip raw request markers for TUI display
                content = content.replace("<USER_REQUEST>", "").replace("</USER_REQUEST>", "")
                table.add_row(r[0], r[1], content, r[3])
        except Exception as e:
            self.console.print(f"[-] Error reading context: {e}", style="red")

        self.console.print(table)
        self.console.print("\n[bold green]Press any key to return to Dashboard...[/bold green]")
        msvcrt.getch()

    def view_profile(self):
        self.console.clear()
        self.console.print(Panel(Align.center(Text("👤 DEVELOPER PROGRESS PROFILE 👤", style="bold green")), border_style="green"))
        
        table = Table(expand=True)
        table.add_column("Category", style="cyan")
        table.add_column("Name", style="yellow")
        table.add_column("Description", style="white", ratio=3)
        table.add_column("Confidence", style="green", width=12)
        table.add_column("Freq", style="magenta", width=6)
        table.add_column("Last Observed", style="blue", width=20)

        try:
            profile = self.db.get_developer_profile()
            for r in profile:
                conf_str = f"{r['confidence'] * 100:.1f}%" if r['confidence'] else "N/A"
                last_seen_str = r['last_seen'].split(".")[0] if r['last_seen'] else "N/A"
                table.add_row(r['category'].upper(), r['name'], r['description'], conf_str, str(r['frequency']), last_seen_str)
        except Exception as e:
            self.console.print(f"[-] Error reading developer profile: {e}", style="red")

        self.console.print(table)
        self.console.print("\n[bold green]Press any key to return to Dashboard...[/bold green]")
        msvcrt.getch()

    def configure_settings(self):
        import requests
        
        while True:
            self.console.clear()
            self.console.print(Panel(Align.center(Text("⚙️ SYSTEM CONFIGURATION SETTINGS ⚙️", style="bold yellow")), border_style="yellow"))
            
            # Read current values
            provider = self.db.get_preference("llm_provider", "local_ollama")
            model = self.db.get_preference("llm_model", "qwen2.5-coder:14b")
            endpoint = self.db.get_preference("ollama_endpoint", "http://localhost:11434")
            gemini_key = self.db.get_preference("gemini_api_key", "")
            
            mask_key = f"{gemini_key[:4]}...{gemini_key[-4:]}" if len(gemini_key) > 8 else ("Set" if gemini_key else "Not Set")
            
            table = Table(expand=True, box=None)
            table.add_column("Key", style="bold cyan")
            table.add_column("Current Value", style="white")
            table.add_column("Command Option", style="bold green")
            
            table.add_row("LLM Provider", provider.upper(), "[1] Toggle Provider (Ollama / Gemini)")
            table.add_row("Active LLM Model", model, "[2] Change Active Model")
            table.add_row("Ollama Endpoint", endpoint, "[3] Change Ollama Endpoint URL")
            table.add_row("Gemini API Key", mask_key, "[4] Change Gemini API Key")
            
            self.console.print(table)
            self.console.print("\n[bold yellow]Available Commands:[/bold yellow]")
            self.console.print("  [1-4] Edit respective settings")
            self.console.print("  [T]   Detect local Ollama models")
            self.console.print("  [Q]   Return to Main Dashboard")
            
            char = msvcrt.getch()
            try:
                cmd = char.decode('utf-8').lower()
            except UnicodeDecodeError:
                continue
                
            if cmd == 'q':
                break
            elif cmd == '1':
                new_provider = "cloud_gemini" if provider == "local_ollama" else "local_ollama"
                self.db.set_preference("llm_provider", new_provider)
                self.add_log(f"Changed provider to {new_provider}")
            elif cmd == '2':
                self.console.print("\nEnter new active model identifier (e.g. qwen2.5-coder:14b, gemini-1.5-flash): ", style="bold green", end="")
                new_model = input().strip()
                if new_model:
                    self.db.set_preference("llm_model", new_model)
                    self.add_log(f"Set model path to: {new_model}")
            elif cmd == '3':
                self.console.print("\nEnter new Ollama Endpoint URL (default http://localhost:11434): ", style="bold green", end="")
                new_url = input().strip()
                if new_url:
                    self.db.set_preference("ollama_endpoint", new_url)
                    self.add_log(f"Set Ollama endpoint to: {new_url}")
            elif cmd == '4':
                self.console.print("\nEnter new Gemini API Key: ", style="bold green", end="")
                new_key = input().strip()
                if new_key:
                    self.db.set_preference("gemini_api_key", new_key)
                    self.add_log("Successfully updated cloud API credential.")
            elif cmd == 't':
                self.console.print("\n[*] Querying local Ollama instance tags...", style="cyan")
                try:
                    url = f"{endpoint.rstrip('/')}/api/tags"
                    res = requests.get(url, timeout=10)
                    if res.status_code == 200:
                        models = [m['name'] for m in res.json().get('models', [])]
                        self.console.print("\nDetected local models:", style="bold green")
                        for idx, m_name in enumerate(models):
                            self.console.print(f"  [{idx + 1}] {m_name}")
                        self.console.print("\nSelect number to set model, or press any other key to abort: ", style="yellow", end="")
                        selection_char = msvcrt.getch()
                        try:
                            sel_idx = int(selection_char.decode('utf-8')) - 1
                            if 0 <= sel_idx < len(models):
                                self.db.set_preference("llm_model", models[sel_idx])
                                self.add_log(f"Selected Ollama model: {models[sel_idx]}")
                        except:
                            pass
                    else:
                        self.console.print(f"[-] Ollama returned error: {res.status_code}", style="bold red")
                        time.sleep(2)
                except Exception as e:
                    self.console.print(f"[-] Failed to reach Ollama: {e}", style="bold red")
                    time.sleep(2)

    def start(self):
        # Auto-initialize DB schema just in case
        self.db.initialize_db()
        
        while True:
            self.render_dashboard()
            char = msvcrt.getch()
            try:
                key = char.decode('utf-8').lower()
            except UnicodeDecodeError:
                continue

            if key == 's':
                self.trigger_sync()
                time.sleep(1.5)
            elif key == 'b':
                self.trigger_backup()
                time.sleep(1.5)
            elif key == 'd':
                self.view_facts()
            elif key == 'l':
                self.view_messages()
            elif key == 'p':
                self.view_profile()
            elif key == 'c':
                self.configure_settings()
            elif key == 'h':
                self.trigger_rule_sync()
                time.sleep(1.5)
            elif key == 'q':
                self.console.print("\n[bold magenta]Exiting Vespera Control Center. Keep the momentum high. 🚀[/bold magenta]\n")
                break
