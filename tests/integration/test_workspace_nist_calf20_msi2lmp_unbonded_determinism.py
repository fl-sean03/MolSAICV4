from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure repo root import (same pattern as other integration tests)
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


WORKSPACE_NAME = "nist_calf20_msi2lmp_unbonded_v1"


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _workspace_dir() -> Path:
    return REPO_ROOT / "workspaces" / "NIST" / WORKSPACE_NAME


def _workspace_files() -> dict[str, Path]:
    d = _workspace_dir()
    return {
        "dir": d,
        "config": d / "config.json",
        "run": d / "run.py",
    }


def _load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _assert_manifest_hashed_paths(
    section: dict,
    *,
    required_keys: list[str],
    path_prefix: str | None = None,
) -> None:
    """Assert `{key: {path, sha256}}` contract for run_manifest inputs/outputs.

    This intentionally validates *contracts* (stable schema, relative paths, sha256),
    not brittle workspace `config.json` internals.
    """
    assert isinstance(section, dict)
    for k in required_keys:
        assert k in section
        rec = section[k]
        assert isinstance(rec, dict)

        p = rec.get("path")
        s = rec.get("sha256")
        assert isinstance(p, str) and p.strip()
        assert isinstance(s, str) and _SHA256_RE.match(s)
        if path_prefix is not None:
            assert p.startswith(path_prefix)


def _run_once(tmp_path: Path) -> dict[str, Path]:
    ws = _workspace_files()
    cfg = _load_json(ws["config"])

    # Guardrail: this workspace's contract is to generate the `.frc` via UPM at runtime
    # (under outputs/frc_files/) and *not* ship any `.frc` under inputs/.
    inputs_dir = ws["dir"] / "inputs"
    assert inputs_dir.is_dir()
    assert list(inputs_dir.glob("*.frc")) == []

    outdir = tmp_path / "outputs"
    outdir.mkdir(parents=True, exist_ok=True)

    # Force the external step to be skipped deterministically:
    # - make executable resolution fail (PATH="") so the workspace falls back to a missing absolute path
    # - msi2lmp wrapper should still write a deterministic result.json envelope
    cfg_copy = dict(cfg)
    cfg_copy["outputs_dir"] = str(outdir)
    cfg_copy["executables"] = {"msi2lmp": "/__missing__/msi2lmp"}
    cfg_copy["executables_profiles"] = {}
    cfg_copy["selected_profile"] = None

    tmp_cfg = tmp_path / "config.json"
    tmp_cfg.write_text(json.dumps(cfg_copy, indent=2) + "\n", encoding="utf-8")

    env = os.environ.copy()
    env["PATH"] = ""
    env["PYTHONHASHSEED"] = "0"

    cmd = [sys.executable, str(ws["run"]), "--config", str(tmp_cfg)]
    proc = subprocess.run(cmd, cwd=str(ws["dir"]), env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
    assert proc.returncode == 0

    termset = outdir / "termset.json"
    parameterset = outdir / "parameterset.json"
    frc_cvff = outdir / "frc_files" / "ff_cvff_min_bonded.frc"
    manifest = outdir / "run_manifest.json"
    coord_norm_report = outdir / "coord_normalization_report.json"
    validation_report = outdir / "validation_report.json"

    assert termset.exists() and termset.stat().st_size > 0
    assert parameterset.exists() and parameterset.stat().st_size > 0
    assert frc_cvff.exists() and frc_cvff.stat().st_size > 0
    assert manifest.exists() and manifest.stat().st_size > 0
    assert coord_norm_report.exists() and coord_norm_report.stat().st_size > 0
    assert validation_report.exists() and validation_report.stat().st_size > 0

    # Back-compat: older/newer revisions may also write a nonbond-only .frc.
    # If present, we include it in determinism checks.
    frc_nonbond = outdir / "ff_nonbond_only.frc"

    m = _load_json(manifest)
    assert m.get("schema") == "molsaic.run_manifest.v0.1.1"
    assert m.get("workspace") == WORKSPACE_NAME

    # ---- Contract assertions: staged inputs/outputs live under outputs_dir and are sha256 hashed ----
    _assert_manifest_hashed_paths(
        m.get("inputs") or {},
        required_keys=["car", "mdf", "parameterset"],
        path_prefix="inputs/",
    )
    _assert_manifest_hashed_paths(
        m.get("outputs") or {},
        required_keys=[
            "coord_normalization_report",
            "termset",
            "parameterset",
            "ff_cvff_min_bonded",
            "validation_report",
        ],
    )

    # Sanity: hashed manifest entries correspond to real files.
    for rec in (m.get("inputs") or {}).values():
        p = outdir / Path(rec["path"])
        assert p.exists() and p.stat().st_size > 0
    for rec in (m.get("outputs") or {}).values():
        p = outdir / Path(rec["path"])
        assert p.exists() and p.stat().st_size > 0

    # External wrapper contract: we force msi2lmp to be missing.
    ext = m.get("external")
    assert isinstance(ext, dict)
    assert ext.get("tool") == "msi2lmp"
    assert ext.get("status") == "missing_tool"

    # Optional: if present, msi2lmp result.json should exist and be parseable,
    # but it may legitimately include absolute paths (cwd, output paths) that
    # differ between temp directories, so we do NOT byte-compare it.
    result_json = None
    rel = ext.get("result_json_path")
    if isinstance(rel, str) and rel.strip():
        cand = outdir / Path(rel)
        if cand.exists() and cand.stat().st_size > 0:
            result_json = cand

    out: dict[str, Path] = {
        "termset": termset,
        "parameterset": parameterset,
        "ff_cvff_min_bonded": frc_cvff,
        "run_manifest": manifest,
        "coord_normalization_report": coord_norm_report,
        "validation_report": validation_report,
    }
    if frc_nonbond.exists() and frc_nonbond.stat().st_size > 0:
        out["ff_nonbond_only"] = frc_nonbond
    if result_json is not None:
        out["msi2lmp_result"] = result_json
    return out


@pytest.mark.integration
def test_nist_msi2lmp_unbonded_workspace_determinism(tmp_path: Path) -> None:
    """Run the NIST msi2lmp-unbonded workspace twice and assert strict byte determinism.

    Required artifacts:
      - termset.json
      - parameterset.json
      - ff_cvff_min_bonded.frc
      - run_manifest.json

    Robustness:
      - External tool execution may be unavailable; we force msi2lmp to be missing.
      - If the wrapper still emits msi2lmp_run/result.json, assert its determinism too.
    """

    run1 = _run_once(tmp_path / "run1")
    run2 = _run_once(tmp_path / "run2")

    assert run1["termset"].read_bytes() == run2["termset"].read_bytes()
    assert run1["parameterset"].read_bytes() == run2["parameterset"].read_bytes()
    assert run1["ff_cvff_min_bonded"].read_bytes() == run2["ff_cvff_min_bonded"].read_bytes()
    assert run1["run_manifest"].read_bytes() == run2["run_manifest"].read_bytes()
    assert run1["coord_normalization_report"].read_bytes() == run2["coord_normalization_report"].read_bytes()
    assert run1["validation_report"].read_bytes() == run2["validation_report"].read_bytes()

    if "ff_nonbond_only" in run1 and "ff_nonbond_only" in run2:
        assert run1["ff_nonbond_only"].read_bytes() == run2["ff_nonbond_only"].read_bytes()

    assert _load_json(run1["run_manifest"]) == _load_json(run2["run_manifest"])

    if "msi2lmp_result" in run1 and "msi2lmp_result" in run2:
        # Smoke-check result.json invariants without requiring byte determinism
        # across different temp directories.
        r1 = _load_json(run1["msi2lmp_result"])
        r2 = _load_json(run2["msi2lmp_result"])
        assert r1.get("tool") == "msi2lmp"
        assert r2.get("tool") == "msi2lmp"
        assert r1.get("status") == "missing_tool"
        assert r2.get("status") == "missing_tool"

        # Required wrapper output artifacts must exist (stdout may be empty; stderr should be non-empty).
        for r in (r1, r2):
            outs = r.get("outputs") or {}
            assert isinstance(outs, dict)
            for k in ["stdout_file", "stderr_file", "result_json"]:
                assert isinstance(outs.get(k), str) and outs[k].strip()
                assert Path(outs[k]).exists()
            assert Path(outs["stderr_file"]).stat().st_size > 0
