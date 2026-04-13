"""
pm2msi — Packmol to Materials Studio Interface bridge (PDB → CAR/MDF).

Bridges Packmol's coordinate-only PDB output to the Materials Studio CAR/MDF
format expected by msi2namd and msi2lmp. Matches atoms to force field
templates using index-based positional matching within each residue group,
which scales to any system size (including >999 atoms per residue).

Built on USM v2.0 for all file I/O.

Naming convention:
  - pm2msi: packmol → MSI (CAR/MDF)
  - msi2namd: MSI → NAMD (PSF/PDB)
  - msi2lmp: MSI → LAMMPS (data file)

Usage:
    from pm2msi import build
    result = build("system.yaml")

    # Or programmatically:
    from pm2msi import enrich, SystemConfig
    result = enrich(config)
"""

__version__ = "1.0.0"

from .core import build, enrich
from .config import load_config, SystemConfig
