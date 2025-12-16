USM on LB_SF_carmdf — Round-trip and Ops Demos (v1)

Purpose
- Exercise USM I/O and operations on curated Materials Studio structures in assets/LB_SF_carmdf.
- Validate round-trip fidelity (CAR and MDF), composition of CAR coordinates with MDF topology, and core ops: selection, transforms, replication, merge, renumber.
- Surface proficiencies and current limits (notably orthorhombic-only wrap/replicate).

Inputs
- [assets/LB_SF_carmdf/FAPbBr2I.car](assets/LB_SF_carmdf/FAPbBr2I.car) + [assets/LB_SF_carmdf/FAPbBr2I.mdf](assets/LB_SF_carmdf/FAPbBr2I.mdf) — orthorhombic
- [assets/LB_SF_carmdf/R-2-3-FMBA_pi.car](assets/LB_SF_carmdf/R-2-3-FMBA_pi.car) + [assets/LB_SF_carmdf/R-2-3-FMBA_pi.mdf](assets/LB_SF_carmdf/R-2-3-FMBA_pi.mdf) — orthorhombic
- [assets/LB_SF_carmdf/PbI2_sup.car](assets/LB_SF_carmdf/PbI2_sup.car) + [assets/LB_SF_carmdf/PbI2_sup.mdf](assets/LB_SF_carmdf/PbI2_sup.mdf) — non-orthorhombic (gamma≈120°)
- [assets/LB_SF_carmdf/R-2-FMBA_PbI4_new_298K_red_cif_checked.car](assets/LB_SF_carmdf/R-2-FMBA_PbI4_new_298K_red_cif_checked.car) + [assets/LB_SF_carmdf/R-2-FMBA_PbI4_new_298K_red_cif_checked.mdf](assets/LB_SF_carmdf/R-2-FMBA_PbI4_new_298K_red_cif_checked.mdf) — monoclinic (beta≈99.14°; hybrid perovskite+organic)

USM APIs referenced
- CAR I/O: [load_car()](src/usm/io/car.py:128), [save_car()](src/usm/io/car.py:187)
- MDF I/O: [load_mdf()](src/usm/io/mdf.py:243), [save_mdf()](src/usm/io/mdf.py:378)
- PDB export: [save_pdb()](src/usm/io/pdb.py:69)
- Compose coords+bonds: [compose_on_keys()](src/usm/ops/compose.py:13)
- Selection: [select_by_element()](src/usm/ops/select.py:55)
- Transforms: [translate()](src/usm/ops/transform.py:26), [rotation_matrix_from_axis_angle()](src/usm/ops/transform.py:38), [rotate()](src/usm/ops/transform.py:62), [wrap_to_cell()](src/usm/ops/transform.py:91)
- Replication: [replicate_supercell()](src/usm/ops/replicate.py:34) (orthorhombic only)
- Merge: [merge_structures()](src/usm/ops/merge.py:59)
- Renumber: [renumber_atoms()](src/usm/ops/renumber.py:30)

Scenarios
- A — FAPbBr2I (orthorhombic): CAR+MDF round-trips, compose, translate+rotate+wrap, replicate 2x2x2, selections, renumber, exports.
- B — R-2-3-FMBA_pi (orthorhombic organic): CAR+MDF round-trips, transform suite, replicate 2x1x1, renumber, exports.
- C1 — PbI2_sup (non-orthorhombic layered): round-trips, selection/merge/renumber; wrap/replicate intentionally no-op/unsupported (documented).
- C2 — R-2-FMBA_PbI4 (monoclinic hybrid): compose CAR coords with MDF topology; selection/merge/renumber; wrap/replicate no-op/unsupported.

How to run
- Configurable runner lives at [workspaces/other/usm_lb_sf_carmdf_v1/run.py](workspaces/other/usm_lb_sf_carmdf_v1/run.py:1) with config [workspaces/other/usm_lb_sf_carmdf_v1/config.json](workspaces/other/usm_lb_sf_carmdf_v1/config.json:1).
- Execute:
  - python workspaces/other/usm_lb_sf_carmdf_v1/run.py --config workspaces/other/usm_lb_sf_carmdf_v1/config.json
- Outputs will be created under workspaces/other/usm_lb_sf_carmdf_v1/outputs/{A,B,C1,C2}/ with artifacts (.car/.mdf/.pdb) and per-scenario summary.json.

Validation patterns
- CAR round-trip:
  - u1 = [load_car()](src/usm/io/car.py:128); write with [save_car()](src/usm/io/car.py:187) preserve_headers=True; u2 = [load_car()](src/usm/io/car.py:128)
  - Assert preserved_text.car_header_lines equal; xyz arrays allclose at 1e-5.
- MDF round-trip:
  - m1 = [load_mdf()](src/usm/io/mdf.py:243); write with [save_mdf()](src/usm/io/mdf.py:378) preserve_headers=True, write_normalized_connections=False; m2 = [load_mdf()](src/usm/io/mdf.py:243)
  - Assert preserved_text.mdf_header_lines equal; map name→connections_raw equal.
- Compose CAR+MDF:
  - composed = [compose_on_keys()](src/usm/ops/compose.py:13)(car, mdf); expect bonds>0; coords unchanged vs CAR for identical key rows.
- Replication:
  - Orthorhombic only (angles ~ 90°): [replicate_supercell()](src/usm/ops/replicate.py:34)(u, na, nb, nc); assert atom count scales and cell a/b/c scaled.
- Determinism:
  - Re-running a scenario yields identical counts/cell in summary.json (byte-level artifact equivalence is not required).

Code snippets
1) Load, translate, rotate, wrap, save
Python
from usm.io.car import load_car, save_car  # [load_car()](src/usm/io/car.py:128), [save_car()](src/usm/io/car.py:187)
from usm.ops.transform import translate, rotation_matrix_from_axis_angle, rotate, wrap_to_cell  # [translate()](src/usm/ops/transform.py:26), [rotation_matrix_from_axis_angle()](src/usm/ops/transform.py:38), [rotate()](src/usm/ops/transform.py:62), [wrap_to_cell()](src/usm/ops/transform.py:91)

u = load_car("assets/LB_SF_carmdf/FAPbBr2I.car")
u2 = translate(u.copy(), (0.5, 0.0, 0.0))
Rz = rotation_matrix_from_axis_angle((0,0,1), 15.0)
u3 = rotate(u2, Rz)
u4 = wrap_to_cell(u3)
save_car(u4, "workspaces/other/usm_lb_sf_carmdf_v1/outputs/A/FAPbBr2I_xform.car")

2) Compose CAR+MDF to add bonds, then replicate (orthorhombic)
Python
from usm.io.car import load_car  # [load_car()](src/usm/io/car.py:128)
from usm.io.mdf import load_mdf  # [load_mdf()](src/usm/io/mdf.py:243)
from usm.ops.compose import compose_on_keys  # [compose_on_keys()](src/usm/ops/compose.py:13)
from usm.ops.replicate import replicate_supercell  # [replicate_supercell()](src/usm/ops/replicate.py:34)

car = load_car("assets/LB_SF_carmdf/FAPbBr2I.car")
mdf = load_mdf("assets/LB_SF_carmdf/FAPbBr2I.mdf")
cmpd = compose_on_keys(car, mdf)
sup = replicate_supercell(cmpd, 2, 2, 2)

Known limits to watch
- Non-orthorhombic cells (e.g., PbI2_sup gamma=120°, monoclinic beta≠90°) skip wrap/replicate by design in v0.1.
- MDF has no coordinates; USM keeps x,y,z=NaN for MDF-only loads; combine with CAR via composition to get bonds+coords.
- PDB writer is minimal; only ATOM/TER/END and optional CRYST1 when cell fully specified.

Workflow diagram (Mermaid)
flowchart TD
  A[Load CAR/MDF] --> B[Round-trip checks]
  A --> C[Compose coords+bonds]
  C --> D[Ops: select, translate, rotate, wrap, replicate, renumber, merge]
  D --> E[Export: CAR/MDF/PDB]
  E --> F[Reparse to check determinism]