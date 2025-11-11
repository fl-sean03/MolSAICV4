import pytest
from pathlib import Path
from typing import List
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from usm.io.mdf import load_mdf, save_mdf


def _mdf_with_formal_charges(tokens: List[str]) -> str:
    lines = []
    lines.append("!BIOSYM molecular_data 4")
    lines.append("")
    lines.append("!Date: Tue Jan 01 00:00:00 2000   Test MDF")
    lines.append("")
    lines.append("#topology")
    lines.append("")
    lines.append("@column 1 element")
    lines.append("@column 2 atom_type")
    lines.append("@column 3 charge_group")
    lines.append("@column 4 isotope")
    lines.append("@column 5 formal_charge")
    lines.append("@column 6 charge")
    lines.append("@column 7 switching_atom")
    lines.append("@column 8 oop_flag")
    lines.append("@column 9 chirality_flag")
    lines.append("@column 10 occupancy")
    lines.append("@column 11 xray_temp_factor")
    lines.append("@column 12 connections")
    lines.append("")
    lines.append("@molecule TEST")
    lines.append("")
    for idx, tok in enumerate(tokens, start=1):
        prefix = f"XXXX_1:A{idx}"
        element = "C"
        atom_type = "c*"
        charge_group = "?"
        isotope = "0"
        charge = "-0.1000"
        switching_atom = "0"
        oop_flag = "0"
        chirality_flag = "0"
        occupancy = "1.0000"
        xrf = "0.0000"
        line = f"{prefix} {element} {atom_type} {charge_group} {isotope} {tok} {charge} {switching_atom} {oop_flag} {chirality_flag} {occupancy} {xrf}"
        lines.append(line)
    lines.append("")
    lines.append("#end")
    return "\n".join(lines) + "\n"


@pytest.mark.unit
def test_formal_charge_tokens_roundtrip(tmp_path: Path):
    tokens = ["0", "1+", "2-", "1/2+"]
    mdf_text = _mdf_with_formal_charges(tokens)
    in_path = tmp_path / "in.mdf"
    in_path.write_text(mdf_text, encoding="utf-8")

    u1 = load_mdf(str(in_path))
    fc1 = u1.atoms["formal_charge"].astype(str).tolist()
    assert fc1 == tokens

    out_path = tmp_path / "out.mdf"
    save_mdf(u1, str(out_path), preserve_headers=False)

    u2 = load_mdf(str(out_path))
    fc2 = u2.atoms["formal_charge"].astype(str).tolist()
    assert fc2 == tokens

    import numpy as np
    ch1 = u1.atoms["charge"].to_numpy()
    ch2 = u2.atoms["charge"].to_numpy()
    assert np.allclose(ch2, ch1, atol=1e-6, rtol=0)

    occ2 = u2.atoms["occupancy"].to_numpy()
    xrf2 = u2.atoms["xray_temp_factor"].to_numpy()
    assert np.allclose(occ2, 1.0)
    assert np.allclose(xrf2, 0.0)