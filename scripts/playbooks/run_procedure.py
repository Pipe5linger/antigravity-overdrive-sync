import sys
import os
import argparse

# Enforce UTF-8 terminal piping on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
        sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)
    except AttributeError:
        pass

from core.procedural_runner import ProceduralRunner

def main():
    parser = argparse.ArgumentParser(description="Vespera ULM Procedural Graph Engine")
    subparsers = parser.add_subparsers(dest="subcommand", help="Sub-commands")

    # Command: list
    list_parser = subparsers.add_parser("list", help="List all registered procedural nodes and triplet edges")

    # Command: seed
    seed_parser = subparsers.add_parser("seed", help="Seed the 3 core production workflows")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Execute a procedure node or chain")
    run_parser.add_argument("node_id", help="The starting node ID to execute")
    run_parser.add_argument("--dry-run", action="store_true", help="Simulate execution without running underlying commands")
    run_parser.add_argument("--max-steps", type=int, default=10, help="Maximum number of node transitions in the chain")
    run_parser.add_argument("--single", action="store_true", help="Execute only the single specified node without following edges")

    args = parser.parse_args()

    runner = ProceduralRunner()

    if args.subcommand == "seed":
        runner.seed_production_workflows()
        runner.list_graph()
    elif args.subcommand == "list" or not args.subcommand:
        runner.list_graph()
    elif args.subcommand == "run":
        if args.single:
            runner.execute_node(args.node_id, dry_run=args.dry_run)
        else:
            runner.execute_chain(args.node_id, max_steps=args.max_steps, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
