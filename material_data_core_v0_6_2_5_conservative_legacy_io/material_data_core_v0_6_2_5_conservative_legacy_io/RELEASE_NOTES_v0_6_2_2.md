# v0.6.2.2 Release Notes — Workflow + Filename Fidelity Fix

## Scope

No Web layer and no storage redesign. The v0.6.2.1 data core remains intact.

## Fixed

- Parse semicolon-separated INCAR assignments, e.g. `IBRION=2 ; NSW=200 ; ISIF=2`.
- Context workflow `geometry_optimization` from ionic-relaxation evidence.
- Context workflow `static_scf` from explicit static tags or, when defaults are omitted, electronic outputs plus absence of relaxation evidence.
- Folder names such as `opt` and `scr` are not used as truth.
- Preserve exact source filename/path case for Calculation-level queries and exports.
- Separate content-object first-seen name (`object_original_name`) from logical Calculation source name (`original_name` / `display_name`).
- Duplicate re-import repairs legacy lower-cased logical paths in-place without duplicating SHA256 objects.
- Duplicate re-import can refresh a legacy `unknown` Calculation type using improved workflow inference.

## Compatibility

- Coarse database `calc_type` remains backward compatible: `relax`, `static`, `band`, etc.
- Rich context `workflow` uses `geometry_optimization`, `static_scf`, `band_structure`, `hse_band`, etc.
- Existing catalogs can be reused. Re-import the same Calculation/project to refresh semantics and filename fidelity.

## Tests

53 automated tests pass, including new regression tests for semicolon INCAR syntax, workflow inference, same-SHA/different-logical-name behavior, and legacy lowercase path repair.
