# pm2msi — Packmol → Materials Studio Interface bridge

Force field enrichment bridge that converts Packmol's coordinate-only PDB
output into the Materials Studio CAR/MDF format expected by `msi2namd` and
`msi2lmp`.

## Naming Convention

Aligns with the existing MSI tool ecosystem:
- **pm2msi**: Packmol → MSI (CAR/MDF)
- **msi2namd**: MSI → NAMD (PSF/PDB)
- **msi2lmp**: MSI → LAMMPS (data file)

## Why?

Packmol outputs PDB files with coordinates only — no atom types, no charges,
no bonds. msi2namd/msi2lmp need full force field topology in CAR/MDF format.
pm2msi bridges this gap by:

1. Reading MDF templates (force field data: atom types, charges, bonds)
2. Parsing the Packmol PDB
3. Matching atoms to templates by **positional index within each residue group**
4. Writing CAR/MDF with coordinates + full FF topology + PBC

## Key Features

- **Index-based matching**: handles any atom count (no >999 atom limit)
- **Generic**: any residue names via YAML config (not hardcoded to AS2/WAT)
- **Robust PDB parser**: handles hex serials for systems >99,999 atoms
- **Auto-cell**: derives box dimensions from PDB bounding box if not specified
- **Built on USM v2.0**: uses USM for all file I/O
- **Pre-flight validation**: catches missing templates, atom count mismatches
- **Config-driven**: YAML-based, no Python edits per system

## vs pm2mdfcar

`pm2mdfcar` is the legacy slab+water-specific bridge (hardcoded for AS2/WAT
templates with periodic crystal slabs). pm2msi is the generic replacement:
- Less code (~600 LOC vs 2,117 LOC)
- More flexible (any residue names, any system geometry)
- Better validation
- Built directly on USM

## Usage

### YAML config

```yaml
pdb: PT_NEC4H.pdb
templates:
  - mdf: PtCubic.mdf
    pdb_resname: PT
    grouping: single        # all atoms → one molecule block (NP)
  - mdf: NEC_4H.mdf
    pdb_resname: nec
    grouping: separate      # each molecule → separate block
cell:
  a: 120.0
  b: 120.0
  c: 120.0
output: NEC+Pt
```

Or omit the `cell` block to auto-derive from PDB bounding box.

### CLI

```bash
python -m pm2msi system.yaml
python -m pm2msi system.yaml --verbose
python -m pm2msi system.yaml --dry-run
```

### Python API

```python
from pm2msi import build, enrich, load_config

# From YAML
result = build("system.yaml")

# Or programmatically
config = load_config("system.yaml")
result = enrich(config)

print(result["car_file"])  # Path to output CAR
print(result["mdf_file"])  # Path to output MDF
print(result["summary"])   # Atom counts, types, cell, etc.
print(result["warnings"])  # Any non-fatal issues
```

## Cell Modes

**Explicit**: specify `a, b, c` in YAML.
```yaml
cell:
  a: 120.0
  b: 120.0
  c: 120.0
```

**Auto**: omit `cell` block (or specify only `padding`). Cell is derived from
PDB bounding box + 2 × padding (default 5 Å). Coordinates are shifted so the
minimum sits at `padding` from the origin.
```yaml
cell:
  padding: 10.0
```

NPT equilibration will compress oversized boxes to the target density.

## Pre-Flight Validation

Before doing any heavy work, pm2msi checks:

1. **Missing templates**: every PDB residue has a matching MDF template
2. **Unused templates**: warns if a template provided but no PDB residue matches
3. **Atom count divisibility**: PDB atom counts must be exact multiples of template sizes

## Testing

```bash
# Smoke tests (no external data needed)
pytest src/pm2msi/tests/

# Full pipeline tests with real systems live in consumer projects
# (e.g., ~/LabWork/Workspace/31-Hydrogenation/system-building/rn_v2/tests/)
```

## See Also

- `usm` — USM v2.0, the structure I/O layer that pm2msi is built on
- `pm2mdfcar` — Legacy slab+water bridge (kept for backward compat)
- `external/msi2namd.py` — MSI → NAMD wrapper
- `external/msi2lmp.py` — MSI → LAMMPS wrapper
