"""
main.py — Typer CLI entrypoint for FilePilot AI

Commands:
  organize  Scan a directory and use AI to move loose files.
  search    Query ChromaDB to find where your files went.

Usage:
  python main.py organize --path /your/folder
  python main.py organize --path /your/folder --dry-run
  python main.py search --query "tax documents"
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from check_env import run_env_check
from database import search_files
from models import MoveDecision
from organizer import ask_llm, execute_moves, get_file_meta
from scanner import scan_directory

app = typer.Typer(
    name="FilePilot AI",
    help="🗂️ AI-powered local file organizer using Llama 3.2 + ChromaDB.",
    add_completion=False,
)
console = Console()


# ── organize command ──────────────────────────────────────────────────────────


@app.command()
def organize(
    path: Path = typer.Option(
        ...,
        "--path",
        "-p",
        help="Root directory to organize.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview proposed moves without moving any files.",
    ),
) -> None:
    """Scan PATH and use AI to organize loose files into folders."""

    console.print(
        Panel.fit(
            "[bold cyan]FilePilot AI[/bold cyan] ✈️\n"
            f"[dim]Target directory:[/dim] {path}",
            border_style="cyan",
        )
    )

    # ── Environment check ─────────────────────────────────────────────────────
    if not dry_run:
        ok = run_env_check(quiet=True)
        if not ok:
            console.print(
                "\n[red bold]❌ Environment check failed.[/red bold] "
                "Run [bold]python check_env.py[/bold] for details.\n"
            )
            raise typer.Exit(code=1)

    # ── Scan ──────────────────────────────────────────────────────────────────
    console.print("\n[bold]Scanning directory…[/bold]")
    scan = scan_directory(path)
    console.print(f"  {scan.summary()}")

    if not scan.loose_files:
        console.print("\n[green]✓ Nothing to organize — no loose files found![/green]")
        raise typer.Exit()

    if dry_run:
        console.print(
            "\n[yellow]Dry-run mode:[/yellow] Ollama will not be called. "
            "Showing scanner results only.\n"
        )
        # In dry-run without Ollama we still show what *would* happen
        # by calling the LLM for proposals (skip env check fail)
        console.print(
            "[dim]Tip: Remove --dry-run to call the LLM and get real proposals.[/dim]"
        )
        # Simple table of loose files
        t = Table(show_header=True, header_style="bold magenta", show_lines=True)
        t.add_column("Loose File", style="white")
        t.add_column("Extension", style="cyan")
        t.add_column("Existing Folders Available", style="green")
        for f in scan.loose_files:
            t.add_row(
                f.name,
                f.suffix or "(none)",
                ", ".join(scan.existing_folders) or "—",
            )
        console.print(t)
        raise typer.Exit()

    # ── LLM reasoning loop ────────────────────────────────────────────────────
    console.print(
        f"\n[bold]Asking [cyan]llama3.2[/cyan] to categorize "
        f"{len(scan.loose_files)} file(s)…[/bold]\n"
    )

    decisions: list[tuple[Path, MoveDecision]] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task_id = progress.add_task("Processing…", total=len(scan.loose_files))

        for file_path in scan.loose_files:
            progress.update(task_id, description=f"Analyzing [cyan]{file_path.name}[/cyan]…")
            meta = get_file_meta(file_path)
            decision = ask_llm(meta, scan.existing_folders)
            if decision:
                decisions.append((file_path, decision))
            progress.advance(task_id)

    if not decisions:
        console.print("\n[red]No valid decisions were made. Check Ollama logs.[/red]")
        raise typer.Exit(code=1)

    # ── Execute or dry-run ───────────────────────────────────────────────────
    execute_moves(decisions, path, dry_run=False)


# ── search command ────────────────────────────────────────────────────────────


@app.command()
def search(
    query: str = typer.Option(
        ...,
        "--query",
        "-q",
        help="Natural language query, e.g. 'visa document' or 'Python scripts'.",
    ),
    limit: int = typer.Option(5, "--limit", "-n", help="Max results to show."),
) -> None:
    """Search ChromaDB with a natural language query to find moved files."""

    console.print(
        Panel.fit(
            f"[bold cyan]FilePilot AI Search[/bold cyan] 🔍\n"
            f"[dim]Query:[/dim] {query}",
            border_style="cyan",
        )
    )

    results = search_files(query, n_results=limit)

    if not results:
        console.print(
            "\n[yellow]No results found.[/yellow] "
            "Run [bold]python main.py organize[/bold] first to index some files."
        )
        raise typer.Exit()

    table = Table(
        title=f"\nTop {len(results)} result(s) for: \"{query}\"",
        show_header=True,
        header_style="bold magenta",
        show_lines=True,
    )
    table.add_column("File", style="white", no_wrap=True)
    table.add_column("New Location", style="green")
    table.add_column("Reason", style="dim")
    table.add_column("Score", style="cyan", justify="right")
    table.add_column("Moved At", style="dim", no_wrap=True)

    for r in results:
        table.add_row(
            r.get("filename", "?"),
            r.get("new_path", "?"),
            r.get("reason", "?"),
            str(r.get("relevance_score", "?")),
            r.get("timestamp", "?")[:19],  # trim microseconds
        )

    console.print(table)


# ── entry point ───────────────────────────────────────────────────────────────


if __name__ == "__main__":
    app()
