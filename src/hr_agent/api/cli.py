"""
HR Agent CLI

Supports both single-query mode and interactive multi-turn conversations.
"""

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
import sys

from ..seed import seed_if_needed
from ..infrastructure.config import settings
from ..core.agent import HRAgent, run_agent

console = Console()


def run_interactive(user_email: str):
    """Run the agent in interactive multi-turn mode."""
    console.print(
        Panel.fit(
            f"[bold cyan]HR Agent Interactive Mode[/bold cyan]\n"
            f"User: [green]{user_email}[/green]\n"
            f"Type [bold]'exit'[/bold] or [bold]'quit'[/bold] to end the session.\n"
            f"Type [bold]'clear'[/bold] to start a new conversation.",
            title="Welcome",
        )
    )

    agent = HRAgent(user_email)

    while True:
        try:
            question = console.input("\n[bold green]You:[/bold green] ").strip()

            if not question:
                continue

            if question.lower() in ("exit", "quit"):
                console.print("[yellow]Goodbye![/yellow]")
                break

            if question.lower() == "clear":
                agent = HRAgent(user_email)  # New session
                console.print("[yellow]Started new conversation.[/yellow]")
                continue

            if question.lower() == "confirm":
                question = "confirm_action"
            elif question.lower() == "cancel":
                question = "cancel_action"

            with console.status("[cyan]Thinking...[/cyan]"):
                answer = agent.chat(question)

            console.print(f"\n[bold cyan]Agent:[/bold cyan] {answer}")

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Goodbye![/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def main():
    load_dotenv()
    seed_if_needed()

    # Check for interactive mode
    if len(sys.argv) == 2 and sys.argv[1] in ("-i", "--interactive"):
        run_interactive(settings.demo_user_email)
        return

    # Check for user override
    if len(sys.argv) >= 3 and sys.argv[1] in ("-u", "--user"):
        user_email = sys.argv[2]
        if len(sys.argv) == 3:
            # Interactive mode with custom user
            run_interactive(user_email)
            return
        elif len(sys.argv) == 4 and sys.argv[3] == "-i":
            run_interactive(user_email)
            return
        elif len(sys.argv) >= 4:
            question = " ".join(sys.argv[3:])
        else:
            console.print("[bold]Usage:[/bold]")
            console.print('  python -m hr_agent.cli "your question"')
            console.print("  python -m hr_agent.cli -i  (interactive mode)")
            console.print('  python -m hr_agent.cli -u email@example.com "question"')
            console.print(
                "  python -m hr_agent.cli -u email@example.com -i  (interactive with custom user)"
            )
            raise SystemExit(1)
    elif len(sys.argv) < 2:
        console.print("[bold]Usage:[/bold]")
        console.print('  python -m hr_agent.cli "your question"')
        console.print("  python -m hr_agent.cli -i  (interactive mode)")
        console.print('  python -m hr_agent.cli -u email@example.com "question"')
        console.print(
            "  python -m hr_agent.cli -u email@example.com -i  (interactive with custom user)"
        )
        raise SystemExit(1)
    else:
        user_email = settings.demo_user_email
        question = sys.argv[1]

    # Single query mode
    answer = run_agent(user_email, question)

    console.print(f"\n[bold cyan]User:[/bold cyan] {user_email}")
    console.print(f"[bold green]Q:[/bold green] {question}")
    console.print(f"[bold yellow]A:[/bold yellow] {answer}\n")


if __name__ == "__main__":
    main()
