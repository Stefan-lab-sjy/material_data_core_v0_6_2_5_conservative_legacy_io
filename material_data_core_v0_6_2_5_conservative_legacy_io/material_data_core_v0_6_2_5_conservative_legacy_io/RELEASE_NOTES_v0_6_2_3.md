# v0.6.2.3 Release Notes — Real-world INCAR Annotation Parser Fix

## Scope
This is a narrow parser/workflow reliability fix on top of v0.6.2.2. The SQLite catalog, SHA256 object store, recursive discovery, filename fidelity, and I/O semantic schema are unchanged.

## Fixed
- Parses INCAR lines such as `NSW = 100 (Max ionic steps)` as integer `100`.
- Parses `IBRION = 2 (Algorithm: ...)`, `ISIF = 2 (...)`, `EDIFFG = -2E-02 (...)`, booleans such as `.FALSE. (...)`, and similar annotated scalar tags.
- Semicolons inside parenthetical human notes no longer split a line into fake assignments.
- Human annotation text is retained in `annotations` and the original right-hand side in `raw_tags`, but neither is used as workflow evidence.
- A geometry optimization with `NSW > 0` is therefore no longer incorrectly downgraded to `static_scf` merely because its numeric values have explanatory text after them.

## Expected SiS2 behavior
For the user's real `SiS2/opt` style INCAR containing `NSW=100`, `IBRION=2`, `ISIF=2`, `EDIFFG=-2E-02` with trailing parentheses:
- `calc_type = relax`
- `workflow = geometry_optimization`

For a static electronic run with no ionic-relaxation evidence:
- `calc_type = static`
- `workflow = static_scf`
