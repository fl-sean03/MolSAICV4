from __future__ import annotations

from pathlib import Path

import pytest

from external import msi2lmp


def _write_frc(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.unit
def test_build_argv_autodetect_cvff_labeled_uses_classI_and_frc_relpath(tmp_path: Path) -> None:
    wd = tmp_path / "wd"
    wd.mkdir(parents=True, exist_ok=True)
    frc_dir = tmp_path / "frc_files"
    frc_dir.mkdir(parents=True, exist_ok=True)

    exe = tmp_path / "msi2lmp.exe"
    staged_frc = _write_frc(
        frc_dir / "ff_cvff.frc",
        "!BIOSYM forcefield 1\n#define cvff\n#atom_types\tcvff\n",
    )

    argv = msi2lmp._build_msi2lmp_argv(
        exe=exe,
        base_stem="MXN",
        wd=wd,
        staged_frc=staged_frc,
        forcefield_class=None,
        use_f_flag=None,
        ignore=False,
        print_level=None,
    )

    assert argv[:2] == [str(exe), "MXN"]
    assert "-class" in argv and argv[argv.index("-class") + 1] == "I"
    assert "-frc" in argv
    frc_arg = argv[argv.index("-frc") + 1]
    assert frc_arg == "../frc_files/ff_cvff.frc"
    assert "-f" not in argv


@pytest.mark.unit
def test_build_argv_autodetect_non_cvff_uses_legacy_f_stem_no_class(tmp_path: Path) -> None:
    wd = tmp_path / "wd"
    wd.mkdir(parents=True, exist_ok=True)
    frc_dir = tmp_path / "frc_files"
    frc_dir.mkdir(parents=True, exist_ok=True)

    exe = tmp_path / "msi2lmp.exe"
    staged_frc = _write_frc(
        frc_dir / "ff_minimal.frc",
        "#atom_types\n#nonbond(12-6)\n",
    )

    argv = msi2lmp._build_msi2lmp_argv(
        exe=exe,
        base_stem="MXN",
        wd=wd,
        staged_frc=staged_frc,
        forcefield_class=None,
        use_f_flag=None,
        ignore=False,
        print_level=None,
    )

    assert argv[:2] == [str(exe), "MXN"]
    assert argv[2:] == ["-f", "ff_minimal"]
    assert "-class" not in argv
    assert "-frc" not in argv


@pytest.mark.unit
def test_build_argv_force_modern_via_forcefield_class(tmp_path: Path) -> None:
    wd = tmp_path / "wd"
    wd.mkdir(parents=True, exist_ok=True)
    frc_dir = tmp_path / "frc_files"
    frc_dir.mkdir(parents=True, exist_ok=True)

    exe = tmp_path / "msi2lmp.exe"
    staged_frc = _write_frc(frc_dir / "ff_any.frc", "#atom_types\n")

    argv = msi2lmp._build_msi2lmp_argv(
        exe=exe,
        base_stem="MXN",
        wd=wd,
        staged_frc=staged_frc,
        forcefield_class="II",
        use_f_flag=None,
        ignore=False,
        print_level=None,
    )

    assert "-class" in argv and argv[argv.index("-class") + 1] == "II"
    assert "-frc" in argv
    assert "-f" not in argv


@pytest.mark.unit
def test_build_argv_force_legacy_via_use_f_flag_true_overrides_class(tmp_path: Path) -> None:
    wd = tmp_path / "wd"
    wd.mkdir(parents=True, exist_ok=True)
    frc_dir = tmp_path / "frc_files"
    frc_dir.mkdir(parents=True, exist_ok=True)

    exe = tmp_path / "msi2lmp.exe"
    staged_frc = _write_frc(frc_dir / "ff_any.frc", "#define cvff\n")

    argv = msi2lmp._build_msi2lmp_argv(
        exe=exe,
        base_stem="MXN",
        wd=wd,
        staged_frc=staged_frc,
        forcefield_class="I",
        use_f_flag=True,
        ignore=False,
        print_level=None,
    )

    assert argv[2:] == ["-f", "ff_any"]
    assert "-class" not in argv
    assert "-frc" not in argv


@pytest.mark.unit
def test_build_argv_diagnostics_ordering_is_stable(tmp_path: Path) -> None:
    wd = tmp_path / "wd"
    wd.mkdir(parents=True, exist_ok=True)
    frc_dir = tmp_path / "frc_files"
    frc_dir.mkdir(parents=True, exist_ok=True)

    exe = tmp_path / "msi2lmp.exe"
    staged_frc = _write_frc(
        frc_dir / "ff_cvff.frc",
        "#define cvff\n#atom_types\tcvff\n",
    )

    argv = msi2lmp._build_msi2lmp_argv(
        exe=exe,
        base_stem="MXN",
        wd=wd,
        staged_frc=staged_frc,
        forcefield_class=None,
        use_f_flag=None,
        ignore=True,
        print_level=2,
    )

    # Expected stable ordering: exe base -ignore -print N -class I -frc rel
    assert argv[:2] == [str(exe), "MXN"]
    assert argv[2:6] == ["-ignore", "-print", "2", "-class"]
    assert argv[6] == "I"
    assert argv[7] == "-frc"
    assert argv[8] == "../frc_files/ff_cvff.frc"

