from __future__ import annotations

"""
External tool adapter contract and helpers for MOLSAIC V3.

Wrappers (msi2namd, packmol, msi2lmp) should populate ExternalToolResult
and return result.to_dict() with unified keys:
  - tool: str (program name, e.g., "packmol")
  - argv: list[str] (full argv including the exe path as argv[0])
  - cwd: str (absolute working directory)
  - duration_s: float
  - stdout: str
  - stderr: str
  - outputs: dict[str,str] (named absolute artifact paths)
  - tool_version: Optional[str]
  - warnings: list[str] (optional; empty when none)
  - seed: Optional[int] (for RNG-driven tools like Packmol)

Helpers provided here:
  - augment_env_with_exe_dir(exe_path) -> dict
  - get_tool_version(exe_path, timeout_s=5) -> str
"""

import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


def augment_env_with_exe_dir(exe_path: str, base_env: Optional[dict] = None) -> dict:
    """
    Prepend the executable's directory to PATH to improve dynamic linker resolution.

    Returns a copy of the environment dict safe for subprocess.run(..., env=...).
    """
    env = (base_env.copy() if base_env is not None else os.environ.copy())
    try:
        exe_dir = str(Path(exe_path).resolve().parent)
    except Exception:
        exe_dir = str(Path(exe_path).parent)
    env["PATH"] = f"{exe_dir}:{env.get('PATH', '')}"
    return env


@dataclass
class ExternalToolResult:
    """
    Unified result envelope for external tool adapters.

    Fields:
      - tool: program name (e.g., "packmol")
      - argv: full argv list; argv[0] is the executable path string
      - cwd: absolute working directory used for the process
      - duration_s: wall-clock seconds
      - stdout: captured stdout text
      - stderr: captured stderr text
      - outputs: mapping of logical output names -> absolute paths
      - tool_version: captured version string when available (else "unknown")
      - warnings: optional list of warning strings
      - seed: optional RNG seed used by the tool (when applicable)
    """
    tool: str
    argv: List[str]
    cwd: str
    duration_s: float
    stdout: str
    stderr: str
    outputs: Dict[str, str]
    tool_version: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    seed: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        # Produce a dict with stable keys; omit None fields but keep empty lists/dicts.
        d = asdict(self)
        if self.tool_version is None:
            d.pop("tool_version", None)
        if self.seed is None:
            d.pop("seed", None)
        # Ensure outputs are strings
        d["outputs"] = {k: str(v) for k, v in self.outputs.items()}
        return d


_VERSION_PATTERNS: List[re.Pattern[str]] = [
    # Common generic: "... version X.Y.Z"
    re.compile(r"\bversion\b[:\s]*([0-9]+(?:\.[0-9]+){0,3}(?:[-_a-zA-Z0-9]+)?)", re.IGNORECASE),
    # Semver-ish standalone
    re.compile(r"\b([0-9]+\.[0-9]+(?:\.[0-9]+){0,2}(?:[-+][\w\.-]+)?)\b"),
    # Packmol typical banner: "PACKMOL v20.15.3" or "PACKMOL 20.15.3"
    re.compile(r"\bpackmol\b[\s:vV]*([0-9]+(?:\.[0-9]+){0,3})", re.IGNORECASE),
    # msi2namd/msi2lmp patterns: "msi2lmp 1.0", "msi2namd v1.2.3"
    re.compile(r"\bmsi2(?:lmp|namd)\b[\s:vV]*([0-9]+(?:\.[0-9]+){0,3})", re.IGNORECASE),
]


def _parse_version_from_text(text: str) -> Optional[str]:
    # Try each pattern; return first plausible match
    for pat in _VERSION_PATTERNS:
        m = pat.search(text or "")
        if m:
            ver = m.group(1).strip()
            # Basic sanity: ensure at least one dot or digit sequence
            if any(ch.isdigit() for ch in ver):
                return ver
    return None


def get_tool_version(exe_path: str, timeout_s: int = 5) -> str:
    """
    Best-effort tool version discovery.

    Strategy:
      1) Try exe --version, -version, -v, -h (in that order)
      2) As last resort, run exe without args (some tools print a banner)
      3) Parse stdout/stderr with _parse_version_from_text
      4) Return "unknown" if all attempts fail or parse yields nothing

    This function never raises; it is safe to call in summaries.
    """
    try:
        exe = Path(exe_path).resolve()
        if not exe.exists():
            return "unknown"
    except Exception:
        return "unknown"

    attempts: List[List[str]] = [
        [str(exe), "--version"],
        [str(exe), "-version"],
        [str(exe), "-v"],
        [str(exe), "-h"],
        [str(exe)],
    ]

    env = augment_env_with_exe_dir(str(exe))
    for argv in attempts:
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                env=env,
                check=False,
            )
            text = (proc.stdout or "") + "\n" + (proc.stderr or "")
            ver = _parse_version_from_text(text)
            if ver:
                return ver
        except Exception:
            # Ignore and continue attempts
            continue

    # As a final fallback, try invoking via shell if the path includes spaces (rare on Linux)
    try:
        cmd = f"{shlex.quote(str(exe))} --version"
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=env,
            check=False,
        )
        text = (proc.stdout or "") + "\n" + (proc.stderr or "")
        ver = _parse_version_from_text(text)
        if ver:
            return ver
    except Exception:
        pass

    return "unknown"


def resolve_executable(
    config_val: Optional[str],
    prog_name: str,
    search_dirs: Optional[List[Union[Path, str]]] = None,
) -> str:
    """
    Resolve an executable path using a simple precedence:
      1) If config_val is an absolute path, validate and return it.
      2) If config_val is relative, try each directory in search_dirs/<dir>/config_val.
         If not found, try shutil.which(config_val).
      3) Fallback to shutil.which(prog_name).
    Returns the absolute path or raises FileNotFoundError.
    """
    # 1) Absolute config
    if config_val:
        p = Path(config_val)
        if p.is_absolute():
            if p.exists() and p.is_file():
                return str(p.resolve())
        else:
            # 2) Relative: check search_dirs then PATH
            dirs: List[Path] = [Path(d) for d in (search_dirs or [])]
            for d in dirs:
                cand = (d / p).resolve()
                if cand.exists() and cand.is_file():
                    return str(cand)
            found = shutil.which(str(p))
            if found:
                fp = Path(found).resolve()
                if fp.exists():
                    return str(fp)

    # 3) Fallback to PATH by program name
    found2 = shutil.which(prog_name)
    if found2 and Path(found2).exists():
        return str(Path(found2).resolve())

    raise FileNotFoundError(f"Executable for '{prog_name}' not found. Provided: {config_val!r}")