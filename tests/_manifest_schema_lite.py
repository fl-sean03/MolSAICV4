"""Deterministic, dependency-free validation for the workspace `summary.json` manifest.

These integration tests intentionally keep third-party dependencies minimal.
If `jsonschema` is available we validate against the full JSON schema.
Otherwise we perform a small, stable subset of checks that still guards the
contracts we rely on in tests.
"""

from __future__ import annotations

from typing import Any


def validate_manifest_v1_schema_lite(summary: dict[str, Any]) -> None:
    """Validate a minimal subset of [`docs/manifest.v1.schema.json`](docs/manifest.v1.schema.json:1).

    This is *not* a full JSON Schema validator. It is a deterministic set of
    assertions that:
      - avoids adding `jsonschema` as a required dependency
      - catches accidental contract drift in the fields tests depend on
    """

    assert isinstance(summary, dict)

    # ---- Top-level required fields (per schema) ----
    for k in ["started_at", "finished_at", "inputs", "outputs", "counts", "cell"]:
        assert k in summary, f"manifest missing required key: {k}"

    assert isinstance(summary.get("started_at"), str) and summary["started_at"].strip()
    assert isinstance(summary.get("finished_at"), str) and summary["finished_at"].strip()

    # ---- inputs ----
    inputs = summary.get("inputs")
    assert isinstance(inputs, dict)
    for k in [
        "templates_dir",
        "parameters_prm",
        "frc_file",
        "packmol_deck",
        "residue_surface",
        "residue_water",
        "target_c",
    ]:
        assert k in inputs, f"manifest.inputs missing required key: {k}"

    for k in ["templates_dir", "parameters_prm", "frc_file", "packmol_deck"]:
        assert isinstance(inputs.get(k), str) and inputs[k].strip(), f"manifest.inputs.{k} must be a non-empty string"

    for k in ["residue_surface", "residue_water"]:
        v = inputs.get(k)
        assert isinstance(v, str) and 1 <= len(v.strip()) <= 4, f"manifest.inputs.{k} must be 1-4 char string"

    tc = inputs.get("target_c")
    assert isinstance(tc, (int, float)), "manifest.inputs.target_c must be a number"

    # ---- outputs ----
    outputs = summary.get("outputs")
    assert isinstance(outputs, dict)
    for k in ["lmp_data_file", "car_file", "mdf_file", "packed_structure"]:
        assert k in outputs, f"manifest.outputs missing required key: {k}"
        assert isinstance(outputs.get(k), str) and outputs[k].strip(), f"manifest.outputs.{k} must be a non-empty string"

    # ---- counts ----
    counts = summary.get("counts")
    assert isinstance(counts, dict)

    # ---- cell ----
    cell = summary.get("cell")
    assert isinstance(cell, dict)
    assert "c" in cell, "manifest.cell.c is required"
    assert isinstance(cell.get("c"), (int, float)), "manifest.cell.c must be a number"

