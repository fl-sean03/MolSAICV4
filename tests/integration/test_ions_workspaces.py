import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

import pytest

# Ensure repo root import
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

WORKSPACES = [
    "alumina_AS2_ions_v1",
    "alumina_AS5_ions_v1",
    "alumina_AS10_ions_v1",
    "alumina_AS12_ions_v1",
]


def _workspace_dir(name: str) -> Path:
    return REPO_ROOT / "workspaces" / name


def _workspace_files(name: str) -> Dict[str, Path]:
    d = _workspace_dir(name)
    return {
        "dir": d,
        "config": d / "config.json",
        "run": d / "run.py",
        "outputs": d / "outputs",
        "summary": d / "outputs" / "summary.json",
    }


def _load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _load_config_target_c(cfg: dict) -> Optional[float]:
    try:
        return float(cfg.get("target_c")) if cfg.get("target_c") is not None else None
    except Exception:
        return None


def _resolve_executable(execs_cfg: dict, profiles_cfg: dict, selected_profile: Optional[str], key: str) -> Optional[str]:
    # Precedence: executables[key] > profiles[selected_profile][key] > shutil.which
    val = (execs_cfg or {}).get(key)
    if not val and selected_profile:
        prof = (profiles_cfg or {}).get(selected_profile, {})
        val = prof.get(key)
    if val:
        p = Path(val)
        if p.is_file():
            return str(p)
        found = shutil.which(str(p))
        if found:
            return str(Path(found).resolve())
    found = shutil.which(key)
    return str(Path(found).resolve()) if found else None


def _executables_available(cfg: dict) -> bool:
    execs_cfg = cfg.get("executables", {}) or {}
    profiles_cfg = cfg.get("executables_profiles", {}) or {}
    selected_profile = cfg.get("selected_profile")

    needed = ["msi2namd", "packmol", "msi2lmp"]
    for k in needed:
        path = _resolve_executable(execs_cfg, profiles_cfg, selected_profile, k)
        if not path or not Path(path).exists():
            return False
    return True


def _validate_manifest(summary: dict, schema_path: Path) -> None:
    try:
        import jsonschema  # type: ignore
    except Exception:
        pytest.skip("jsonschema not installed; skipping manifest validation")
        return
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=summary, schema=schema)


def _assert_summary_invariants(name: str, cfg: dict, summary: dict) -> None:
    # Required keys
    assert "inputs" in summary and "outputs" in summary and "counts" in summary and "cell" in summary

    # Verify output files exist and are non-empty
    outputs = summary["outputs"]
    for k in ["car_file", "mdf_file", "lmp_data_file", "packed_structure"]:
        p = Path(outputs[k])
        assert p.exists(), f"[{name}] missing output: {k} -> {p}"
        assert p.stat().st_size > 0, f"[{name}] empty output: {k} -> {p}"

    # Cell.c must equal config target_c when present
    target_c = _load_config_target_c(cfg)
    if target_c is not None:
        assert abs(float(summary["cell"].get("c", -1.0)) - float(target_c)) < 1e-6, f"[{name}] cell.c != target_c"

    # Simple counts sanity when present
    counts = summary.get("counts", {})
    atoms = counts.get("atoms")
    surface_atoms = counts.get("surface_atoms")
    waters = counts.get("waters")
    if atoms is not None and surface_atoms is not None and waters is not None:
        assert atoms == surface_atoms + 3 * waters, f"[{name}] counts mismatch: atoms != surface_atoms + 3*waters"


@pytest.mark.integration
@pytest.mark.parametrize("ws_name", WORKSPACES)
def test_existing_summaries_validate_manifest(ws_name: str):
    """
    Validate existing workspace outputs/summary.json against manifest schema and invariants.
    This test does NOT run the external tools; it inspects committed artifacts.
    """
    ws = _workspace_files(ws_name)
    if not ws["summary"].exists():
        pytest.skip(f"No precomputed summary found for {ws_name}: {ws['summary']}")
    cfg = _load_json(ws["config"])
    summary = _load_json(ws["summary"])

    _validate_manifest(summary, REPO_ROOT / "docs" / "manifest.v1.schema.json")
    _assert_summary_invariants(ws_name, cfg, summary)


@pytest.mark.integration
@pytest.mark.parametrize("ws_name", WORKSPACES)
def test_run_workspace_when_executables_available(ws_name: str, tmp_path: Path):
    """
    Conditionally run a workspace end-to-end when RUN_INTEGRATION=1 and all executables are available.
    Writes into a temp outputs dir to avoid clobbering committed artifacts.
    """
    if os.environ.get("RUN_INTEGRATION", "0") != "1":
        pytest.skip("Set RUN_INTEGRATION=1 to enable end-to-end workspace runs")

    ws = _workspace_files(ws_name)
    cfg = _load_json(ws["config"])

    if not _executables_available(cfg):
        pytest.skip(f"Executables not available for {ws_name}; skipping run")

    # Prepare a temporary copy of the config with a temp outputs_dir and manifest validation enabled
    cfg_copy = dict(cfg)
    tmp_outputs = tmp_path / "outputs"
    cfg_copy["outputs_dir"] = str(tmp_outputs)
    cfg_copy["validate_manifest"] = True

    # Write temp config
    tmp_cfg_path = tmp_path / "config.json"
    tmp_cfg_path.write_text(json.dumps(cfg_copy, indent=2), encoding="utf-8")

    # Run: python run.py --config tmp_cfg_path
    cmd = [sys.executable, str(ws["run"]), "--config", str(tmp_cfg_path)]
    env = os.environ.copy()
    proc = subprocess.run(cmd, cwd=str(ws["dir"]), env=env, capture_output=True, text=True)
    # If process failed, surface stdout/stderr for diagnosis
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
    assert proc.returncode == 0, f"Workspace run failed: {ws_name}"

    # Validate new summary
    new_summary_path = tmp_outputs / "summary.json"
    assert new_summary_path.exists(), f"Missing summary.json after run: {new_summary_path}"
    summary = _load_json(new_summary_path)
    _validate_manifest(summary, REPO_ROOT / "docs" / "manifest.v1.schema.json")
    _assert_summary_invariants(ws_name, cfg_copy, summary)


@pytest.mark.integration
@pytest.mark.parametrize("ws_name", WORKSPACES)
def test_determinism_when_enabled(ws_name: str, tmp_path: Path):
    """
    Run the same workspace twice when RUN_DETERMINISM=1 to compare manifest fields for equality.
    We don't byte-compare heavy artifacts, but we ensure structured fields (inputs, params, tools, cell, counts) match.
    """
    if os.environ.get("RUN_DETERMINISM", "0") != "1":
        pytest.skip("Set RUN_DETERMINISM=1 to enable determinism checks")

    ws = _workspace_files(ws_name)
    cfg = _load_json(ws["config"])
    if not _executables_available(cfg):
        pytest.skip(f"Executables not available for {ws_name}; skipping determinism run")

    def _run_once(outdir: Path) -> dict:
        cfg_copy = dict(cfg)
        cfg_copy["outputs_dir"] = str(outdir)
        cfg_copy["validate_manifest"] = True
        tmp_cfg = outdir / "config.json"
        outdir.mkdir(parents=True, exist_ok=True)
        tmp_cfg.write_text(json.dumps(cfg_copy, indent=2), encoding="utf-8")
        cmd = [sys.executable, str(ws["run"]), "--config", str(tmp_cfg)]
        proc = subprocess.run(cmd, cwd=str(ws["dir"]), capture_output=True, text=True)
        if proc.returncode != 0:
            print(proc.stdout)
            print(proc.stderr, file=sys.stderr)
        assert proc.returncode == 0
        return _load_json(outdir / "summary.json")

    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"

    s1 = _run_once(out1)
    s2 = _run_once(out2)

    # Compare key structured fields (ignore timings and finished_at/started_at)
    for key in ["inputs", "params", "tools", "tool_versions", "tool_profile", "counts", "cell"]:
        if key in s1 or key in s2:
            assert s1.get(key) == s2.get(key), f"[{ws_name}] Determinism mismatch in field: {key}"