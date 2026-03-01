"""
scanner.py — Directory scanner for FilePilot AI

Scans a root directory and returns:
  - existing_folders: list of subfolder names (potential categories)
  - loose_files: list of Path objects for files directly in root (to be organized)

Respects .aiignore files found in the root directory.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

# Patterns always ignored regardless of .aiignore
DEFAULT_IGNORE_PATTERNS: list[str] = [
    ".DS_Store",
    ".git",
    ".gitignore",
    "__pycache__",
    "*.pyc",
    "Thumbs.db",
    "desktop.ini",
    ".aiignore",
]


@dataclass
class ScanResult:
    existing_folders: list[str] = field(default_factory=list)
    loose_files: list[Path] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Found {len(self.existing_folders)} existing folder(s) "
            f"and {len(self.loose_files)} loose file(s)."
        )


def _load_aiignore(root: Path) -> list[str]:
    """Read .aiignore patterns from the root directory."""
    aiignore_path = root / ".aiignore"
    if not aiignore_path.exists():
        return []
    patterns: list[str] = []
    for line in aiignore_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append(line)
    return patterns


def _is_ignored(name: str, ignore_patterns: list[str]) -> bool:
    """Return True if the file/folder name matches any ignore pattern."""
    if name.startswith("."):
        return True
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False


def scan_directory(root: str | Path) -> ScanResult:
    """
    Scan *root* for loose files and existing subfolders.

    Args:
        root: Path to the directory to organize.

    Returns:
        ScanResult with existing_folders and loose_files populated.

    Raises:
        NotADirectoryError: if *root* is not a valid directory.
    """
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"'{root}' is not a directory.")

    ignore_patterns = DEFAULT_IGNORE_PATTERNS + _load_aiignore(root)

    result = ScanResult()

    for item in sorted(root.iterdir()):
        if _is_ignored(item.name, ignore_patterns):
            continue

        if item.is_dir():
            result.existing_folders.append(item.name)
        elif item.is_file():
            result.loose_files.append(item)

    return result
