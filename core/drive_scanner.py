import os
from pathlib import Path
from typing import List, Dict

class DriveHierarchyScanner:
    """Scans key workstation drive roots and generates a compact, structured tree mapping for ULM context."""
    
    DEFAULT_ROOTS = [
        r"D:\AI\Projects",
        r"D:\AI\Models",
        r"E:\_Sanctuary_Backups",
        r"E:\Media_Server",
        r"G:\My Drive",
        r"C:\Users\boben\.gemini\antigravity"
    ]

    def __init__(self, roots: List[str] = None):
        self.roots = roots or self.DEFAULT_ROOTS

    EXCLUDE_DIRS = {
        "node_modules", ".venv", "venv", "cache", ".git", "__pycache__", 
        "dist", "build", "pip", ".cache", "appdata", "temp", "tmp", 
        "$RECYCLE.BIN", "System Volume Information", "apps", "logs", 
        "obj", "bin", "site-packages", "wheels"
    }

    def scan_directory(self, root_path: str, max_depth: int = 2) -> str:
        p = Path(root_path)
        if not p.exists():
            return f"[DIR] {root_path} [Path not mounted/found]\n"
        
        tree_lines = [f"[ROOT] {p.resolve()}"]
        
        def _walk(current_path: Path, current_depth: int, prefix: str):
            if current_depth > max_depth:
                return
            
            try:
                entries = sorted(list(current_path.iterdir()), key=lambda x: (not x.is_dir(), x.name.lower()))
            except PermissionError:
                tree_lines.append(f"{prefix}|-- [Permission Denied]")
                return
            except Exception as e:
                tree_lines.append(f"{prefix}|-- [Error: {e}]")
                return

            # Filter out hidden or noise folders
            filtered = [
                e for e in entries 
                if not e.name.startswith(".") 
                and e.name.lower() not in self.EXCLUDE_DIRS
            ]

            count = len(filtered)
            for idx, entry in enumerate(filtered):
                is_last = (idx == count - 1)
                connector = "\\-- " if is_last else "|-- "
                sub_prefix = "    " if is_last else "|   "

                if entry.is_dir():
                    tree_lines.append(f"{prefix}{connector}[DIR] {entry.name}/")
                    if current_depth < max_depth:
                        _walk(entry, current_depth + 1, prefix + sub_prefix)
                else:
                    # Show key config / markdown / db files, skip bulk data
                    ext = entry.suffix.lower()
                    if ext in [".py", ".json", ".yaml", ".yml", ".db", ".bat", ".vbs", ".md", ".txt", ".safetensors", ".gguf", ".png", ".jpg"]:
                        size_str = f"({entry.stat().st_size / (1024*1024):.1f} MB)" if entry.stat().st_size > 1024*1024 else ""
                        tree_lines.append(f"{prefix}{connector}{entry.name} {size_str}".strip())

        _walk(p, 1, "")
        return "\n".join(tree_lines)

    def scan_all(self) -> str:
        sections = []
        for root in self.roots:
            depth = 2 if "Projects" in root or "Models" in root else 1
            sections.append(self.scan_directory(root, max_depth=depth))
        return "\n\n".join(sections)

if __name__ == "__main__":
    scanner = DriveHierarchyScanner()
    print(scanner.scan_all())
