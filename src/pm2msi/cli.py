#!/usr/bin/env python3
"""CLI for pm2msi (Packmol → MSI) bridge.

Usage:
    python -m pm2msi system.yaml
    python -m pm2msi system.yaml --verbose
    python -m pm2msi system.yaml --dry-run
"""

import sys
import json
import logging
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="pm2msi: Force field enrichment bridge (PDB + MDF → CAR/MDF)",
    )
    parser.add_argument("config", help="Path to system YAML configuration")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate config and templates without writing")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Change to config file's directory for relative paths
    config_path = Path(args.config).resolve()
    import os
    os.chdir(config_path.parent)

    from .config import load_config
    config = load_config(str(config_path))

    if args.dry_run:
        print(f"PDB: {config.pdb}")
        for tc in config.templates:
            print(f"Template: {tc.mdf} (resname={tc.pdb_resname}, grouping={tc.grouping})")
        if config.cell.is_explicit:
            print(f"Cell (explicit): {config.cell.a} x {config.cell.b} x {config.cell.c}")
        else:
            print(f"Cell (auto): padding={config.cell.padding} A")
        print(f"Output: {config.output}")
        print("Dry run complete — no files written.")
        return

    from .core import enrich
    result = enrich(config)

    print(f"\nCAR: {result['car_file']}")
    print(f"MDF: {result['mdf_file']}")
    print(f"\nSummary:")
    print(f"  Total atoms: {result['summary']['total_atoms']}")
    print(f"  Molecules: {result['summary']['molecules']}")
    print(f"  Atom types: {result['summary']['atom_types']}")

    if result["warnings"]:
        print(f"\nWarnings ({len(result['warnings'])}):")
        for w in result["warnings"]:
            print(f"  [!] {w}")
    else:
        print("\nNo warnings — all validations passed.")


if __name__ == "__main__":
    main()
