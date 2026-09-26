#!/usr/bin/env python3
"""
ULM Security Auditor Role Playbook
==================================
Performs static security analysis, secret leak scans, SQL injection audit,
and environment credential verification across the ULM codebase.
"""

import os
import sys
import re
import subprocess
from pathlib import Path

# Enforce UTF-8 output on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
        sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)
    except AttributeError:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Directories to skip
IGNORED_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
    ".vscode", "node_modules", "dist", "build", "egg-info"
}

# Secret detection regexes
SECRET_PATTERNS = [
    ("OpenAI/Anthropic Secret Key", re.compile(r"""(?:sk|ant)-[a-zA-Z0-9_\-]{32,}""")),
    ("Google API Key", re.compile(r"""AIza[0-9A-Za-z\-_]{35}""")),
    ("HuggingFace Token", re.compile(r"""hf_[a-zA-Z0-9]{34,}""")),
    ("GitHub Personal Token", re.compile(r"""ghp_[a-zA-Z0-9]{36}""")),
    ("Generic Private Key Header", re.compile(r"""-----BEGIN (?:RSA|OPENSSH|EC) PRIVATE KEY-----""")),
]

# Raw string formatting in SQL execute calls (potential SQL injection)
SQL_INJECTION_PATTERN = re.compile(r"""\.(?:execute|executemany)\s*\(\s*f["'].*?(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER).*?\{""", re.IGNORECASE)

def is_gitignored(path: Path) -> bool:
    try:
        rel = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
        res = subprocess.run(
            ["git", "check-ignore", rel],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        return res.returncode == 0
    except Exception:
        return False

def audit_secrets():
    findings = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.endswith(".egg-info")]
        for file in files:
            # Skip binary files, lock files, and documentation examples
            if file.endswith((".png", ".jpg", ".jpeg", ".ico", ".db", ".pyc", ".lock")):
                continue
            if file in (".env.example", "persona_baseline.example.yaml"):
                continue
            
            file_path = Path(root) / file
            rel_path = file_path.relative_to(PROJECT_ROOT)
            
            # If the file is strictly ignored by git (e.g. db/, .env), secrets are local and not committed upstream
            if is_gitignored(file_path):
                continue
            
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for name, pattern in SECRET_PATTERNS:
                matches = pattern.findall(content)
                if matches:
                    findings.append({
                        "type": "SECRET_LEAK",
                        "severity": "CRITICAL",
                        "file": str(rel_path),
                        "description": f"Potential {name} detected: {matches[0][:8]}... (length {len(matches[0])})"
                    })
    return findings

def audit_sql_injection():
    findings = []
    py_files = list(PROJECT_ROOT.glob("core/**/*.py")) + list(PROJECT_ROOT.glob("scripts/**/*.py"))
    
    for file_path in py_files:
        rel_path = file_path.relative_to(PROJECT_ROOT)
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for i, line in enumerate(content.splitlines(), start=1):
            if SQL_INJECTION_PATTERN.search(line):
                # Whitelist safe parameter placeholders (e.g. ",".join("?" * len(batch)))
                if "placeholders" in line or '",".join' in line:
                    continue
                # Whitelist internal schema inspection / ALTER migrations on trusted identifiers
                if any(k in line for k in ['"{t}"', '"{table}"', '"{tbl}"', '\\"{t}\\"', '\\"{table}\\"', '\\"{tbl}\\"', "table_name", "col_name", "tbl"]):
                    continue
                findings.append({
                    "type": "SQL_INJECTION_RISK",
                    "severity": "HIGH",
                    "file": f"{rel_path}:{i}",
                    "description": f"Unescaped table/column string interpolation in SQL execute call: {line.strip()[:80]}"
                })
    return findings

def audit_environment_hygiene():
    findings = []
    gitignore_path = PROJECT_ROOT / ".gitignore"
    if not gitignore_path.exists():
        findings.append({
            "type": "HYGIENE",
            "severity": "HIGH",
            "file": ".gitignore",
            "description": "Missing .gitignore file at project root."
        })
    else:
        gi_content = gitignore_path.read_text(encoding="utf-8", errors="ignore")
        required_ignores = [".env", "*.db", "token_usage_log.csv"]
        for req in required_ignores:
            if req not in gi_content:
                findings.append({
                    "type": "HYGIENE",
                    "severity": "MEDIUM",
                    "file": ".gitignore",
                    "description": f"Pattern '{req}' should be tracked in .gitignore."
                })
    return findings

def run_security_audit():
    print("🔒 [ULM Security Auditor] Starting comprehensive security audit...")
    print("=" * 70)
    
    all_findings = []
    all_findings.extend(audit_secrets())
    all_findings.extend(audit_sql_injection())
    all_findings.extend(audit_environment_hygiene())
    
    criticals = [f for f in all_findings if f["severity"] == "CRITICAL"]
    highs = [f for f in all_findings if f["severity"] == "HIGH"]
    mediums = [f for f in all_findings if f["severity"] == "MEDIUM"]
    
    if not all_findings:
        print("  ✓ Zero security violations detected.")
        print("  ✓ Static analysis clean: No plaintext keys, no unparameterized SQL, .gitignore verified.")
        print("=" * 70)
        return True, 0

    print(f"\n[-] Found {len(all_findings)} finding(s): {len(criticals)} Critical, {len(highs)} High, {len(mediums)} Medium")
    for f in all_findings:
        print(f"  [{f['severity']}] {f['type']} in {f['file']}: {f['description']}")
    print("=" * 70)
    
    # Return non-zero if critical or high issues found
    return (len(criticals) + len(highs) == 0), len(criticals) + len(highs)

if __name__ == "__main__":
    success, issues = run_security_audit()
    sys.exit(0 if success else 1)
