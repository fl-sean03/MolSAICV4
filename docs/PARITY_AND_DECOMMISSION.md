# MolSAIC V3 Parity and Decommission Plan

Executive summary
- Hydration pipelines for AS2, AS5, AS10, AS12 in this repo achieve parity with the original MolSAIC V2 outputs (.data equivalence in headers, masses, coeffs, atom types/charges/coordinates XY exact, Z uniform shift, and all topologies).
- V3 workspaces and wrappers now produce deterministic, validated artifacts with a standardized run manifest (manifest v1).

Primary parity artifacts (in-repo)
- V3 LAMMPS .data
  - AS2: [AS2_hydration.data](workspaces/alumina_AS2_hydration_v1/outputs/simulation/AS2_hydration.data:1)
  - AS5: [AS5_hydration.data](workspaces/alumina_AS5_hydration_v1/outputs/simulation/AS5_hydration.data:1)
  - AS10: [AS10_hydration.data](workspaces/alumina_AS10_hydration_v1/outputs/simulation/AS10_hydration.data:1)
  - AS12: [AS12_hydration.data](workspaces/alumina_AS12_hydration_v1/outputs/simulation/AS12_hydration.data:1)
- JSON comparison summaries
  - AS2: [compare_vs_legacy.json](workspaces/alumina_AS2_hydration_v1/outputs/simulation/compare_vs_legacy.json:1)
  - AS5: [compare_vs_legacy_AS5.json](workspaces/alumina_AS5_hydration_v1/outputs/simulation/compare_vs_legacy_AS5.json:1)
  - AS10: [compare_vs_legacy_AS10.json](workspaces/alumina_AS10_hydration_v1/outputs/simulation/compare_vs_legacy_AS10.json:1)
  - AS12: [compare_vs_legacy_AS12.json](workspaces/alumina_AS12_hydration_v1/outputs/simulation/compare_vs_legacy_AS12.json:1)

What changed to reach parity
- Header normalization and uniform Z shift (msi2lmp wrapper)
  - Implemented header-only XY normalization (xlo/xhi -> [0,a], ylo/yhi -> [0,b]) and Z normalization with uniform per-atom Z shift so min(z)=0, then zlo/zhi set to 0 and either normalize_z_to or CAR PBC c.
  - Implementation: [msi2lmp.run()](molsaicv3/usm/external/msi2lmp.py:68) and normalization block near [msi2lmp.run() post-processing](molsaicv3/usm/external/msi2lmp.py:136).
  - AS2 parity nuance: pass normalize_z_to=None so zlo/zhi uses the CAR PBC c (legacy behavior): [run.py](workspaces/alumina_AS2_hydration_v1/run.py:209).
- Target cell height parity
  - target_c set to 81.397 across all hydration configs:
    - AS2: [config.json](workspaces/alumina_AS2_hydration_v1/config.json:9)
    - AS5: [config.json](workspaces/alumina_AS5_hydration_v1/config.json:9)
    - AS10: [config.json](workspaces/alumina_AS10_hydration_v1/config.json:9)
    - AS12: [config.json](workspaces/alumina_AS12_hydration_v1/config.json:9)
- Packmol deck parity fixes (positions/boxes)
  - AS5 deck: [packmol_AS5.inp](assets/AluminaSurfaces/packmol/packmol_AS5.inp:1)
  - AS10 deck: [packmol_AS10.inp](assets/AluminaSurfaces/packmol/packmol_AS10.inp:1)
- Packmol wrapper determinism and portability
  - Replaced shell redirection with seekable stdin FH; added seed injection ("seed N"), warnings aggregation and optional escalation policy.
  - Implementation: [packmol.run()](molsaicv3/usm/external/packmol.py:46)
- Composition kept MSI-compatible dialect via vendored builder
  - pm2mdfcar builds CAR/MDF with numeric PBC and c := target_c; counts and cell echoed to summary.
  - Implementation: [pm2mdfcar.build()](molsaicv3/usm/ops/pm2mdfcar.py:392)

Manifest v1 standardization
- Runners write a standardized manifest with meta, inputs, params, tools, tool_versions, tool_profile, timings, outputs, counts, cell, warnings.
- Schema: [manifest.v1.schema.json](docs/manifest.v1.schema.json:1)
- Example runner summaries
  - AS10 runner summary block: [run.py](workspaces/alumina_AS10_hydration_v1/run.py:243)
  - AS12 runner summary block: [run.py](workspaces/alumina_AS12_hydration_v1/run.py:243)
  - AS5 runner summary block: [run.py](workspaces/alumina_AS5_hydration_v1/run.py:243)
  - AS2 runner summary block (AS2 nuance for z normalization): [run.py](workspaces/alumina_AS2_hydration_v1/run.py:224)

Acceptance criteria (for parity-ready tag)
1) Artifact presence and non-emptiness
- For each workspace, the following exist and are non-empty:
  - PDB/PSF for surface and WAT (outputs/*.pdb, outputs/*.psf)
  - Hydrated PDB (Packmol) (outputs/hydrated_*.pdb)
  - CAR/MDF (outputs/converted/*_hydrated.car/.mdf)
  - LAMMPS .data (outputs/simulation/*_hydration.data)
  - Manifest (outputs/summary.json)
2) Manifest validation
- Each outputs/summary.json validates against [manifest.v1.schema.json](docs/manifest.v1.schema.json:1).
- CI executes this via an integration test: [test_existing_summaries_validate_manifest](tests/integration/test_hydration_workspaces.py:115)
3) Cell and counts checks
- cell.c equals config target_c (81.397).
- counts.atoms = counts.surface_atoms + 3*counts.waters when present.
- Verified in: [test_hydration_workspaces invariants](tests/integration/test_hydration_workspaces.py:90)
4) Parity comparisons retained for reference
- JSON comparison summaries (listed above) remain present (read-only reference).

Reproducibility and determinism
- Packmol determinism via seed; seed recorded under summary.params.packmol_seed.
- Warnings policy for deck validation is configurable; can be escalated in CI to fail on missing structures.
- Determinism test harness exists to compare key structured fields over repeated runs:
  - [test_determinism_when_enabled](tests/integration/test_hydration_workspaces.py:176)
  - Intended to run with RUN_DETERMINISM=1 in provisioned environments.

CI workflow (proposed)
- Two jobs:
  - Unit (always)
    - Setup Python 3.11+
    - pip install pytest jsonschema
    - Run: pytest -q -m "unit"
  - Integration (partial, no external tools)
    - pip install pytest jsonschema
    - Run manifest checks only: pytest -q -m "integration" -k "existing_summaries_validate_manifest"
- Optional extended jobs (when toolchain available):
  - RUN_INTEGRATION=1: run end-to-end workspaces
  - RUN_DETERMINISM=1: run determinism checks
- The workflow file will live at [.github/workflows/ci.yml](.github/workflows/ci.yml:1)

Decommission plan for legacy structures
- Preconditions (gated by CI):
  - All unit tests green
  - Integration manifest validation green
  - Optional extended runs (when provisioned) green
- Steps:
  1) Create annotated tag: v3-parity-ready
  2) Remove legacy directory: [18-UnifiedStructs/](18-UnifiedStructs/README.md:1) (and any remaining references)
  3) Update docs to remove references to legacy paths; ensure Quickstart/Workflows/Adapter Contract remain accurate:
     - Quickstart anchors: [docs/QUICKSTART.md](docs/QUICKSTART.md:1)
     - Workflows anchors: [docs/WORKFLOWS.md](docs/WORKFLOWS.md:1)
     - Adapter contract: [docs/ADAPTER_CONTRACT.md](docs/ADAPTER_CONTRACT.md:1)
  4) Run CI (unit + integration manifest) on PR to confirm green on main
  5) After merge, cut tag v3.0.0

Appendix: key implementation anchors
- Adapter contract and helpers:
  - [ExternalToolResult()](molsaicv3/usm/external/adapter.py:48)
  - [augment_env_with_exe_dir()](molsaicv3/usm/external/adapter.py:33)
  - [get_tool_version()](molsaicv3/usm/external/adapter.py:112)
- Wrappers:
  - [packmol.run()](molsaicv3/usm/external/packmol.py:46)
  - [msi2namd.run()](molsaicv3/usm/external/msi2namd.py:96)
  - [msi2lmp.run()](molsaicv3/usm/external/msi2lmp.py:68)
- Composition:
  - [pm2mdfcar.build()](molsaicv3/usm/ops/pm2mdfcar.py:392)
- Runners:
  - AS2: [run.py](workspaces/alumina_AS2_hydration_v1/run.py:1)
  - AS5: [run.py](workspaces/alumina_AS5_hydration_v1/run.py:1)
  - AS10: [run.py](workspaces/alumina_AS10_hydration_v1/run.py:1)
  - AS12: [run.py](workspaces/alumina_AS12_hydration_v1/run.py:1)