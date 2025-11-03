# MolSAIC V3 — Code-first Plan and AS2 Hydration Pilot

Authoritative baseline: [MOLSAICV3/DevDoc.md](MOLSAICV3/DevDoc.md:1). This plan consolidates the simplified V3 approach and defines the first pilot to reproduce the Alumina AS2 hydration workflow producing a LAMMPS .data file.

Decision summary
- Self-contained assets will be vendored into [MOLSAICV3/assets/AluminaSurfaces](MOLSAICV3/assets/AluminaSurfaces).
- Default executables:
  - /home/sf2/LabWork/software/msi2namd.exe
  - /home/sf2/LabWork/software/packmol-20.15.3/packmol
  - /home/sf2/LabWork/software/msi2lmp.exe

Scope and out-of-scope
- In scope:
  - Minimal Python library (USM core, IO, ops) and thin wrappers for external executables
  - Code-first workspaces (run.py + config.json + outputs) with deterministic behavior
  - Reproduction of selected v1/v2 pipelines without plugin registry, YAML DSL, or executors
- Out of scope:
  - Plugin discovery/registry, entry points, dynamic loading
  - YAML pipeline specs and orchestrators
  - Event bus/state store frameworks
  - Advanced perception beyond pass-through preservation

Package naming and imports
- Python package root: molsaicv3
  - Layout: [MOLSAICV3/molsaicv3/](MOLSAICV3/molsaicv3/)
  - Subpackages:
    - [MOLSAICV3/molsaicv3/usm/](MOLSAICV3/molsaicv3/usm/)
    - [MOLSAICV3/molsaicv3/usm/io/](MOLSAICV3/molsaicv3/usm/io/)
    - [MOLSAICV3/molsaicv3/usm/ops/](MOLSAICV3/molsaicv3/usm/ops/)
    - [MOLSAICV3/molsaicv3/usm/bundle/](MOLSAICV3/molsaicv3/usm/bundle/)
    - [MOLSAICV3/molsaicv3/usm/external/](MOLSAICV3/molsaicv3/usm/external/)
- Workspaces live under [MOLSAICV3/workspaces/](MOLSAICV3/workspaces/) and import from molsaicv3.*
- External wrappers API (planned):
  - [msi2namd.run()](MOLSAICV3/usm/external/msi2namd.py:1)
  - [packmol.run()](MOLSAICV3/usm/external/packmol.py:1)
  - [msi2lmp.run()](MOLSAICV3/usm/external/msi2lmp.py:1)
  - [pm2mdfcar.build()](MOLSAICV3/usm/ops/pm2mdfcar.py:1)

Repository layout (target)
- Package
  - [MOLSAICV3/molsaicv3/__init__.py](MOLSAICV3/molsaicv3/__init__.py)
  - [MOLSAICV3/molsaicv3/usm/core/model.py](MOLSAICV3/molsaicv3/usm/core/model.py)
  - [MOLSAICV3/molsaicv3/usm/io/car.py](MOLSAICV3/molsaicv3/usm/io/car.py)
  - [MOLSAICV3/molsaicv3/usm/io/mdf.py](MOLSAICV3/molsaicv3/usm/io/mdf.py)
  - [MOLSAICV3/molsaicv3/usm/io/pdb.py](MOLSAICV3/molsaicv3/usm/io/pdb.py)
  - [MOLSAICV3/molsaicv3/usm/bundle/io.py](MOLSAICV3/molsaicv3/usm/bundle/io.py)
  - [MOLSAICV3/molsaicv3/usm/ops/surface.py](MOLSAICV3/molsaicv3/usm/ops/surface.py)
  - [MOLSAICV3/molsaicv3/usm/ops/pairing.py](MOLSAICV3/molsaicv3/usm/ops/pairing.py)
  - [MOLSAICV3/molsaicv3/usm/ops/mdf_connections.py](MOLSAICV3/molsaicv3/usm/ops/mdf_connections.py)
  - [MOLSAICV3/molsaicv3/usm/ops/pm2mdfcar.py](MOLSAICV3/molsaicv3/usm/ops/pm2mdfcar.py)
  - [MOLSAICV3/molsaicv3/usm/external/msi2namd.py](MOLSAICV3/molsaicv3/usm/external/msi2namd.py)
  - [MOLSAICV3/molsaicv3/usm/external/packmol.py](MOLSAICV3/molsaicv3/usm/external/packmol.py)
  - [MOLSAICV3/molsaicv3/usm/external/msi2lmp.py](MOLSAICV3/molsaicv3/usm/external/msi2lmp.py)
- Workspaces
  - [MOLSAICV3/workspaces/_template/run.py](MOLSAICV3/workspaces/_template/run.py)
  - [MOLSAICV3/workspaces/_template/config.json](MOLSAICV3/workspaces/_template/config.json)
  - [MOLSAICV3/workspaces/alumina_AS2_hydration_v1/run.py](MOLSAICV3/workspaces/alumina_AS2_hydration_v1/run.py)
  - [MOLSAICV3/workspaces/alumina_AS2_hydration_v1/config.json](MOLSAICV3/workspaces/alumina_AS2_hydration_v1/config.json)
- Assets (vendored)
  - [MOLSAICV3/assets/AluminaSurfaces/templates/AS2.car](MOLSAICV3/assets/AluminaSurfaces/templates/AS2.car)
  - [MOLSAICV3/assets/AluminaSurfaces/templates/AS2.mdf](MOLSAICV3/assets/AluminaSurfaces/templates/AS2.mdf)
  - [MOLSAICV3/assets/AluminaSurfaces/templates/WAT.car](MOLSAICV3/assets/AluminaSurfaces/templates/WAT.car)
  - [MOLSAICV3/assets/AluminaSurfaces/templates/WAT.mdf](MOLSAICV3/assets/AluminaSurfaces/templates/WAT.mdf)
  - [MOLSAICV3/assets/AluminaSurfaces/packmol/packmol_AS2.inp](MOLSAICV3/assets/AluminaSurfaces/packmol/packmol_AS2.inp)
  - [MOLSAICV3/assets/AluminaSurfaces/prm_files/parameters.prm](MOLSAICV3/assets/AluminaSurfaces/prm_files/parameters.prm)
  - [MOLSAICV3/assets/AluminaSurfaces/frc_files/cvff_IFF_metal_oxides_v2.frc](MOLSAICV3/assets/AluminaSurfaces/frc_files/cvff_IFF_metal_oxides_v2.frc)
- Docs
  - [MOLSAICV3/docs/HYDRATION_AS2.md](MOLSAICV3/docs/HYDRATION_AS2.md)
  - [MOLSAICV3/docs/QUICKSTART.md](MOLSAICV3/docs/QUICKSTART.md)
  - [MOLSAICV3/docs/WORKFLOWS.md](MOLSAICV3/docs/WORKFLOWS.md)
  - [MOLSAICV3/docs/ACCEPTANCE.md](MOLSAICV3/docs/ACCEPTANCE.md)
  - [MOLSAICV3/docs/PLAN_V3.md](MOLSAICV3/docs/PLAN_V3.md)

Pilot 0: Reproduce Alumina AS2 hydration (.data)
- Source pipeline: [workflows/pipeline-alumina-AS2-hydration.yaml](workflows/pipeline-alumina-AS2-hydration.yaml:1)
- Steps to mirror (code-first):
  1) Convert AS2 to PDB and PSF using [msi2namd.run()](MOLSAICV3/usm/external/msi2namd.py:1)
  2) Convert WAT to PDB and PSF using [msi2namd.run()](MOLSAICV3/usm/external/msi2namd.py:1)
  3) Assemble hydrated slab via [packmol.run()](MOLSAICV3/usm/external/packmol.py:1) with deck packmol_AS2.inp → hydrated_AS2.pdb
  4) Convert hydrated PDB to CAR and MDF via [pm2mdfcar.build()](MOLSAICV3/usm/ops/pm2mdfcar.py:1), set cell c to 81.397 Å, normalized MDF connections, deterministic renumber
  5) Generate LAMMPS .data via [msi2lmp.run()](MOLSAICV3/usm/external/msi2lmp.py:1), rename to simulation/AS2_hydration.data, optionally normalize header XY and Z

External wrappers contract
- [msi2namd.run()](MOLSAICV3/usm/external/msi2namd.py:1)
  - Inputs: mdf_file, car_file, prm_file, residue, output_prefix, exe_path, timeout_s=600
  - Outputs: { pdb_file, psf_file, logs, duration_s }
  - Notes: use absolute exe_path; build env PATH including exe dir; ensure residue ≤ 4 chars
- [packmol.run()](MOLSAICV3/usm/external/packmol.py:1)
  - Inputs: deck_path, exe_path, timeout_s=600
  - Outputs: { packed_structure, logs, duration_s }
  - Notes: verify referenced PDBs exist in cwd; respect output filename in deck
- [msi2lmp.run()](MOLSAICV3/usm/external/msi2lmp.py:1)
  - Inputs: base_name, frc_file, exe_path, output_prefix=None, normalize_xy=True, normalize_z_to=None, timeout_s=600
  - Outputs: { lmp_data_file, stdout, stderr, duration_s }
  - Notes: run in directory with base_name.{car,mdf}; expected default output is base_name.data; rename to output_prefix.data when provided; post-normalize header and Z if configured

pm2mdfcar via USM (design)
- Load hydrated_AS2.pdb coordinates
- Load templates AS2 and WAT (CAR+MDF) into USM tables
- Compose topology: assign labels/types per template to PDB-derived coordinates; preserve intra-species bonds where available
- Set cell: a and b preserved from AS2 template; c set to 81.397; recenter and wrap to [0, L) as needed
- Deterministic renumber (aid equals row order), stable sort keys
- MDF export in normalized mode; CAR export with numeric PBC header
- Outputs: converted/AS2_hydrated.car, converted/AS2_hydrated.mdf, plus build manifest with counts and cell

Acceptance criteria for Pilot 0
- simulation/AS2_hydration.data exists and loads in downstream tools
- converted/AS2_hydrated.car and .mdf exist; atom counts match; labels align; CAR has numeric PBC
- Cell c equals 81.397 Å; XY equals template values when normalize_xy=True
- Summary manifest includes inputs, parameters, counts, cell, timings, and output paths
- Re-running with the same config yields identical structured summary values (timestamps excluded)

Determinism and reproducibility
- All operations deterministic; no RNG required for this pipeline
- File outputs confined to workspace outputs/; input assets read-only under assets/

Mermaid
flowchart LR
  A[Assets AS2 WAT prm frc deck] --> B[msi2namd wrapper]
  B --> C[PDBs AS2 WAT]
  C --> D[packmol wrapper]
  D --> E[hydrated_AS2 pdb]
  E --> F[pm2mdfcar build]
  F --> G[AS2_hydrated car mdf]
  G --> H[msi2lmp wrapper]
  H --> I[AS2_hydration data]

Milestones and deliverables
- M0 Pilot AS2 Hydration (this plan)
  - Vendor assets under assets/AluminaSurfaces
  - Implement external wrappers and pm2mdfcar
  - Scaffold workspace alumina_AS2_hydration_v1 and run end-to-end
  - Write [MOLSAICV3/docs/HYDRATION_AS2.md](MOLSAICV3/docs/HYDRATION_AS2.md) and add integration test
- M1 Baseline library
  - USM IO and core ops; workspace template; centralize surface and counts helpers
- M2 Consolidation
  - Add pairing and MDF connection helpers; finalize placement/selection manifests
- M3 Visualization and CSR utilities
  - Add CSR selection utilities; optional plotting hooks; tests
- M4 Documentation and quickstart
  - Finish docs set; acceptance checklist; decommission 18-UnifiedStructs post-parity

Risks and mitigations
- msi2lmp sensitivity to MDF dialects: export normalized connections and minimal blocks; validate labels ordering early
- External executable availability: document absolute paths in workspace config; detect and error clearly if missing
- Asset drift: vendor minimal inputs; pin versions and checksums in assets manifest

Work items (synced to TODO)
- Decide package import root and record here (molsaicv3) → adopted
- Vendor AS2 assets into assets/AluminaSurfaces
- Implement [msi2namd.run()](MOLSAICV3/usm/external/msi2namd.py:1), [packmol.run()](MOLSAICV3/usm/external/packmol.py:1), [msi2lmp.run()](MOLSAICV3/usm/external/msi2lmp.py:1), [pm2mdfcar.build()](MOLSAICV3/usm/ops/pm2mdfcar.py:1)
- Scaffold [MOLSAICV3/workspaces/alumina_AS2_hydration_v1/run.py](MOLSAICV3/workspaces/alumina_AS2_hydration_v1/run.py) and config
- Add integration test and acceptance checks
- Update [MOLSAICV3/docs/WORKFLOWS.md](MOLSAICV3/docs/WORKFLOWS.md) and [MOLSAICV3/docs/QUICKSTART.md](MOLSAICV3/docs/QUICKSTART.md)
- Plan removal of [MOLSAICV3/18-UnifiedStructs](MOLSAICV3/18-UnifiedStructs/docs/DESIGN.md) after parity achieved

References
- V3 DevDoc: [MOLSAICV3/DevDoc.md](MOLSAICV3/DevDoc.md:1)
- Original MolSAIC overview: [docs/OVERVIEW.md](docs/OVERVIEW.md:1)
- Pipeline spec: [docs/PIPELINE_SPEC.md](docs/PIPELINE_SPEC.md:1)
- Hydration pilot runbook: [docs/AluminaHydration_Rerun_2025-10.md](docs/AluminaHydration_Rerun_2025-10.md:1)
- Original AS2 pipeline YAML: [workflows/pipeline-alumina-AS2-hydration.yaml](workflows/pipeline-alumina-AS2-hydration.yaml:1)

Appendix A: Workspace contract
- Each workspace directory contains:
  - run.py with main() entry and step logs
  - config.json defaults and overrides
  - outputs/ for artifacts
- Required behavior:
  - Deterministic logic
  - Writes only under outputs/
  - Writes summary.json with inputs, params, counts, cell, and paths

Appendix B: Summary manifest keys (hydration)
- inputs: paths and versions for AS2, WAT, prm, frc, deck
- parameters: residue labels, target_c, normalize flags
- counts: atoms by species, waters placed (from PDB), final totals
- cell: a, b, c, angles
- outputs: hydrated pdb path, car/mdf paths, data file path
- timings: per-step durations and overall

Appendix C: Future parity targets
- AS5, AS10, AS12 hydration variants (after AS2 verified)
- MXN + water unified pipeline parity
- Substitution and grafting workflows once USM ops are centralized