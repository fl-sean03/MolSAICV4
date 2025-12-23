# Using `msi2lmp.exe` Standalone

This document explains how to use the `msi2lmp.exe` executable independently to convert Materials Studio `.car` and `.mdf` files into LAMMPS-readable `.data` files.

## 1. Purpose of `msi2lmp.exe`

`msi2lmp.exe` is a utility that converts molecular structure and forcefield information from Materials Studio (Cerius2) `.car` and `.mdf` files into a `.data` file format compatible with LAMMPS (Large-scale Atomic/Molecular Massively Parallel Simulator). This conversion is essential for preparing atomic configurations and their associated forcefield parameters for molecular dynamics simulations in LAMMPS.

## 2. Location of `msi2lmp.exe`

The `msi2lmp.exe` executable is located in the `0-ExternalScripts/` directory.

`./0-ExternalScripts/msi2lmp.exe`

## 3. Usage

To use `msi2lmp.exe` standalone, you typically execute it from the directory where your `.car` and `.mdf` input files are located. You need to provide the base name of your structure files (without the `.car` or `.mdf` extension) and specify the path to the forcefield file (`.frc` or `.dat`).

The general syntax is:

```bash
./msi2lmp.exe [base_filename] -f /path/to/forcefield_file.frc
```

Where:
*   `[base_filename]`: The name of your `.car` and `.mdf` files without their extensions (e.g., if your files are `my_structure.car` and `my_structure.mdf`, you would use `my_structure`).
*   `-f /path/to/forcefield_file.frc`: The `-f` flag specifies the forcefield file to be used for parameterization. Ensure the path to this file is correct relative to where you are running the command.

The output will be a `.data` file named `[base_filename].data` in the directory from which you executed the command.

## 4. Example

Let's assume you have the following files:
*   `msi2lmps/rectangular_Ti3C2_OH_Bilayer.car`
*   `msi2lmps/rectangular_Ti3C2_OH_Bilayer.mdf`
*   `forcefields/cvff.frc` (This file was previously `cvff_iff_v1_5_MXenes.frc` and was renamed to `cvff.frc` for compatibility with `msi2lmp.exe`'s default forcefield naming convention.)

To convert these files into a LAMMPS `.data` file, navigate to the `msi2lmps/` directory and then execute `msi2lmp.exe` from there, providing the relative path to the executable and the forcefield file:

```bash
cd msi2lmps/
../0-ExternalScripts/msi2lmp.exe rectangular_Ti3C2_OH_Bilayer -f ../forcefields/cvff.frc
```

After successful execution, a new file named `rectangular_Ti3C2_OH_Bilayer.data` will be created in the `msi2lmps/` directory.

**Note on Forcefield File Naming and Case Sensitivity:**
The `msi2lmp.exe` tool, by default, looks for a forcefield file named `cvff.frc` in a directory relative to its execution path. If your forcefield file has a different name (e.g., `cvff_iff_v1_5_MXenes.frc`), you might need to rename it to `cvff.frc` or ensure the `-f` flag correctly points to its location and name. In this project, `forcefields/cvff_iff_v1_5_MXenes.frc` was renamed to `forcefields/cvff.frc` to facilitate its use with `msi2lmp.exe`.

**Important:** Force field atom types are case-sensitive. The atom types in the `.car` and `.mdf` files must exactly match the case used in the `.frc` file.