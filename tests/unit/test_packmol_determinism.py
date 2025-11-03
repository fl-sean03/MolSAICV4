import os
from pathlib import Path
import textwrap
import shutil
import sys

import pytest

# Ensure repo root import
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from external import packmol  # noqa: E402


@pytest.mark.unit
def test_inject_seed_removes_existing_and_prepends_new():
    original = textwrap.dedent(
        """
        # comment
        seed 111
        tolerance 2.0
        output hydrated.pdb
        structure AS2.pdb
        end structure
        """
    ).strip("\n")
    new_text = packmol._inject_seed(original, 12345)  # type: ignore[attr-defined]
    # New seed must be the very first non-empty line
    first_line = new_text.splitlines()[0].strip()
    assert first_line.lower().startswith("seed ")
    assert "12345" in first_line
    # No other seed lines remain
    assert sum(1 for ln in new_text.splitlines() if ln.strip().lower().startswith("seed")) == 1


@pytest.mark.unit
def test_escalate_missing_structures_raises_before_execution(tmp_path: Path):
    # Create a minimal deck that references non-existent structures
    deck = tmp_path / "deck.inp"
    deck.write_text(
        textwrap.dedent(
            """
            output hydrated.pdb
            tolerance 2.0
            structure AS2.pdb
            end structure
            structure WAT.pdb
            end structure
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    # Use /bin/true as a stand-in "executable"; run() should raise before execution due to escalation
    exe_candidates = ["/bin/true", "/usr/bin/true"]
    exe = next((p for p in exe_candidates if Path(p).exists()), None)
    if exe is None:
        pytest.skip("No suitable /bin/true available to satisfy executable presence check")

    with pytest.raises(RuntimeError) as ei:
        with tmp_path.as_cwd() if hasattr(tmp_path, "as_cwd") else _tmp_chdir(tmp_path):
            packmol.run(
                deck_path=str(deck),
                exe_path=exe,
                timeout_s=5,
                seed=7,
                escalate_warnings_to_error=True,
            )
    msg = str(ei.value)
    assert "validation failed" in msg or "warnings" in msg.lower()


# Backport helper for Python versions lacking Path.as_cwd() in pytest tmp_path
from contextlib import contextmanager  # noqa: E402


@contextmanager
def _tmp_chdir(path: Path):
    prev = Path.cwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(str(prev))