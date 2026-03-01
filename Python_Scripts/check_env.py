"""
check_env.py — Pre-flight environment checker for FilePilot AI

Verifies:
  1. 'ollama' binary is available on PATH
  2. Ollama server is running at http://localhost:11434
  3. The 'llama3.2' model is pulled and available

Run standalone: python check_env.py
Also called automatically by 'python main.py organize' before live runs.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

import httpx
from rich.console import Console
from rich.table import Table

console = Console()

_OLLAMA_URL = "http://localhost:11434"
_REQUIRED_MODEL = "llama3.2"


def _check_ollama_binary() -> tuple[bool, str]:
    path = shutil.which("ollama")
    if path:
        return True, f"Found at: {path}"
    return False, "Not found on PATH. Install from https://ollama.com/download"


def _check_ollama_running() -> tuple[bool, str]:
    try:
        r = httpx.get(_OLLAMA_URL, timeout=3)
        if r.status_code == 200:
            return True, f"Reachable at {_OLLAMA_URL}"
        return False, f"Unexpected status {r.status_code} at {_OLLAMA_URL}"
    except Exception as exc:
        return False, f"Cannot connect to {_OLLAMA_URL} — run 'ollama serve' first. ({exc})"


def _check_model_available() -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if _REQUIRED_MODEL in result.stdout:
            return True, f"'{_REQUIRED_MODEL}' model is pulled and ready."
        return (
            False,
            f"'{_REQUIRED_MODEL}' not found. Run: ollama pull {_REQUIRED_MODEL}",
        )
    except FileNotFoundError:
        return False, "Cannot run 'ollama list' — binary not on PATH."
    except Exception as exc:
        return False, str(exc)


def run_env_check(quiet: bool = False) -> bool:
    """
    Run all environment checks and print a summary table.

    Args:
        quiet: If True suppress the table; only return pass/fail bool.

    Returns:
        True if all checks pass, False otherwise.
    """
    checks = [
        ("Ollama binary on PATH", _check_ollama_binary),
        ("Ollama server running", _check_ollama_running),
        (f"Model '{_REQUIRED_MODEL}' available", _check_model_available),
    ]

    results: list[tuple[str, bool, str]] = []
    all_ok = True

    for label, fn in checks:
        ok, detail = fn()
        results.append((label, ok, detail))
        if not ok:
            all_ok = False

    if not quiet:
        table = Table(
            title="[bold cyan]FilePilot AI — Environment Check[/bold cyan]",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Check", style="white")
        table.add_column("Status", justify="center")
        table.add_column("Details", style="dim")

        for label, ok, detail in results:
            status = "[bold green]✅ PASS[/bold green]" if ok else "[bold red]❌ FAIL[/bold red]"
            table.add_row(label, status, detail)

        console.print()
        console.print(table)

        if all_ok:
            console.print("\n[bold green]All checks passed! FilePilot AI is ready.[/bold green]\n")
        else:
            console.print(
                "\n[bold red]Some checks failed.[/bold red] "
                "Please fix the issues above before running [bold]organize[/bold].\n"
            )

    return all_ok


if __name__ == "__main__":
    ok = run_env_check(quiet=False)
    sys.exit(0 if ok else 1)
