# v0.6.2.4 Release Notes — Molecular Dynamics Workflow Fix

## Scope
A narrow workflow-classification correction on top of v0.6.2.3. Storage, schema, recursive discovery, filename fidelity, and INCAR annotation parsing are unchanged.

## Fixed
- `NSW > 0` no longer automatically means geometry optimization.
- `IBRION = 0` with positive `NSW` is classified as `calc_type = md`, `workflow = molecular_dynamics`.
- MD evidence records `NSW`, `IBRION`, and when present `POTIM`, `MDALGO`, `TEBEG`, `TEEND`, `SMASS`.
- `IBRION = 1/2/3` with positive `NSW` continues to classify as geometry optimization.
- `ICHARG = 1/11` now promotes `CHGCAR` (not generic `CHG`) to input.

## Expected real-data behavior
For a molecular-dynamics folder such as:
```text
NSW = 5000
IBRION = 0
ISIF = 2
EDIFFG = -0.01
```
Expected:
```text
Calc type : md
Workflow  : molecular_dynamics
Evidence  : INCAR:NSW=5000>0, INCAR:IBRION=0, ...
```

For a relaxation folder such as `NSW=100`, `IBRION=2`, behavior remains:
```text
Calc type : relax
Workflow  : geometry_optimization
```
