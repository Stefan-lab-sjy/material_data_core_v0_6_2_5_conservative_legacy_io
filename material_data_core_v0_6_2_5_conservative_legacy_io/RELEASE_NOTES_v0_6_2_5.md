# v0.6.2.5 Release Notes — Conservative Historical I/O Provenance

## Why this release exists

Real laboratory VASP folders are usually inspected **after** a run has completed.
The final directory can contain `WAVECAR` or `CHGCAR`, but their presence after the
run does not prove those files existed before the run.  Therefore `ISTART` /
`ICHARG` are dependency hints, not sufficient provenance to rewrite a historical
file as an input.

## New rule for historical-folder import

Default confirmed VASP inputs:

- `INCAR`
- `POSCAR`
- `KPOINTS`
- `POTCAR`

Workflow-specific confirmed inputs are still supported, for example HSE/band:

- `KPATH.in`
- `HIGH_SYMMETRY_POINTS` (in confirmed band context)

Completed-folder products remain outputs unless direct provenance exists:

- `WAVECAR`
- `CHGCAR`
- `CHG`
- `OUTCAR`, `CONTCAR`, `DOSCAR`, `EIGENVAL`, `PROCAR`, `AECCAR*`, ...

If `ISTART > 0` or `ICHARG in {1,11}`, the explanation records that a restart
dependency is possible, but the primary role stays `output` because no pre-run
input manifest exists.

## Future direction

When the agent itself creates a run, a pre-run input manifest should become the
authoritative provenance source.  Such a manifest can then explicitly record
`WAVECAR` / `CHGCAR` as inputs when they are deliberately supplied.

## Compatibility

- Storage remains `catalog.db + objects/sha256`.
- Recursive Calculation discovery remains unchanged.
- Workflow inference (`geometry_optimization`, `static_scf`, `hse_band`,
  `molecular_dynamics`, etc.) remains unchanged.
- Filename fidelity remains unchanged.
- Re-importing an unchanged Calculation refreshes semantics in place; it does not
  duplicate the Calculation or SHA256 objects.
