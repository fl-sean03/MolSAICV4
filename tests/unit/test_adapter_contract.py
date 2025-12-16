import os
from pathlib import Path

import pytest

# Under repo root, ensure we can import this project (src/ is importable for tests)
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(SRC_ROOT))

from external.adapter import (  # noqa: E402
    augment_env_with_exe_dir,
    get_tool_version,
)


@pytest.mark.unit
def test_augment_env_with_exe_dir_inserts_parent_dir_tmp(tmp_path: Path):
    exe_dir = tmp_path / "bin"
    exe_dir.mkdir(parents=True, exist_ok=True)
    exe_path = exe_dir / "tool"
    exe_path.write_text("", encoding="utf-8")

    env = augment_env_with_exe_dir(str(exe_path))
    assert "PATH" in env
    # Parent of exe must be prepended to PATH
    path_parts = env["PATH"].split(":")
    assert str(exe_dir.resolve()) == path_parts[0]


@pytest.mark.unit
def test_get_tool_version_never_raises_and_returns_string_for_nonexistent():
    # Non-existent exe should not raise; returns "unknown"
    ver = get_tool_version("/path/that/does/not/exist/tool", timeout_s=1)
    assert isinstance(ver, str)


@pytest.mark.unit
def test_get_tool_version_on_echo_or_true_returns_string():
    # Try common always-present tools to ensure non-raising behavior
    candidate_bins = ["/bin/echo", "/usr/bin/echo", "/bin/true", "/usr/bin/true"]
    exe = next((p for p in candidate_bins if Path(p).exists()), None)
    if exe is None:
        pytest.skip("No suitable simple system binary found to probe version banner")
    ver = get_tool_version(exe, timeout_s=1)
    assert isinstance(ver, str)