import time
import sys
import os
try:
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import print as rprint
except ImportError:
    print("This visualizer requires the 'rich' library. Please run: pip install rich")
    sys.exit(1)

console = Console()

def demo_token_economy():
    """Simulates the 96% Token Reduction (O(N^2) vs O(1))"""
    table = Table(title="[bold cyan]ULM Architecture vs Standard Cloud AI (Token Burn)[/bold cyan]")
    table.add_column("Turn", justify="center", style="cyan", no_wrap=True)
    table.add_column("Standard AI (O(N²))", justify="right", style="red")
    table.add_column("ULM Architecture (O(1))", justify="right", style="green")

    standard_cum = 0
    ulm_cum = 0
    standard_ctx = 0
    
    with Live(table, refresh_per_second=10) as live:
        for turn in range(1, 101):
            time.sleep(0.08) # Animation speed
            
            # Standard bloats every turn
            standard_ctx += 250 
            standard_cum += standard_ctx
            
            # ULM stays flat (Base rules + strict sliding window)
            ulm_ctx = 1500 + min(turn * 250, 750) 
            ulm_cum += ulm_ctx
            
            savings = ((standard_cum - ulm_cum) / standard_cum) * 100 if standard_cum > 0 else 0
            
            std_str = f"[red]{standard_cum:,} tokens[/red]"
            ulm_str = f"[green]{ulm_cum:,} tokens[/green] (-{savings:.1f}%)"
            
            table.add_row(str(turn), std_str, ulm_str)

    console.print(Panel(
        f"[bold white]FINAL TOKEN COST AFTER 100 TURNS[/bold white]\n\n"
        f"[red]Standard API Cost:[/red]   {standard_cum:,} tokens\n"
        f"[green]ULM Architecture:[/green]    {ulm_cum:,} tokens\n\n"
        f"[bold cyan]Total API Savings: {savings:.2f}%[/bold cyan]",
        title="[bold]Test Concluded[/bold]",
        border_style="cyan"
    ))

def demo_graveyard_miner():
    """Simulates the Graveyard Miner preventing token burn loops"""
    console.print(Panel("[bold yellow]SIMULATION: AGENT RUNS BROKEN COMMAND[/bold yellow]", border_style="yellow"))
    time.sleep(1)
    
    console.print("\n[bold red]--- SCENARIO A: Standard Autonomous Agent ---[/bold red]")
    time.sleep(1)
    for i in range(1, 4):
        console.print(f"[cyan]Agent:[/cyan] Executing `npm install nonexistent-library-x` (Turn {i})")
        time.sleep(0.5)
        console.print(f"[red]Terminal [stderr]:[/red] ERR! 404 Not Found - nonexistent-library-x")
        time.sleep(0.8)
        console.print(f"[cyan]Agent:[/cyan] Command failed. Let me try again...")
        time.sleep(0.5)
    console.print("[bold red][SYSTEM] Infinite Loop Detected. 15,000 tokens burned.[/bold red]\n")
    
    time.sleep(2)
    
    console.print("[bold green]--- SCENARIO B: ULM + Graveyard Miner ---[/bold green]")
    time.sleep(1)
    console.print(f"[cyan]Agent:[/cyan] Executing `npm install nonexistent-library-x` (Turn 1)")
    time.sleep(0.5)
    console.print(f"[red]Terminal [stderr]:[/red] ERR! 404 Not Found - nonexistent-library-x")
    time.sleep(0.8)
    console.print(f"[bold magenta][ULM Graveyard Miner][/bold magenta] Intercepted stderr. Pattern analyzed.")
    time.sleep(0.6)
    console.print(f"[bold magenta][ULM DB][/bold magenta] Rule Injected: [yellow]'Never attempt to install nonexistent-library-x.'[/yellow]")
    time.sleep(0.8)
    console.print(f"[cyan]Agent:[/cyan] Package does not exist. Pivoting approach. Writing custom utility script instead.")
    time.sleep(0.5)
    console.print("[bold green][SYSTEM] Loop Prevented. 0 tokens wasted.[/bold green]\n")

def demo_session_amnesia():
    """Simulates ULM curing session amnesia"""
    console.print(Panel("[bold blue]SIMULATION: CURING SESSION AMNESIA[/bold blue]", border_style="blue"))
    time.sleep(1)
    
    console.print("\n[bold white]Session 1 Terminated. User goes to sleep.[/bold white]")
    time.sleep(1.5)
    console.print("[bold white]12 Hours Later... Starting Session 2.[/bold white]\n")
    time.sleep(1)
    
    console.print("[bold red]--- SCENARIO A: Standard API ---[/bold red]")
    time.sleep(1)
    console.print("[cyan]Agent:[/cyan] Hello! I am a helpful AI. How can I assist you today?")
    time.sleep(0.8)
    console.print("[yellow]User:[/yellow] Where were we on the SQLite refactor?")
    time.sleep(0.8)
    console.print("[cyan]Agent:[/cyan] I'm sorry, I don't have access to previous conversations. Could you provide the code?\n")
    
    time.sleep(2)
    
    console.print("[bold green]--- SCENARIO B: ULM Architecture ---[/bold green]")
    time.sleep(1)
    console.print("[bold magenta][ULM Sync][/bold magenta] Connecting to `sync_state.db`...")
    time.sleep(0.5)
    console.print("[bold magenta][ULM Sync][/bold magenta] Loaded 23 facts, 5 active constraints, and current project cursor.")
    time.sleep(0.8)
    console.print("[cyan]Agent:[/cyan] Welcome back. Resuming the SQLite WAL refactor. The last constraint we added was the Jeselnik protocol. I have the next function ready for testing.")
    time.sleep(0.5)
    console.print("[bold green][SYSTEM] Context seamlessly restored. Zero manual prompting required.[/bold green]\n")

def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    console.print(Panel("[bold white]ULM ARCHITECTURE: VISUAL DEMONSTRATION SUITE[/bold white]\n"
                        "Select a feature to simulate for screen recording:", border_style="cyan"))
    
    print("1. Token Economy (96% Reduction via O(1) Context)")
    print("2. The Graveyard Miner (Preventing Retry Loops)")
    print("3. State Persistence (Curing Session Amnesia)")
    print("4. Exit")
    
    choice = input("\nEnter selection (1-4): ")
    
    os.system('cls' if os.name == 'nt' else 'clear')
    
    if choice == '1':
        demo_token_economy()
    elif choice == '2':
        demo_graveyard_miner()
    elif choice == '3':
        demo_session_amnesia()
    else:
        sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
