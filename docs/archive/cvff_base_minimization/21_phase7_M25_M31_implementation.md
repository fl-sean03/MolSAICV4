# Phase 7 Ultimate Minimization (M25-M31) - Implementation Plan

**Created**: 2025-12-20
**Status**: Ready for Implementation

## 1) Current State Analysis

### 1.1 What Already Exists

| Component | Location | Status |
|-----------|----------|--------|
| CvffPruneOptions Phase 7 fields | [`frc_from_scratch.py:1631-1640`](src/upm/src/upm/build/frc_from_scratch.py:1631) | ✅ Defined |
| M25-M31 presets | [`frc_from_scratch.py:2348-2510`](src/upm/src/upm/build/frc_from_scratch.py:2348) | ✅ Defined |
| Preamble filtering logic | [`frc_from_scratch.py:2008-2011`](src/upm/src/upm/build/frc_from_scratch.py:2008) | ❌ **NOT IMPLEMENTED** |
| Section line filtering logic | [`frc_from_scratch.py:2033`](src/upm/src/upm/build/frc_from_scratch.py:2033) | ❌ **NOT IMPLEMENTED** |

### 1.2 Current cvff_M24.frc Structure (205 lines)

```
Lines 1:      !BIOSYM forcefield 1
Lines 2:      (blank)
Lines 3-18:   16 #version cvff.frc lines  → Phase 7 target
Lines 19:     (blank)
Lines 20-23:  4 Insight comment lines     → Phase 7 target
Lines 24-26:  (blanks)
Lines 27-42:  #define cvff_nocross_nomorse block (16 lines)
Lines 43-65:  #define cvff block (23 lines)
Lines 66-83:  #define cvff_nocross block (18 lines)
Lines 84-105: #define cvff_nomorse block (22 lines)
Lines 106+:   Section headers with CALF20 entries
```

### 1.3 Phase 7 Options in CvffPruneOptions

```python
# Phase 7: Preamble cleanup options (M25-M28)
keep_version_history: bool = True       # M25/M26
keep_latest_version_only: bool = False  # M25
keep_insight_comments: bool = True      # M27
define_blocks: Literal['all', 'cvff_only'] = 'all'  # M28

# Phase 7: Section cleanup options (M29-M31)
keep_description_comments: bool = True  # M29: Keep > lines
keep_column_headers: bool = True        # M30: Keep ! lines
minimize_blank_lines: bool = False      # M31: Collapse blanks
```

## 2) Implementation Requirements

### 2.1 Preamble Filtering (after line 2010)

The current code at lines 2008-2011:
```python
# Always include preamble
if "preamble" in sections:
    _, _, preamble_lines = sections["preamble"]
    output_lines.extend(preamble_lines)  # <-- No filtering!
```

**Required change**: Filter preamble_lines before extending:

```python
# Always include preamble
if "preamble" in sections:
    _, _, preamble_lines = sections["preamble"]
    filtered_preamble = _filter_preamble_lines(preamble_lines, prune)
    output_lines.extend(filtered_preamble)
```

### 2.2 Helper Function: _filter_preamble_lines()

Add this helper function before build_frc_cvff_with_pruned_base():

```python
def _filter_preamble_lines(
    preamble_lines: list[str],
    prune: CvffPruneOptions,
) -> list[str]:
    """Filter preamble lines based on Phase 7 prune options.
    
    Args:
        preamble_lines: Raw preamble lines from embedded base
        prune: Pruning options with Phase 7 settings
        
    Returns:
        Filtered list of preamble lines
    """
    result: list[str] = []
    
    # Track state for #define block filtering
    in_define_block = False
    current_define_macro = ""
    skip_current_block = False
    
    for line in preamble_lines:
        stripped = line.strip()
        
        # Handle #version lines
        if stripped.startswith("#version"):
            if not prune.keep_version_history:
                continue  # Skip all version lines (M26)
            if prune.keep_latest_version_only:
                # Keep only if it's the latest version (4.0)
                if "4.0" not in stripped:
                    continue
            result.append(line)
            continue
        
        # Handle Insight comments (lines 20-23 style)
        # Pattern: "! Currently Insight does not handle..."
        if stripped.startswith("!") and "Insight" in stripped:
            if not prune.keep_insight_comments:
                continue
            result.append(line)
            continue
        
        # Handle continuation of Insight comment block
        if stripped.startswith("!") and any(kw in stripped for kw in ["occurence", "comment", "first", "line"]):
            if not prune.keep_insight_comments:
                continue
            result.append(line)
            continue
        
        # Handle #define blocks
        if stripped.startswith("#define"):
            in_define_block = True
            # Extract macro name (e.g., "cvff_nocross_nomorse", "cvff", etc.)
            parts = stripped.split()
            current_define_macro = parts[1] if len(parts) > 1 else ""
            
            if prune.define_blocks == 'cvff_only':
                # Only keep the "#define cvff" block (not variants)
                skip_current_block = (current_define_macro != "cvff")
            else:
                skip_current_block = False
            
            if not skip_current_block:
                result.append(line)
            continue
        
        # Handle lines inside #define blocks
        if in_define_block:
            # Check if we're starting a new section (not in define anymore)
            if stripped.startswith("#") and not stripped.startswith("#define"):
                in_define_block = False
                skip_current_block = False
                result.append(line)
                continue
            
            # Skip if we're in a filtered block
            if skip_current_block:
                continue
            
            result.append(line)
            continue
        
        # Default: keep the line
        result.append(line)
    
    # Apply minimize_blank_lines if enabled
    if prune.minimize_blank_lines:
        result = _collapse_blank_lines(result)
    
    return result
```

### 2.3 Section Line Filtering (after line 2033)

Current code at line 2033:
```python
output_lines.extend(section_lines)
```

**Required change**: Filter section lines before extending:

```python
# Apply Phase 7 section line filtering
filtered_section = _filter_section_lines(section_lines, prune)
output_lines.extend(filtered_section)
```

### 2.4 Helper Function: _filter_section_lines()

```python
def _filter_section_lines(
    section_lines: list[str],
    prune: CvffPruneOptions,
) -> list[str]:
    """Filter section lines based on Phase 7 prune options.
    
    Args:
        section_lines: Lines including section header
        prune: Pruning options with Phase 7 settings
        
    Returns:
        Filtered list of section lines
    """
    result: list[str] = []
    
    for i, line in enumerate(section_lines):
        stripped = line.strip()
        
        # Always keep section header (first line starting with #)
        if i == 0 and stripped.startswith("#"):
            result.append(line)
            continue
        
        # Filter description comments (> lines) - M29
        if stripped.startswith(">"):
            if not prune.keep_description_comments:
                continue
            result.append(line)
            continue
        
        # Filter column headers (! lines) - M30
        if stripped.startswith("!"):
            if not prune.keep_column_headers:
                continue
            result.append(line)
            continue
        
        # Keep all other lines (data entries, @ directives, etc.)
        result.append(line)
    
    # Apply minimize_blank_lines if enabled
    if prune.minimize_blank_lines:
        result = _collapse_blank_lines(result)
    
    return result
```

### 2.5 Helper Function: _collapse_blank_lines()

```python
def _collapse_blank_lines(lines: list[str]) -> list[str]:
    """Collapse consecutive blank lines to a single blank line.
    
    Args:
        lines: Input lines
        
    Returns:
        Lines with consecutive blanks collapsed
    """
    result: list[str] = []
    prev_blank = False
    
    for line in lines:
        is_blank = not line.strip()
        
        if is_blank:
            if prev_blank:
                continue  # Skip consecutive blank
            prev_blank = True
        else:
            prev_blank = False
        
        result.append(line)
    
    return result
```

## 3) M25-M31 Experiment Definitions

Based on search results (lines 2348-2510), the presets are already defined:

| Preset | Configuration | Expected Impact |
|--------|---------------|-----------------|
| M25 | keep_latest_version_only=True | -15 lines (16→1 version) |
| M26 | keep_version_history=False | -16 lines (all versions) |
| M27 | M26 + keep_insight_comments=False | -4 more lines |
| M28 | M27 + define_blocks='cvff_only' | ~-63 lines (3 define blocks) |
| M29 | M28 + keep_description_comments=False | ~-10 lines |
| M30 | M29 + keep_column_headers=False | ~-20 lines |
| M31 | M30 + minimize_blank_lines=True | ~-10 lines |

## 4) Test Script

Create test script at `workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/run_phase7_experiments.py`:

```python
#!/usr/bin/env python3
"""Phase 7 Ultimate Minimization Experiments (M25-M31).

Run each M25-M31 preset and validate with msi2lmp.exe.
"""

import json
import subprocess
import hashlib
from pathlib import Path

# Configuration
WORKSPACE_ROOT = Path(__file__).parent
MSI2LMP_EXE = Path("/home/sf2/LabWork/software/msi2lmp.exe")
PRESETS = ["M25", "M26", "M27", "M28", "M29", "M30", "M31"]

def run_experiment(preset: str) -> dict:
    """Run a single M-series experiment."""
    output_dir = WORKSPACE_ROOT / f"outputs_{preset}"
    output_dir.mkdir(exist_ok=True)
    
    # Import and run builder
    from upm.build.frc_from_scratch import (
        build_frc_cvff_with_pruned_base,
        CVFF_MINIMIZATION_PRESETS,
    )
    
    # Load termset and parameterset
    termset = json.loads((WORKSPACE_ROOT / "inputs/termset.json").read_text())
    parameterset = json.loads((WORKSPACE_ROOT / "inputs/parameterset.json").read_text())
    
    # Build .frc
    frc_path = output_dir / f"cvff_{preset}.frc"
    build_frc_cvff_with_pruned_base(
        termset=termset,
        parameterset=parameterset,
        out_path=frc_path,
        prune=CVFF_MINIMIZATION_PRESETS[preset],
    )
    
    # Count lines
    frc_lines = len(frc_path.read_text().splitlines())
    
    # Run msi2lmp.exe
    msi2lmp_dir = output_dir / "msi2lmp_run"
    msi2lmp_dir.mkdir(exist_ok=True)
    
    # Copy inputs
    for f in ["CALF20.car", "CALF20.mdf"]:
        src = WORKSPACE_ROOT / "inputs" / f
        dst = msi2lmp_dir / f
        dst.write_bytes(src.read_bytes())
    
    # Copy .frc
    (msi2lmp_dir / f"cvff_{preset}.frc").write_text(frc_path.read_text())
    
    # Run msi2lmp
    result = subprocess.run(
        [str(MSI2LMP_EXE), "CALF20", "-class", "I", "-frc", f"cvff_{preset}.frc"],
        cwd=msi2lmp_dir,
        capture_output=True,
        timeout=30,
    )
    
    # Check output
    data_path = msi2lmp_dir / "CALF20.data"
    data_exists = data_path.exists()
    data_sha256 = ""
    data_size = 0
    
    if data_exists:
        data_bytes = data_path.read_bytes()
        data_size = len(data_bytes)
        data_sha256 = hashlib.sha256(data_bytes).hexdigest()
    
    return {
        "preset": preset,
        "frc_lines": frc_lines,
        "exit_code": result.returncode,
        "data_exists": data_exists,
        "data_size": data_size,
        "data_sha256": data_sha256,
        "status": "PASS" if result.returncode == 0 and data_exists else "FAIL",
    }


def main():
    results = []
    
    for preset in PRESETS:
        print(f"Running {preset}...")
        try:
            result = run_experiment(preset)
            results.append(result)
            print(f"  {preset}: {result['frc_lines']} lines, {result['status']}")
        except Exception as e:
            print(f"  {preset}: ERROR - {e}")
            results.append({
                "preset": preset,
                "status": "ERROR",
                "error": str(e),
            })
    
    # Save results
    output_path = WORKSPACE_ROOT / "phase7_results.json"
    output_path.write_text(json.dumps(results, indent=2))
    
    # Print summary table
    print("\n" + "=" * 70)
    print("Phase 7 Results Summary")
    print("=" * 70)
    print(f"{'Preset':<8} {'Lines':<8} {'Exit':<6} {'Data':<12} {'Status':<8}")
    print("-" * 70)
    for r in results:
        if r.get("status") == "ERROR":
            print(f"{r['preset']:<8} {'N/A':<8} {'N/A':<6} {'N/A':<12} {'ERROR':<8}")
        else:
            data_info = f"{r.get('data_size', 0)} bytes" if r.get('data_exists') else "None"
            print(f"{r['preset']:<8} {r.get('frc_lines', 'N/A'):<8} {r.get('exit_code', 'N/A'):<6} {data_info:<12} {r['status']:<8}")
    
    print("=" * 70)


if __name__ == "__main__":
    main()
```

## 5) Expected Results

Based on M24 at 205 lines and the filtering targets:

| Preset | Expected Lines | Reduction from M24 |
|--------|----------------|-------------------|
| M24 (baseline) | 205 | baseline |
| M25 | ~190 | -15 (version→1) |
| M26 | ~189 | -16 (no versions) |
| M27 | ~185 | -20 (no Insight) |
| M28 | ~125 | -80 (single define) |
| M29 | ~115 | -90 (no > comments) |
| M30 | ~95 | -110 (no ! headers) |
| M31 | ~85 | -120 (minimize blanks) |

**Theoretical minimum**: ~85-90 lines (if all cleanups work)

## 6) Implementation Steps for Code Mode

1. Add helper functions after line 1686 (after SECTION_LIMIT_MAP):
   - `_filter_preamble_lines()`
   - `_filter_section_lines()`
   - `_collapse_blank_lines()`

2. Update preamble handling at line 2010:
   - Replace direct extend with filtered extend

3. Update section handling at line 2033:
   - Replace direct extend with filtered extend

4. Create test script at workspace

5. Run experiments and collect results

## 7) Success Criteria

1. **All M25-M31 presets produce valid CALF20.data** (exit code 0)
2. **CALF20.data SHA256 matches** previous runs: `cbf9981e990d02b4e8b7cf96a9a42a9a24da3a8238ebe601f3ca4192e6d1af45`
3. **M31 achieves ~85-95 lines** (further reduction from M24's 205)
4. **Thrust log updated** with complete results table

## 8) Files to Modify

1. [`src/upm/src/upm/build/frc_from_scratch.py`](src/upm/src/upm/build/frc_from_scratch.py)
   - Add 3 helper functions
   - Modify preamble handling (line 2010)
   - Modify section handling (line 2033)

2. `workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/run_phase7_experiments.py`
   - Create test script

3. [`docs/DevGuides/thrust_log_cvff_base_minimization.md`](docs/DevGuides/thrust_log_cvff_base_minimization.md)
   - Add Phase 7 results section

---

**Ready for implementation in Code mode.**
