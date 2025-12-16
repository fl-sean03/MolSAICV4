import json
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure repo root import (same pattern as other integration tests)
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

WORKSPACE_NAME = "02_usm_upm_msi2lmp_pipeline"


def _workspace_dir() -> Path:
    return REPO_ROOT / "workspaces" / WORKSPACE_NAME


def _workspace_files() -> dict[str, Path]:
    d = _workspace_dir()
    return {
        "dir": d,
        "config": d / "config.json",
        "run": d / "run.py",
    }


def _load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _run_once(tmp_path: Path) -> dict[str, Path]:
    ws = _workspace_files()

    cfg = _load_json(ws["config"])

    outdir = tmp_path / "outputs"
    outdir.mkdir(parents=True, exist_ok=True)

    # Force the external step to be skipped deterministically: point to a missing executable.
    cfg_copy = dict(cfg)
    cfg_copy["outputs_dir"] = str(outdir)
    cfg_copy["executables"] = dict(cfg_copy.get("executables") or {})
    cfg_copy["executables"]["msi2lmp"] = "/__missing__/msi2lmp"

    tmp_cfg = tmp_path / "config.json"
    tmp_cfg.write_text(json.dumps(cfg_copy, indent=2), encoding="utf-8")

    cmd = [sys.executable, str(ws["run"]), "--config", str(tmp_cfg)]
    proc = subprocess.run(cmd, cwd=str(ws["dir"]), capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
    assert proc.returncode == 0

    req = outdir / "requirements.json"
    frc = outdir / "ff_minimal.frc"
    manifest = outdir / "run_manifest.json"

    assert req.exists() and req.stat().st_size > 0
    assert frc.exists() and frc.stat().st_size > 0
    assert manifest.exists() and manifest.stat().st_size > 0

    # Ensure wrapper wrote a result.json even when tool is missing.
    m = _load_json(manifest)
    assert m.get("schema") == "molsaic.run_manifest.v0.1.1"
    assert m.get("workspace") == WORKSPACE_NAME
    assert "tool_versions" in m and isinstance(m["tool_versions"], dict)
    assert "inputs" in m and isinstance(m["inputs"], dict)
    assert "outputs" in m and isinstance(m["outputs"], dict)
    assert "external" in m and isinstance(m["external"], dict)
    assert m["external"].get("tool") == "msi2lmp"
    assert m["external"].get("status") == "missing_tool"
    assert "result_json_path" in m["external"]

    result_json_rel = Path(str(m["external"]["result_json_path"]))
    result_json = outdir / result_json_rel
    assert result_json.exists() and result_json.stat().st_size > 0

    return {"requirements": req, "ff_minimal": frc, "run_manifest": manifest}


@pytest.mark.integration
def test_golden_workspace_determinism(tmp_path: Path) -> None:
    """
    Run the golden workspace twice and assert determinism of:
      - requirements.json
      - ff_minimal.frc
      - run_manifest.json

    External tool step is forced to missing_tool to keep the integration test runnable
    on machines without the msi2lmp executable.
    """
    run1 = _run_once(tmp_path / "run1")
    run2 = _run_once(tmp_path / "run2")

    # Strict byte equality for deterministic artifacts
    assert run1["requirements"].read_bytes() == run2["requirements"].read_bytes()
    assert run1["ff_minimal"].read_bytes() == run2["ff_minimal"].read_bytes()
    assert run1["run_manifest"].read_bytes() == run2["run_manifest"].read_bytes()

    # Also compare parsed JSON for clarity
    assert _load_json(run1["run_manifest"]) == _load_json(run2["run_manifest"])