# MOLSAIC V3 — minimal workspaces

Goal
- Keep usage simple: each workspace is just a small run.py you edit and run directly.
- No required config files, schemas, outputs/ folders, baselines/, or verification steps.
- Stable import surface only: usm.*, external.*, pm2mdfcar.*.

Quickstart
1) Install in editable mode
- From repo root:
  ```
  python -m pip install -e 24-MOLSAIC-V3
  ```

2) Create a minimal workspace
- Copy the minimal template and edit it in place:
  ```
  cp -r 24-MOLSAIC-V3/workspaces/_template 24-MOLSAIC-V3/workspaces/my_job
  ```
- Template script: [workspaces/_template/run.py](24-MOLSAIC-V3/workspaces/_template/run.py:1)

3) Run it
- Directly execute your script (no config required):
  ```
  python 24-MOLSAIC-V3/workspaces/my_job/run.py
  ```

What to import (stable surface)
- Core IO and model (table-first structures):
  - [usm.io.car.load_car()](24-MOLSAIC-V3/src/usm/io/car.py:128), [usm.io.car.save_car()](24-MOLSAIC-V3/src/usm/io/car.py:187)
  - [usm.io.mdf](24-MOLSAIC-V3/src/usm/io/mdf.py), [usm.io.pdb](24-MOLSAIC-V3/src/usm/io/pdb.py)
- Optional helpers for MXN-like edits:
  - [usm.ops.selection.split_threshold()](24-MOLSAIC-V3/src/usm/ops/selection.py:15)
  - [usm.ops.selection.pair_oh_by_distance()](24-MOLSAIC-V3/src/usm/ops/selection.py:34)
  - [usm.ops.selection.count_by_side()](24-MOLSAIC-V3/src/usm/ops/selection.py:71)
  - [usm.ops.mdf_conn_preserve.key_from_row()](24-MOLSAIC-V3/src/usm/ops/mdf_conn_preserve.py:23), [usm.ops.mdf_conn_preserve.cleanse_connections_raw()](24-MOLSAIC-V3/src/usm/ops/mdf_conn_preserve.py:57)
- External tools (optional):
  - [external.adapter.resolve_executable()](24-MOLSAIC-V3/src/external/adapter.py:180)
  - [external.packmol.run()](24-MOLSAIC-V3/src/external/packmol.py:46)
  - [external.msi2namd.run()](24-MOLSAIC-V3/src/external/msi2namd.py:96)
  - [external.msi2lmp.run()](24-MOLSAIC-V3/src/external/msi2lmp.py:68)
- Hydration composition (optional):
  - [pm2mdfcar.build()](24-MOLSAIC-V3/src/pm2mdfcar/__init__.py:392)

Minimal examples (sketches)
- Edit a CAR next to your run.py:
  - Load with [usm.io.car.load_car()](24-MOLSAIC-V3/src/usm/io/car.py:128)
  - Modify the pandas table (usm.atoms) as you like
  - Save with [usm.io.car.save_car()](24-MOLSAIC-V3/src/usm/io/car.py:187) to a file in the same folder
- Hydration flow (if you want it):
  - Locate binaries with [external.adapter.resolve_executable()](24-MOLSAIC-V3/src/external/adapter.py:180) or hardcode paths
  - Convert templates via [external.msi2namd.run()](24-MOLSAIC-V3/src/external/msi2namd.py:96)
  - Pack with [external.packmol.run()](24-MOLSAIC-V3/src/external/packmol.py:46)
  - Compose final CAR/MDF with [pm2mdfcar.build()](24-MOLSAIC-V3/src/pm2mdfcar/__init__.py:392)
  - (Optional) Emit LAMMPS .data with [external.msi2lmp.run()](24-MOLSAIC-V3/src/external/msi2lmp.py:68)

Directory layout (lean)
- 24-MOLSAIC-V3/src/
  - external/     (external tool wrappers + adapter)
  - pm2mdfcar/    (hydration composition op)
  - usm/          (USM core: io + ops)
- 24-MOLSAIC-V3/workspaces/
  - _template/    (minimal run.py you can copy)
  - your jobs here (any folder name you prefer)
- 24-MOLSAIC-V3/docs/
  - Minimal philosophy, usage notes: [docs/EXTENSIBILITY.md](24-MOLSAIC-V3/docs/EXTENSIBILITY.md:1)

Conventions (by design)
- No required config.json. If you want one, parse it in your run.py.
- No required outputs/ baselines/ logs/ summary.json. Write files next to your script or wherever you prefer.
- No workspace naming rules. Use any folder names under workspaces/.
- Only import from usm.*, external.*, pm2mdfcar.*. Avoid sys.path hacks.

Notes on existing folders
- Some existing workspaces still use configs and outputs folders for historical reasons; they continue to run unchanged.
- For new workspaces, prefer the minimal template: [workspaces/_template/run.py](24-MOLSAIC-V3/workspaces/_template/run.py:1)

Troubleshooting
- ImportError for usm/external/pm2mdfcar: make sure you’ve run editable install
  ```
  python -m pip install -e 24-MOLSAIC-V3
  ```
- External tools not found: pass absolute paths to [external.adapter.resolve_executable()](24-MOLSAIC-V3/src/external/adapter.py:180) or hardcode the full path in your run.py.


## Alumina ions-in-water workflows (Packmol)

These new workspaces build alumina surfaces with ions interspersed in the aqueous region using Packmol, instead of embedding ions in the slab templates. Ion totals per surface match the legacy templates to preserve stoichiometry while enabling mobility in solution.

Documentation:
- See the detailed workflow guide: [docs/ions-in-water-workflows.md](docs/ions-in-water-workflows.md:1)

Workspaces:
- AS2: [workspaces/alumina_AS2_ions_v1/run.py](workspaces/alumina_AS2_ions_v1/run.py:1)
- AS5: [workspaces/alumina_AS5_ions_v1/run.py](workspaces/alumina_AS5_ions_v1/run.py:1)
- AS10: [workspaces/alumina_AS10_ions_v1/run.py](workspaces/alumina_AS10_ions_v1/run.py:1)
- AS12: [workspaces/alumina_AS12_ions_v1/run.py](workspaces/alumina_AS12_ions_v1/run.py:1)

Quickstart (from repo root):
- AS2:  python3 workspaces/alumina_AS2_ions_v1/run.py --config config.json
- AS5:  python3 workspaces/alumina_AS5_ions_v1/run.py --config config.json
- AS10: python3 workspaces/alumina_AS10_ions_v1/run.py --config config.json
- AS12: python3 workspaces/alumina_AS12_ions_v1/run.py --config config.json

Outputs per run:
- Packed PDB: outputs/hydrated_ASX_ions.pdb
- Composed CAR/MDF: outputs/converted/ASX_hydrated.{car,mdf}
- LAMMPS data: outputs/simulation/ASX_ions_hydration.data
- Manifest: outputs/summary.json (conforms to [docs/manifest.v1.schema.json](docs/manifest.v1.schema.json:1))
- Ion z-distributions: outputs/ion_z_histogram.{json,csv}

Notes:
- Ion counts default to the legacy totals embedded in the original surface templates; override via config.ions.counts_override when needed.
- Deterministic Packmol is enabled via a seed in config (see summary “params.packmol_seed”).
- When an ion count is zero, the generated Packmol deck omits that ion’s structure block to avoid STOP 171.
