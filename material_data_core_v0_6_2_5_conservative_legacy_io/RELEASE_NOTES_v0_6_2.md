# v0.6.2 Release Notes — Context-aware I/O Classification

## A. 不再 filename-only

新增 `src/material_agent/semantics/`：

- `context.py`：从 INCAR、KPOINTS、文件组合建立 workflow context；
- `rules.py`：先识别 semantic identity，再根据 context 决定 role。

## B. 新角色与可解释性

roles：`input / output / reference / intermediate / auxiliary / unknown`。

`calculation_files` 新增：

- `role_confidence`
- `role_reason`
- `role_source`
- `classification_version`

对 v0.5/v0.6.0/v0.6.1 数据库自动做 SQLite migration。

## C. HSE-band 规则

- `KPATH.in`：band/HSE-band -> input
- `HIGH_SYMMETRY_POINTS`：普通上下文 -> reference；band/HSE-band -> input/reference 主角色 input
- `BAND.dat / BAND_GAP / KLINES.dat / KLABELS` -> output
- `FERMI_ENERGY.in / TRANSMAT.in / KPOINTS_MAPPING_TABLE.in` -> input

## D. VASP 读取上下文

- `ICHARG in {1,11}` 时，`CHGCAR` -> input
- `ISTART > 0` 时，`WAVECAR` -> input

## E. 人工纠正

新增：

- `override-calc-file`
- `clear-calc-file-override`
- `EXPLAIN_CALC_FILE.bat`
- `OVERRIDE_CALC_FILE.bat`
- `CLEAR_CALC_FILE_OVERRIDE.bat`

人工 override 在重复入库时受保护。

## F. 更易测试

新增 `inspect-io` / `CHECK_IO_CLASSIFICATION.bat`，可在不写数据库的情况下直接查看：role、semantic_type、confidence、source、reason。

`LIST_CALCULATIONS.bat` 现在显示 source path，方便从实际目录定位 calculation_id。

## G. Regression

45 个 unittest 全部通过，包括 v0.6.1 递归/边界回归，以及 HSE-band、HIGH_SYMMETRY_POINTS、KPATH.in、CHGCAR ICHARG、manual override 和 schema migration 专项测试。
