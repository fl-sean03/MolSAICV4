import os
import sys
from pathlib import Path
import subprocess
import pytest

# Ensure repo root import
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from external import msi2namd, msi2lmp  # noqa: E402


def _pick_existing_exe():
    for cand in ("/bin/true", "/usr/bin/true", "/bin/echo", "/usr/bin/echo"):
        if Path(cand).exists():
            return cand
    return None


@pytest.mark.unit
def test_msi2namd_wrapper_schema_monkeypatch(tmp_path: Path, monkeypatch):
    # Arrange: create minimal inputs
    mdf = tmp_path / "AS2.mdf"
    car = tmp_path / "AS2.car"
    prm = tmp_path / "parameters.prm"
    mdf.write_text("! dummy MDF\n", encoding="utf-8")
    # CAR content not used by wrapper, but ensure file exists
    car.write_text("! dummy CAR\n", encoding="utf-8")
    prm.write_text("* parameters\n", encoding="utf-8")

    outdir = tmp_path / "outputs"
    outdir.mkdir(parents=True, exist_ok=True)
    out_prefix = outdir / "AS2"

    exe = _pick_existing_exe()
    if exe is None:
        pytest.skip("No simple system binary available for existence check")

    # Fake subprocess.run inside the msi2namd module only
    def fake_run(cmd, cwd=None, env=None, capture_output=True, text=True, timeout=10, check=True):
        # Determine output file base from "-output" arg
        assert "-output" in cmd
        name = cmd[cmd.index("-output") + 1]
        cwd_path = Path(cwd or ".")
        (cwd_path / f"{name}.pdb").write_text("ATOM  ....\n", encoding="utf-8")
        (cwd_path / f"{name}.psf").write_text("PSF   ....\n", encoding="utf-8")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(msi2namd, "subprocess", pytest.importorskip("subprocess"))
    monkeypatch.setattr(msi2namd.subprocess, "run", fake_run)

    # Act
    res = msi2namd.run(
        mdf_file=str(mdf),
        car_file=str(car),
        prm_file=str(prm),
        residue="AS2",
        output_prefix=str(out_prefix),
        exe_path=exe,
        timeout_s=5,
    )

    # Assert: schema and artifacts
    assert isinstance(res, dict)
    assert res.get("tool") == "msi2namd"
    assert res.get("status") == "ok"
    assert "outputs_sha256" in res and isinstance(res["outputs_sha256"], dict)

    assert "duration_s" in res and isinstance(res["duration_s"], float)
    assert isinstance(res.get("stdout", ""), str)
    assert isinstance(res.get("stderr", ""), str)

    assert Path(res["pdb_file"]).exists()
    assert Path(res["psf_file"]).exists()
    outs = res.get("outputs", {})
    assert outs and Path(outs["pdb_file"]).exists() and Path(outs["psf_file"]).exists()


@pytest.mark.unit
def test_msi2lmp_wrapper_schema_and_normalization(tmp_path: Path, monkeypatch):
    # Arrange: base car/mdf and frc
    base = tmp_path / "hydrated"
    car = tmp_path / "hydrated.car"
    mdf = tmp_path / "hydrated.mdf"
    frc = tmp_path / "cvff.frc"

    # Provide a PBC line that wrapper can parse for a/b/c
    car.write_text("! header\nPBC 10.0 20.0 30.0 90.0 90.0 90.0\n! atoms...\n", encoding="utf-8")
    mdf.write_text("! mdf\n", encoding="utf-8")
    frc.write_text("* frc\n", encoding="utf-8")

    outdir = tmp_path / "sim"
    out_prefix = outdir / "sample_hydration"
    outdir.mkdir(parents=True, exist_ok=True)

    exe = _pick_existing_exe()
    if exe is None:
        pytest.skip("No simple system binary available for existence check")

    # Fake run inside msi2lmp to emit a minimal LAMMPS .data in base dir
    def fake_run(cmd, cwd=None, env=None, capture_output=True, text=True, timeout=10, check=True):
        base_stem = cmd[1]
        cwd_path = Path(cwd or ".")
        data_path = cwd_path / f"{base_stem}.data"
        # Minimal header and Atoms section (style full), with z values -1.0 and 0.0
        data_text = "\n".join(
            [
                "LAMMPS data (stub)",
                "",
                "0.0 9.0 xlo xhi",
                "0.0 19.0 ylo yhi",
                "-1.0 29.0 zlo zhi",
                "",
                "Atoms # full",
                "1 1 1 -0.5 1.0 2.0 -1.0",
                "2 1 1  0.5 3.0 4.0  0.0",
                "",
            ]
        )
        data_path.write_text(data_text + "\n", encoding="utf-8")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(msi2lmp, "subprocess", pytest.importorskip("subprocess"))
    monkeypatch.setattr(msi2lmp.subprocess, "run", fake_run)

    # Act
    res = msi2lmp.run(
        base_name=str(base),  # wrapper will resolve to hydrated.car/mdf in same dir
        frc_file=str(frc),
        exe_path=exe,
        output_prefix=str(out_prefix),
        normalize_xy=True,
        normalize_z_to=50.0,
        timeout_s=5,
    )

    # Assert
    assert isinstance(res, dict)
    assert res.get("tool") == "msi2lmp"
    assert res.get("status") == "ok"
    assert "outputs_sha256" in res and isinstance(res["outputs_sha256"], dict)

    outs = res.get("outputs", {})
    assert isinstance(outs, dict)
    assert Path(outs["stdout_file"]).exists()
    assert Path(outs["stderr_file"]).exists()
    assert Path(outs["result_json"]).exists()

    # Hashes exist at least for primary artifacts
    assert "lmp_data_file" in res["outputs_sha256"]
    assert "stdout_file" in res["outputs_sha256"]
    assert "stderr_file" in res["outputs_sha256"]

    out_file = Path(res["lmp_data_file"])
    assert out_file.exists() and out_file.stat().st_size > 0

    text = out_file.read_text(encoding="utf-8")
    # Header normalization expectations
    assert "0.000000 10.000000 xlo xhi" in text
    assert "0.000000 20.000000 ylo yhi" in text
    assert "0.000000 50.000000 zlo zhi" in text
    # Z shift so min(z)=0
    assert "1 1 1 -0.5 1.0 2.0 0.000000" in text
    assert "2 1 1 0.5 3.0 4.0 1.000000" in text


@pytest.mark.unit
def test_msi2lmp_missing_tool_writes_result_json(tmp_path: Path):
    # Arrange: base car/mdf and frc
    base = tmp_path / "hydrated"
    car = tmp_path / "hydrated.car"
    mdf = tmp_path / "hydrated.mdf"
    frc = tmp_path / "cvff.frc"
    car.write_text("! header\nPBC 1.0 1.0 1.0 90 90 90\n", encoding="utf-8")
    mdf.write_text("! mdf\n", encoding="utf-8")
    frc.write_text("* frc\n", encoding="utf-8")

    outdir = tmp_path / "sim"
    out_prefix = outdir / "sample_hydration"
    outdir.mkdir(parents=True, exist_ok=True)

    missing_exe = str(tmp_path / "does_not_exist" / "msi2lmp")

    # Act
    res = msi2lmp.run(
        base_name=str(base),
        frc_file=str(frc),
        exe_path=missing_exe,
        output_prefix=str(out_prefix),
        timeout_s=1,
    )

    # Assert
    assert isinstance(res, dict)
    assert res.get("tool") == "msi2lmp"
    assert res.get("status") == "missing_tool"
    assert "outputs_sha256" in res and isinstance(res["outputs_sha256"], dict)

    outs = res.get("outputs", {})
    assert Path(outs["stdout_file"]).exists()
    assert Path(outs["stderr_file"]).exists()
    assert Path(outs["result_json"]).exists()
    assert "Executable not found" in Path(outs["stderr_file"]).read_text(encoding="utf-8")