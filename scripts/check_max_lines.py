#!/usr/bin/env python3
"""
Check that all Python source files are ≤500 lines.

Usage:
    python scripts/check_max_lines.py

Exit codes:
    0 - All files pass the line limit check
    1 - One or more files exceed the line limit
"""

import sys
from pathlib import Path
from typing import NamedTuple


class FileStats(NamedTuple):
    """Line count statistics for a file."""
    path: Path
    lines: int


# Maximum allowed lines per file
MAX_LINES = 500

# Files/patterns to exclude from the check (vendor/generated files)
# Add patterns here if needed, e.g., for generated code or vendored dependencies
ALLOWLIST = [
    # Example: "src/vendor/",
    # Example: "_generated.py",
]


def count_lines(filepath: Path) -> int:
    """Count the number of lines in a file."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except (OSError, IOError):
        return 0


def is_allowlisted(filepath: Path) -> bool:
    """Check if a file matches any allowlist pattern."""
    path_str = str(filepath)
    for pattern in ALLOWLIST:
        if pattern in path_str:
            return True
    return False


def scan_python_files(src_dir: Path) -> list[FileStats]:
    """Scan all Python files in the source directory."""
    results = []
    for py_file in src_dir.rglob("*.py"):
        if is_allowlisted(py_file):
            continue
        line_count = count_lines(py_file)
        results.append(FileStats(path=py_file, lines=line_count))
    return results


def main() -> int:
    """Main entry point."""
    # Find the src directory relative to script location
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    src_dir = project_root / "src"
    
    if not src_dir.exists():
        print(f"Error: Source directory not found: {src_dir}", file=sys.stderr)
        return 1
    
    # Scan all Python files
    file_stats = scan_python_files(src_dir)
    
    if not file_stats:
        print("No Python files found in src/", file=sys.stderr)
        return 1
    
    # Sort by line count (descending)
    file_stats.sort(key=lambda x: x.lines, reverse=True)
    
    # Find violations
    violations = [f for f in file_stats if f.lines > MAX_LINES]
    
    # Report results
    total_files = len(file_stats)
    
    if violations:
        print(f"✗ {len(violations)} file(s) exceed {MAX_LINES} lines:\n")
        for f in violations:
            rel_path = f.path.relative_to(project_root)
            print(f"  {f.lines:5d}  {rel_path}")
        print()
    else:
        print(f"✓ All {total_files} source files are ≤{MAX_LINES} lines.\n")
    
    # Print top 30 files by line count
    print("Top 30 files by line count:")
    for f in file_stats[:30]:
        rel_path = f.path.relative_to(project_root)
        marker = " [!]" if f.lines > MAX_LINES else ""
        print(f"  {f.lines:5d}  {rel_path}{marker}")
    
    # Print allowlist info if any patterns are defined
    if ALLOWLIST:
        print(f"\nAllowlist patterns ({len(ALLOWLIST)}):")
        for pattern in ALLOWLIST:
            print(f"  - {pattern}")
    
    # Return exit code
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
