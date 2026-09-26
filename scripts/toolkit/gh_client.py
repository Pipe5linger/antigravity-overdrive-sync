#!/usr/bin/env python3
"""
GitHub Operations Client
------------------------
Reusable maintainer tool for managing releases, assets, and repository metadata
using system git credentials. Eliminates scratch script generation.
"""

import sys
import os
import json
import subprocess
import urllib.request
import urllib.error
import argparse

REPO_DEFAULT = "Pipe5linger/antigravity-overdrive-sync"

def get_git_token(host="github.com") -> str:
    """Retrieve OAuth / PAT token from git credential helper."""
    try:
        proc = subprocess.Popen(['git', 'credential', 'fill'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        out, _ = proc.communicate(f"protocol=https\nhost={host}\n")
        creds = dict(line.split('=', 1) for line in out.strip().split('\n') if '=' in line)
        token = creds.get('password')
        if not token:
            raise ValueError("No token found in git credentials helper.")
        return token
    except Exception as e:
        sys.stderr.write(f"[ERROR] Failed to obtain git token: {e}\n")
        sys.exit(1)

def _get_headers(token: str) -> dict:
    return {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'ULM-Maintainer-Toolkit/1.0'
    }

def list_releases(repo: str = REPO_DEFAULT):
    """List all releases including drafts."""
    token = get_git_token()
    url = f"https://api.github.com/repos/{repo}/releases"
    req = urllib.request.Request(url, headers=_get_headers(token))
    with urllib.request.urlopen(req) as resp:
        releases = json.loads(resp.read().decode('utf-8'))
    return releases

def get_release(release_id_or_tag: str, repo: str = REPO_DEFAULT):
    """Get release details by ID or tag name."""
    token = get_git_token()
    if str(release_id_or_tag).isdigit():
        url = f"https://api.github.com/repos/{repo}/releases/{release_id_or_tag}"
    else:
        url = f"https://api.github.com/repos/{repo}/releases/tags/{release_id_or_tag}"
    req = urllib.request.Request(url, headers=_get_headers(token))
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

def upload_asset(release_id: int, file_path: str, repo: str = REPO_DEFAULT):
    """Upload a distribution file or binary to a specific release."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    filename = os.path.basename(file_path)
    token = get_git_token()
    upload_url = f"https://uploads.github.com/repos/{repo}/releases/{release_id}/assets?name={filename}"
    
    with open(file_path, "rb") as f:
        file_data = f.read()

    headers = _get_headers(token)
    headers['Content-Type'] = 'application/octet-stream'

    req = urllib.request.Request(upload_url, data=file_data, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        err = e.read().decode('utf-8', errors='ignore')
        if "already_exists" in err:
            print(f"[WARN] Asset '{filename}' already exists on release {release_id}.")
            return {"status": "exists", "name": filename}
        raise

def set_draft_status(release_id: int, draft: bool = False, repo: str = REPO_DEFAULT):
    """Toggle draft state of a release (e.g. publish)."""
    token = get_git_token()
    url = f"https://api.github.com/repos/{repo}/releases/{release_id}"
    payload = {"draft": draft}
    headers = _get_headers(token)
    headers['Content-Type'] = 'application/json'

    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='PATCH')
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

def main():
    parser = argparse.ArgumentParser(description="Maintainer GitHub CLI")
    subparsers = parser.add_subparsers(dest="command")

    # list
    subparsers.add_parser("list", help="List all releases")

    # info
    info_p = subparsers.add_parser("info", help="Get release info")
    info_p.add_argument("release_id", help="Release ID or tag name")

    # upload
    up_p = subparsers.add_parser("upload", help="Upload asset to release")
    up_p.add_argument("release_id", type=int, help="Release ID")
    up_p.add_argument("file_path", help="Path to asset file")

    # publish
    pub_p = subparsers.add_parser("publish", help="Publish a draft release")
    pub_p.add_argument("release_id", type=int, help="Release ID to publish")

    args = parser.parse_args()

    if args.command == "list":
        releases = list_releases()
        print(f"\n--- Releases for {REPO_DEFAULT} ({len(releases)} found) ---")
        for r in releases:
            status = "DRAFT" if r.get('draft') else "LIVE"
            print(f"ID: {r.get('id')} | Tag: {r.get('tag_name')} | Status: {status} | Name: {r.get('name')}")
            for a in r.get('assets', []):
                print(f"  -> Asset: {a.get('name')} ({a.get('size')} bytes)")
    elif args.command == "info":
        rel = get_release(args.release_id)
        print(json.dumps(rel, indent=2))
    elif args.command == "upload":
        res = upload_asset(args.release_id, args.file_path)
        print(f"[OK] Uploaded asset: {res.get('name')} (ID: {res.get('id')})")
    elif args.command == "publish":
        res = set_draft_status(args.release_id, draft=False)
        print(f"[OK] Published release {args.release_id}: {res.get('html_url')}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
