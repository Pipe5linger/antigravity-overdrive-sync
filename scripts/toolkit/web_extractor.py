#!/usr/bin/env python3
"""
Web & Conversation Extractor
----------------------------
Reusable utility to parse web content, Reddit threads, and Claude shared chats
without generating throwaway scratch scripts.
"""

import sys
import os
import json
import re
import urllib.request
import urllib.error
import argparse

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def extract_claude_share(url_or_uuid: str) -> dict:
    """Fetch structured chat messages from Claude share snapshot API."""
    match = re.search(r"([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})", url_or_uuid)
    if not match:
        raise ValueError("Invalid Claude share UUID or URL.")
    uuid = match.group(1)
    api_url = f"https://claude.ai/api/chat_snapshots/{uuid}?rendering_mode=messages&render_all_tools=true"
    
    req = urllib.request.Request(api_url, headers={
        'User-Agent': USER_AGENT,
        'Accept': 'application/json'
    })
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

def extract_reddit(url: str) -> dict:
    """Fetch post and comments from Reddit URL via JSON endpoint."""
    clean_url = url.split('?')[0].rstrip('/')
    json_url = f"{clean_url}.json"
    
    req = urllib.request.Request(json_url, headers={
        'User-Agent': 'ULM-Extractor/1.0 (Windows NT 10.0; Win64; x64)'
    })
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        
    post_data = data[0]['data']['children'][0]['data']
    comments_data = []
    if len(data) > 1:
        for c in data[1]['data']['children']:
            if c.get('kind') == 't1':
                comments_data.append({
                    "author": c['data'].get('author'),
                    "body": c['data'].get('body'),
                    "score": c['data'].get('score')
                })
                
    return {
        "title": post_data.get('title'),
        "author": post_data.get('author'),
        "selftext": post_data.get('selftext'),
        "url": post_data.get('url'),
        "comments": comments_data
    }

def main():
    parser = argparse.ArgumentParser(description="Web and Chat Extractor")
    parser.add_argument("url", help="Target URL (Claude share, Reddit, or web link)")
    parser.add_argument("-o", "--output", help="Optional output JSON file")
    args = parser.parse_args()

    url = args.url
    if "claude.ai/share" in url or re.match(r"^[0-9a-fA-F-]{36}$", url):
        data = extract_claude_share(url)
        print(f"[OK] Fetched Claude conversation: {len(data.get('chat_messages', []))} messages.")
    elif "reddit.com" in url:
        data = extract_reddit(url)
        print(f"[OK] Fetched Reddit post: '{data.get('title')}' with {len(data.get('comments', []))} comments.")
    else:
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode('utf-8', errors='ignore')
            data = {"url": url, "html": content[:5000]}
        print(f"[OK] Fetched web page ({len(data['html'])} chars preview).")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"[OK] Saved data to {args.output}")
    else:
        print("\n--- Summary ---")
        if "chat_messages" in data:
            for i, m in enumerate(data.get('chat_messages', [])[-3:]):
                sender = m.get('sender')
                txt = m.get('text', '') or str(m.get('content', ''))
                print(f"[{sender}]: {txt[:200]}...\n")
        elif "title" in data:
            print(f"Title: {data.get('title')}")
            print(f"Body: {(data.get('selftext') or '')[:300]}")

if __name__ == "__main__":
    main()
