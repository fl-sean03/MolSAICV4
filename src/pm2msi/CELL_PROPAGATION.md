# Cell Dimension Propagation in the Build Pipeline

## The Problem

Cell (simulation box) dimensions must be consistent across 4 stages:

```
Packmol input  →  Packmol PDB  →  CAR/MDF  →  PSF/PDB  →  NAMD config
(inside box)     (CRYST1?)       (PBC line)   (no cell)   (cellBasisVector)
```

Currently each stage gets its cell info from a different source:
- **Packmol**: `inside box 2 2 2 118 118 118` (constraint, not the box)
- **Packmol PDB**: No CRYST1 (or unreliable bounding-box estimate via `add_box_sides`)
- **rn_v2 CAR/MDF**: From YAML config `cell: {a: 120, b: 120, c: 120}`
- **NAMD**: From simulation config `cellBasisVector1 120 0 0`

The YAML config is the single source of truth, but it's disconnected from the Packmol input. If someone changes the Packmol box without updating the YAML, the cell will be wrong.

## Why Packmol Can't Provide Cell Dimensions

1. `add_box_sides N`: Writes CRYST1 as `bounding_box_of_atoms + N*tolerance`. This is an approximation, not the actual box.
2. `pbc a b c alpha beta gamma`: Used for Packmol's internal minimum-image distance calculations during packing. Does NOT write these values to CRYST1.
3. `inside box x1 y1 z1 x2 y2 z2`: Defines the constraint region, which is typically slightly smaller than the simulation box (atoms need buffer from edges).

## Recommended Solution: Single YAML Config Drives Everything

The YAML config should be the single source of truth for both Packmol AND rn_v2:

```yaml
# system.yaml — single source of truth
pdb: PT_NEC4H.pdb

cell:
  a: 120.0
  b: 120.0
  c: 120.0

templates:
  - mdf: PtCubic.mdf
    pdb_resname: PT
    grouping: single
    fixed_center: true           # auto-center at (a/2, b/2, c/2)
  - mdf: NEC_4H.mdf
    pdb_resname: nec
    grouping: separate
    count: 999                   # number of molecules

output: NEC+Pt

packmol:
  tolerance: 2.5
  seed: 12345
  edge_buffer: 2.0              # constraint box is [buffer, a-buffer]
```

From this single config, a build script can:
1. **Generate pm.inp**: Box = `cell.a`, constraint = `[edge_buffer, a - edge_buffer]`, center = `a/2`
2. **Run Packmol**: produces PDB
3. **Run rn_v2**: reads same `cell` block for CAR/MDF PBC
4. **Generate NAMD config**: reads same `cell` block for cellBasisVector

No separate maintenance of box dimensions across files.

## Current State (What We Have)

For now, the YAML `cell` block drives rn_v2 correctly. The Packmol input is maintained separately but must be consistent. This works but requires manual coordination.

## Future Enhancement

Add a `generate_packmol_input()` function to rn_v2 that reads the YAML and writes a consistent pm.inp. Then the full pipeline becomes:

```bash
python -m rn_v2 generate-packmol system.yaml    # writes pm.inp from YAML
packmol < pm.inp                                  # runs Packmol
python -m rn_v2 enrich system.yaml               # enriches with FF data
msi2namd -file NEC+Pt ...                         # converts to NAMD
```

One config file, one source of truth, fully automated.
