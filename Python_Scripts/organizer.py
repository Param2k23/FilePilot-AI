"""
organizer.py — LLM reasoning engine + file mover for FilePilot AI

Responsibilities:
  1. Extract file metadata (name, extension, first 500 bytes preview)
  2. Build a structured prompt for the local Llama 3.2 model via Ollama
  3. Parse and validate the LLM's JSON response using Pydantic (retries x3)
  4. Present a Rich table in dry-run mode, or execute moves via shutil
  5. Handle filename collisions by appending a short hash
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
import uuid
from pathlib import Path

import ollama
from rich.console import Console
from rich.table import Table

from database import store_move
from models import FileRecord, MoveDecision

console = Console()

_MODEL = "llama3.2"
_MAX_RETRIES = 3
_PREVIEW_BYTES = 500


# ── File metadata ─────────────────────────────────────────────────────────────


def get_file_meta(path: Path) -> dict:
    """
    Extract basic metadata and a plain-text preview from *path*.

    Args:
        path: Absolute path to the file.

    Returns:
        Dict with keys: filename, extension, size_bytes, preview.
    """
    preview = ""
    try:
        raw = path.read_bytes()[:_PREVIEW_BYTES]
        preview = raw.decode("utf-8", errors="replace").strip()
    except Exception:
        preview = "<binary or unreadable content>"

    return {
        "filename": path.name,
        "extension": path.suffix.lower(),
        "size_bytes": path.stat().st_size,
        "preview": preview,
    }


# ── Prompt builder ────────────────────────────────────────────────────────────


def build_prompt(file_meta: dict, existing_folders: list[str]) -> str:
    """
    Construct the LLM prompt with few-shot examples.

    Args:
        file_meta: Output of get_file_meta().
        existing_folders: Current subfolder names in the root directory.

    Returns:
        A complete prompt string.
    """
    folders_str = (
        ", ".join(f'"{f}"' for f in existing_folders)
        if existing_folders
        else "none yet"
    )

    return f"""You are an expert file organizer. Your job is to decide where a loose file should be moved.

## Existing folders (preferred destinations)
{folders_str}

## File to categorize
- Filename : {file_meta['filename']}
- Extension: {file_meta['extension']}
- Size     : {file_meta['size_bytes']} bytes
- Content preview:
```
{file_meta['preview']}
```

## Instructions
1. Choose the BEST existing folder from the list above if any is a logical fit.
2. If NO existing folder fits, suggest a short, descriptive new folder name (Title Case, no spaces — use underscores if needed).
3. Return ONLY valid JSON in this exact schema — no markdown, no extra text:

{{"action": "move", "target_folder": "<folder name>", "reason": "<one sentence why>"}}

### Examples
{{"action": "move", "target_folder": "Documents", "reason": "This is a Word document likely containing written notes or reports."}}
{{"action": "move", "target_folder": "Python_Scripts", "reason": "This is a Python source file with code logic."}}

Respond with JSON only:"""


# ── LLM call ─────────────────────────────────────────────────────────────────


def ask_llm(file_meta: dict, existing_folders: list[str]) -> MoveDecision | None:
    """
    Call the local Llama 3.2 model and parse the MoveDecision JSON.

    Retries up to _MAX_RETRIES times on JSON parse / validation errors.

    Args:
        file_meta: Metadata dict from get_file_meta().
        existing_folders: Available folder names for the LLM to choose from.

    Returns:
        A valid MoveDecision, or None if all retries fail.
    """
    prompt = build_prompt(file_meta, existing_folders)

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = ollama.chat(
                model=_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.1},
            )
            raw_text: str = response["message"]["content"].strip()

            # Strip markdown code fences if the model wraps the JSON
            if raw_text.startswith("```"):
                lines = raw_text.splitlines()
                raw_text = "\n".join(
                    line for line in lines if not line.startswith("```")
                ).strip()

            # Find JSON object boundaries
            start = raw_text.find("{")
            end = raw_text.rfind("}") + 1
            if start == -1 or end == 0:
                raise ValueError("No JSON object found in LLM response.")

            json_text = raw_text[start:end]
            data = json.loads(json_text)
            decision = MoveDecision(**data)
            return decision

        except Exception as exc:
            console.print(
                f"  [yellow]⚠ Attempt {attempt}/{_MAX_RETRIES} failed for "
                f"'{file_meta['filename']}': {exc}[/yellow]"
            )
            if attempt < _MAX_RETRIES:
                time.sleep(1)

    console.print(
        f"  [red]✗ Skipped '{file_meta['filename']}' — LLM could not return valid JSON.[/red]"
    )
    return None


# ── Collision handling ────────────────────────────────────────────────────────


def resolve_collision(dest: Path) -> Path:
    """
    If *dest* already exists, append an 8-char content hash to the stem.

    Args:
        dest: The intended destination path.

    Returns:
        A non-colliding destination path.
    """
    if not dest.exists():
        return dest

    short_hash = hashlib.md5(str(time.time_ns()).encode()).hexdigest()[:8]
    new_name = f"{dest.stem}_{short_hash}{dest.suffix}"
    return dest.parent / new_name


# ── Dry-run table ─────────────────────────────────────────────────────────────


def print_dry_run_table(
    decisions: list[tuple[Path, MoveDecision]], root: Path
) -> None:
    """Print a Rich table summarising proposed moves without executing them."""
    table = Table(
        title="[bold cyan]FilePilot AI — Proposed Moves (Dry Run)[/bold cyan]",
        show_header=True,
        header_style="bold magenta",
        show_lines=True,
    )
    table.add_column("File", style="white", no_wrap=True)
    table.add_column("→ Target Folder", style="green")
    table.add_column("Reason", style="dim")

    for src, decision in decisions:
        table.add_row(
            src.name,
            decision.target_folder,
            decision.reason,
        )

    console.print(table)
    console.print(
        f"\n[bold yellow]Dry run complete.[/bold yellow] "
        f"{len(decisions)} file(s) would be moved. "
        "Re-run without [bold]--dry-run[/bold] to apply."
    )


# ── Execute moves ─────────────────────────────────────────────────────────────


def execute_moves(
    decisions: list[tuple[Path, MoveDecision]],
    root: Path,
    dry_run: bool = False,
) -> None:
    """
    Either print a dry-run table or execute shutil.move for each decision.

    New target folders are created automatically.
    Each successful move is recorded in ChromaDB.

    Args:
        decisions: List of (source_path, MoveDecision) tuples.
        root: The root directory being organized.
        dry_run: If True, print table only; do not move files or update DB.
    """
    if dry_run:
        print_dry_run_table(decisions, root)
        return

    console.print(
        f"\n[bold cyan]Executing {len(decisions)} move(s)…[/bold cyan]\n"
    )

    for src, decision in decisions:
        target_dir = root / decision.target_folder
        target_dir.mkdir(parents=True, exist_ok=True)

        dest = resolve_collision(target_dir / src.name)

        try:
            shutil.move(str(src), str(dest))
            console.print(
                f"  [green]✔[/green] {src.name} → [bold]{decision.target_folder}/[/bold]{dest.name}"
            )

            record = FileRecord(
                id=str(uuid.uuid4()),
                filename=src.name,
                extension=src.suffix.lower(),
                original_path=str(src),
                new_path=str(dest),
                reason=decision.reason,
            )
            store_move(record)

        except Exception as exc:
            console.print(f"  [red]✗ Failed to move '{src.name}': {exc}[/red]")

    console.print("\n[bold green]✓ Organization complete![/bold green]")
    console.print(
        "[dim]Run [bold]python main.py search --query \"<topic>\"[/bold] "
        "or open the Streamlit app to find your files.[/dim]"
    )


# ── Restore / Undo ────────────────────────────────────────────────────────────


def restore_file(record: dict) -> tuple[bool, str]:
    """
    Move a file back to its original location (undo a previous move).

    This is the disk-side half of an undo; pair with undo_move() in
    database.py to also remove the ChromaDB record.

    Args:
        record: A metadata dict as returned by list_all_moves(), containing
                at minimum 'new_path' and 'original_path' keys.

    Returns:
        (True, success_message) or (False, error_message).
    """
    src = Path(record.get("new_path", ""))
    dst = Path(record.get("original_path", ""))

    if not src.exists():
        return False, f"File no longer exists at current location: {src}"

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        # Handle collision at destination
        if dst.exists():
            short_hash = hashlib.md5(str(time.time_ns()).encode()).hexdigest()[:8]
            dst = dst.parent / f"{dst.stem}_restored_{short_hash}{dst.suffix}"
        shutil.move(str(src), str(dst))
        return True, f"Restored → {dst}"
    except Exception as exc:
        return False, f"Restore failed: {exc}"
