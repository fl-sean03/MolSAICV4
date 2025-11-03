Minimal Extensibility Guide — MolSAIC V3

Purpose
- Keep workspaces as tiny, self-owned Python scripts (run.py) with zero required config files, schemas, or directory conventions.
- You decide paths and outputs inside your script. No required outputs/, baselines/, logs/, or summary.json.
- Only stable imports: usm.*, external.*, pm2mdfcar.*.

Philosophy
- No config by default. If you want a config, read it yourself in your run.py.
- No manifest or verification schema. Test or compare outputs however you prefer.
- No workspace naming/versioning rules. Use whatever folder names you like under workspaces/.

Minimal layout
- Create any folder under workspaces/, add a run.py, and write your steps.
- Example template: [workspaces/_template/run.py](24-MOLSAIC-V3/workspaces/_template/run.py:1)

Stable imports (keep these consistent)
- Core IO and model:
  - [usm.io.car.load_car()](usm/io/car.py:128), [usm.io.car.save_car()](usm/io/car.py:187)
- Common helpers (optional):
  - [usm.ops.selection.split_threshold()](usm/ops/selection.py:1)
  - [usm.ops.selection.pair_oh_by_distance()](usm/ops/selection.py:1)
  - [usm.ops.selection.count_by_side()](usm/ops/selection.py:1)
  - [usm.ops.mdf_conn_preserve.key_from_row()](usm/ops/mdf_conn_preserve.py:1), [usm.ops.mdf_conn_preserve.cleanse_connections_raw()](usm/ops/mdf_conn_preserve.py:1)
- External tools (optional):
  - [external.adapter.resolve_executable()](24-MOLSAIC-V3/src/external/adapter.py:180)
  - [external.packmol.run()](24-MOLSAIC-V3/src/external/packmol.py:46)
  - [external.msi2namd.run()](24-MOLSAIC-V3/src/external/msi2namd.py:96)
  - [external.msi2lmp.run()](24-MOLSAIC-V3/src/external/msi2lmp.py:68)
- Hydration composition (optional):
  - [pm2mdfcar.build()](24-MOLSAIC-V3/src/pm2mdfcar/__init__.py:392)

Quickstart
1) Editable install:
   - pip install -e 24-MOLSAIC-V3
2) Make a new workspace and copy the template run.py:
   - cp -r 24-MOLSAIC-V3/workspaces/_template 24-MOLSAIC-V3/workspaces/my_job
   - Edit 24-MOLSAIC-V3/workspaces/my_job/run.py to point at your inputs; write outputs right next to the script (HERE).
3) Run it:
   - python 24-MOLSAIC-V3/workspaces/my_job/run.py

Minimal examples
- MXN F-termination (sketch)
  - Load a CAR via [usm.io.car.load_car()](24-MOLSAIC-V3/src/usm/io/car.py:128)
  - Edit the pandas table (usm.atoms) as you wish
  - Save with [usm.io.car.save_car()](24-MOLSAIC-V3/src/usm/io/car.py:187) to a file in the same folder
- Hydration (sketch)
  - Resolve executables with [external.adapter.resolve_executable()](24-MOLSAIC-V3/src/external/adapter.py:180) or hardcode paths
  - Run [external.msi2namd.run()](24-MOLSAIC-V3/src/external/msi2namd.py:96) for surface and water into the current directory
  - Run [external.packmol.run()](24-MOLSAIC-V3/src/external/packmol.py:46) with a deck near your script
  - Compose CAR/MDF with [pm2mdfcar.build()](24-MOLSAIC-V3/src/pm2mdfcar/__init__.py:392) writing outputs into HERE
  - Optionally run [external.msi2lmp.run()](24-MOLSAIC-V3/src/external/msi2lmp.py:68) to emit a .data file next to run.py

Paths and assets
- Put assets (templates, decks, forcefields) alongside your run.py or in any subfolder you choose.
- Resolve paths via pathlib relative to HERE = Path(__file__).parent.
- No required assets/ layout; organize as you prefer per job.

What we intentionally removed from the contract
- No required config.json (you can add one if you want).
- No outputs/, baselines/, logs/ conventions.
- No summary.json or schema verification.
- No workspace naming/versioning rules.

Tips
- Keep run.py <200 lines by moving reusable logic into your own helper functions or into usm.ops when it becomes generic.
- Prefer usm.*, external.*, pm2mdfcar.* imports only; avoid sys.path hacks.
- If you need deterministic behavior for a step, set seeds inside your script and fix tool versions as you see fit.

Notes on existing workspaces in this repo
- Some existing workspaces still use configs/outputs and verification; they continue to run as-is.
- For new workspaces, start from the minimal template above and write everything inline in run.py.