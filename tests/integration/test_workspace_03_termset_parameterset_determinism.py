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

WORKSPACE_NAME = "03_termset_parameterset_to_frc_nonbond_only"


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

    cfg_copy = dict(cfg)
    cfg_copy["outputs_dir"] = str(outdir)

    tmp_cfg = tmp_path / "config.json"
    tmp_cfg.write_text(json.dumps(cfg_copy, indent=2) + "\n", encoding="utf-8")

    cmd = [sys.executable, str(ws["run"]), "--config", str(tmp_cfg)]
    proc = subprocess.run(cmd, cwd=str(ws["dir"]), capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
    assert proc.returncode == 0

    termset = outdir / "termset.json"
    parameterset = outdir / "parameterset.json"
    frc = outdir / "ff_nonbond_only.frc"
    manifest = outdir / "run_manifest.json"

    assert termset.exists() and termset.stat().st_size > 0
    assert parameterset.exists() and parameterset.stat().st_size > 0
    assert frc.exists() and frc.stat().st_size > 0
    assert manifest.exists() and manifest.stat().st_size > 0

    m = _load_json(manifest)
    assert m.get("schema") == "molsaic.run_manifest.v0.1.1"
    assert m.get("workspace") == WORKSPACE_NAME
    assert "tool_versions" in m and isinstance(m["tool_versions"], dict)
    assert m.get("inputs") == {}
    assert "outputs" in m and isinstance(m["outputs"], dict)

    ts = _load_json(termset)
    ps = _load_json(parameterset)
    assert ts.get("schema") == "molsaic.termset.v0.1.2"
    assert ps.get("schema") == "upm.parameterset.v0.1.2"

    return {
        "termset": termset,
        "parameterset": parameterset,
        "ff_nonbond_only": frc,
        "run_manifest": manifest,
    }


@pytest.mark.integration
def test_workspace_03_determinism(tmp_path: Path) -> None:
    """Run workspace 03 twice and assert strict byte determinism of key artifacts."""

    run1 = _run_once(tmp_path / "run1")
    run2 = _run_once(tmp_path / "run2")

    assert run1["termset"].read_bytes() == run2["termset"].read_bytes()
    assert run1["parameterset"].read_bytes() == run2["parameterset"].read_bytes()
    assert run1["ff_nonbond_only"].read_bytes() == run2["ff_nonbond_only"].read_bytes()
    assert run1["run_manifest"].read_bytes() == run2["run_manifest"].read_bytes()

    assert _load_json(run1["run_manifest"]) == _load_json(run2["run_manifest"])

