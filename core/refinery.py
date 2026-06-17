from pathlib import Path
from core.utils import atomic_write

class MemoryRefinery:
    def __init__(self, vault_dir=None):
        self.vault_dir = Path(vault_dir or ".") / ".vespera_memory"

    def update_memory_file(self, filename, new_content):
        file_path = self.vault_dir / filename
        self.vault_dir.mkdir(parents=True, exist_ok=True)

        if filename == "developer_profile.md":
            if "# 👤 DEVELOPER COGNITIVE PROFILE" not in new_content:
                new_content = "# 👤 DEVELOPER COGNITIVE PROFILE\n\n" + new_content
        elif filename == "current_context.md":
            if "# 📍 ACTIVE WORK BREADCRUMBS" not in new_content:
                new_content = "# 📍 ACTIVE WORK BREADCRUMBS\n\n" + new_content

        if filename in ["project_ledger.md", "post_mortems.md"]:
            lines = new_content.splitlines()
            if len(lines) > 500:
                header = lines[0] if lines[0].startswith("#") else ""
                content_lines = lines[1:] if header else lines
                truncated_lines = content_lines[-499:] if header else content_lines[-500:]
                if header:
                    new_content = header + "\n" + "\n".join(truncated_lines)
                else:
                    new_content = "\n".join(truncated_lines)

        atomic_write(file_path, new_content)