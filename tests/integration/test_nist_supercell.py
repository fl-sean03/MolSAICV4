import json
from pathlib import Path

import pytest

from usm.io.cif import load_cif  # [load_cif()](src/usm/io/cif.py:26)
from usm.ops.replicate import replicate_supercell  # [replicate_supercell()](src/usm/ops/replicate.py:34)
from usm.ops.topology import (
    perceive_periodic_bonds,
    validate_supercell,
)  # [perceive_periodic_bonds()](src/usm/ops/topology.py:11), [validate_supercell()](src/usm/ops/topology.py:88)


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_DIR = REPO_ROOT / "workspaces/NIST/nist_calf20_2x2x2_supercell"


@pytest.mark.integration
def test_nist_calf20_supercell_replication_invariants():
    """Validate stable invariants for the canonical NIST CALF-20 2x2x2 supercell.

    Intent / determinism notes:
    - This test intentionally avoids running the full workspace [run.py](workspaces/NIST/nist_calf20_2x2x2_supercell/run.py:1)
      because that path depends on an external `msi2lmp` binary (machine-specific).
    - Instead we assert stable *behavioral* invariants from the pure-Python pipeline:
      CIF import (+ symmetry expansion), periodic bond perception, and supercell replication.
    """

    cfg = json.loads((WORKSPACE_DIR / "config.json").read_text(encoding="utf-8"))
    dims = (cfg.get("params") or {}).get("supercell_dims") or [2, 2, 2]
    assert list(dims) == [2, 2, 2]  # canonical expectation for this workspace

    cif_rel = (cfg.get("inputs") or {}).get("cif")
    assert isinstance(cif_rel, str) and cif_rel.strip()
    cif_path = (REPO_ROOT / cif_rel).resolve()
    assert cif_path.exists(), f"Missing CIF input: {cif_path}"

    # 1) Load CIF with symmetry expansion (as used by the workspace)
    usm_unit = load_cif(str(cif_path), expand_symmetry=True)
    # 2) Ensure periodic bond image flags are consistent via MIC perception
    usm_unit = perceive_periodic_bonds(usm_unit)
    # 3) Replicate to 2x2x2 and validate connectivity invariants
    usm_super = replicate_supercell(usm_unit, na=2, nb=2, nc=2)
    rep = validate_supercell(usm_super)

    assert rep.get("n_atoms") == 352
    assert rep.get("n_bonds") == 464
    assert rep.get("n_connected_components") == 1
