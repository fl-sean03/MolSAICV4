# External Tool Adapter Contract (v1)

Purpose
- Define a unified, deterministic result envelope for all external tool wrappers in MolSAIC V4.
- Centralize PATH augmentation and tool version capture helpers.
- Ensure workspace manifests (summary.json) are stable and machine-consumable.

References
- Contract and helpers: [adapter.py](src/external/adapter.py:1)
  - Dataclass: [ExternalToolResult()](src/external/adapter.py:50)
  - PATH helper: [augment_env_with_exe_dir()](src/external/adapter.py:34)
  - Version helper: [get_tool_version()](src/external/adapter.py:113)
- Wrappers conforming to this contract:
  - [packmol.run()](src/external/packmol.py:46)
  - [msi2namd.run()](src/external/msi2namd.py:96)
  - [msi2lmp.run()](src/external/msi2lmp.py:68)

Envelope (ExternalToolResult.to_dict)
- tool: program name, e.g., "packmol"
- argv: full argv list, including the executable as argv[0]
- cwd: absolute working directory used for the process
- duration_s: wall-clock seconds (float)
- stdout: captured stdout text
- stderr: captured stderr text
- outputs: mapping of logical output names to absolute paths
- tool_version: best-effort version string (or absent)
- warnings: list of warning strings (empty list when none)
- seed: RNG seed used (when applicable, omitted otherwise)

Conventions
- PATH safety: wrappers prepend the executable’s directory to PATH via [augment_env_with_exe_dir()](src/external/adapter.py:34) to aid dynamic linker resolution.
- Timeouts: all wrappers take a timeout_s and enforce it with subprocess.run(..., timeout=...).
- Deterministic CWD: wrappers run in a deterministic working directory (e.g., parent of output_prefix or staged inputs).
- Output validation: wrappers check expected outputs are created and non-empty, raising on failures.

Version capture
- Wrappers call [get_tool_version()](src/external/adapter.py:113) and record tool_version in the result envelope.
- Strategy tries common flags (--version, -version, -v, -h) and banner parsing. Never raises; returns "unknown" when not found.

Back-compat aliases
- packmol.run() returns outputs["packed_structure"] and sets a top-level "packed_structure" alias.
- msi2lmp.run() returns outputs["lmp_data_file"] and sets a top-level "lmp_data_file" alias.
- These aliases smooth migration from earlier code while consumers pivot to outputs[...] consistently.

Error handling (common)
- FileNotFoundError for missing executables or required inputs.
- ValueError for invalid parameters (e.g., residue length > 4).
- RuntimeError when the process exits non-zero or expected outputs are not produced.

Wrappers overview
- [packmol.run()](src/external/packmol.py:46)
  - Feeds the deck via a seekable stdin file handle (no shell redirection).
  - Supports seed injection ("seed N") for determinism.
  - Aggregates deck validation warnings (e.g., missing structure files) and optionally escalates to error.
  - Returns:
    - outputs.packed_structure: absolute path to hydrated PDB
    - warnings: list of deck validation warnings
    - seed: integer seed when provided
- [msi2namd.run()](src/external/msi2namd.py:96)
  - Stages CAR/MDF into the working dir (parent of output_prefix).
  - Calls external msi2namd with classII params; validates .pdb/.psf outputs.
  - Returns:
    - outputs.pdb_file, outputs.psf_file
- [msi2lmp.run()](src/external/msi2lmp.py:68)
  - Runs in the base CAR/MDF directory; produces .data and moves to output_prefix.data when provided.
  - Optional header normalization (parity with legacy):
    - Normalize xlo/xhi and ylo/yhi to [0, a]/[0, b] when requested.
    - Normalize zlo/zhi to [0, target_c] (or CAR PBC c) and uniformly shift atoms so min(z)=0.
  - Returns:
    - outputs.lmp_data_file

Result example (truncated)
{
  "tool": "packmol",
  "argv": ["/abs/path/packmol"],
  "cwd": "/abs/work/dir",
  "duration_s": 1.234,
  "stdout": "...",
  "stderr": "...",
  "outputs": {
    "packed_structure": "/abs/work/dir/hydrated_AS2.pdb"
  },
  "tool_version": "20.15.3",
  "warnings": [],
  "seed": 12345
}

Adding a new adapter
- Implement a thin wrapper module with run(...)->dict, returning [ExternalToolResult()](src/external/adapter.py:50).to_dict().
- Use [augment_env_with_exe_dir()](src/external/adapter.py:34) for env, capture stdout/stderr, validate outputs.
- Include tool_version via [get_tool_version()](src/external/adapter.py:113).
- Keep parameters minimal and typed; raise standard exceptions defined above.
- Write unit tests that:
  - Monkeypatch subprocess.run to emit minimal valid outputs.
  - Assert the schema keys and that outputs exist and are non-empty.
  - Example patterns: [tests/unit/test_wrappers_schema.py](tests/unit/test_wrappers_schema.py:1)

Manifest alignment
- Workspace runners collect:
  - inputs, params, tools, tool_versions, tool_profile, timings, outputs, counts, cell, warnings
- Schema lives at: [manifest.v1.schema.json](docs/manifest.v1.schema.json:1)
- Runners can optionally validate manifests using jsonschema.

Notes
- For determinism in stochastic tools, surface and record seeds (e.g., Packmol seed) and add to summary params.
- Avoid shell=True; prefer explicit argv and stdin file handles for portability and safety.