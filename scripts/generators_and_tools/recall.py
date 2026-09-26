#!/usr/bin/env python3
"""
ULM CLI RAG Semantic Recall Tool
Query long-term conversational memory directly from the terminal or subagents.
Usage: python recall.py "how did we set up comfyui loras?" [--limit 5] [--min-sim 0.4]
"""

import sys
import os
import argparse
import json
from pathlib import Path

# Enforce UTF-8 output on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
    except AttributeError:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.database import ULMDatabase
from core.engine import ULMEngine
from core.consolidator import MemoryConsolidator

def main():
    parser = argparse.ArgumentParser(description="Query Vespera ULM Semantic Long-Term Memory (RAG)")
    parser.add_argument("query", nargs="+", help="Natural language query string")
    parser.add_argument("--limit", "-k", type=int, default=5, help="Number of results to return (default: 5)")
    parser.add_argument("--min-similarity", "-s", type=float, default=0.4, help="Minimum cosine similarity threshold (default: 0.4)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON results")
    args = parser.parse_args()

    query_str = " ".join(args.query)
    
    engine = ULMEngine()
    db_path = str(Path(engine.target_yaml).with_suffix(".db"))
    db = ULMDatabase(db_path)
    db.initialize_db()

    consolidator = MemoryConsolidator(db)
    query_vector = consolidator._get_embedding(query_str)
    
    if not query_vector:
        print("[-] Could not generate embedding for query. Ensure Ollama or local vector provider is accessible.", file=sys.stderr)
        sys.exit(1)

    results = db.semantic_recall(query_vector=query_vector, limit=args.limit, min_similarity=args.min_similarity)

    if args.json:
        print(json.dumps({"query": query_str, "count": len(results), "results": results}, indent=2, ensure_ascii=False))
        return

    print(f"\n🧠 Vespera Semantic Memory Recall | Query: '{query_str}'")
    print("=" * 70)
    
    if not results:
        print(f"[*] No memory matches found above similarity threshold ({args.min_similarity}).")
        print("    Try lowering the threshold with --min-sim 0.3 or running a text search with: ulm search -q 'keyword'")
        return

    for i, r in enumerate(results, 1):
        score_pct = int(r["similarity"] * 100)
        tag = f" [{r['project_tag']}]" if r.get("project_tag") else ""
        print(f"\n[{i}] [Match: {score_pct}% | Category: {r['category'].upper()}{tag}]")
        print(f"    {r['fact']}")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
