# Material Data Core + Material Agent v0.6.2.5

## v0.6.2.5 本次重点：历史目录采用保守 I/O 证据规则

对于已经计算结束的 VASP 文件夹，最终目录中的 `WAVECAR` / `CHGCAR` 不能证明它们在运行前就存在。
因此本版将历史目录的确定输入收紧为 `INCAR / POSCAR / KPOINTS / POTCAR` 加 workflow 特殊输入（例如 HSE band 的 `KPATH.in`、`HIGH_SYMMETRY_POINTS`）。
`ISTART / ICHARG` 只作为可能的依赖提示，不再自动把 `WAVECAR / CHGCAR` 改成 input。


## v0.6.2.4 本次重点

本版本继续保持 `catalog.db + objects/sha256 + calculations + calculation_files` 架构不变，只收口真实 VASP 测试暴露出的基础 workflow 语义问题：

1. **分子动力学识别**：`NSW > 0` 不再自动等价于结构优化。若 `IBRION = 0`，识别为 `workflow = molecular_dynamics`、`calc_type = md`；`NSW` 作为 MD 步数证据。
2. **结构优化保持兼容**：`NSW > 0` 且不是 `IBRION = 0` 的常见弛豫输入继续识别为 `geometry_optimization`。
3. **MD 证据增强**：若存在 `POTIM / MDALGO / TEBEG / TEEND / SMASS`，会一并记录到 Evidence。
4. **CHG/CHGCAR 语义收口**：`ICHARG = 1/11` 时只有 `CHGCAR` 被提升为当前 Calculation 的 input；`CHG` 保持输出语义，不再被上下文规则误判为 restart 输入。
5. v0.6.2.3 已修复的真实 INCAR 注释解析、文件名原始大小写、递归 discovery、HSE band / optics / static SCF 识别全部保留。

推荐先运行 `START_HERE.bat`，然后用 `CHECK_IO_CLASSIFICATION.bat` 检查真实 MD 目录。预期例如：

```text
NSW = 5000
IBRION = 0
→ Calc type : md
→ Workflow  : molecular_dynamics
```

v0.6.2 直接基于已经验证过的 v0.6.1 增量开发。`catalog.db + data/objects/sha256 + materials / structures / calculations / calculation_files` 全部保留，递归 Calculation discovery 与 Calculation Boundary 也保留。

本版只集中解决一个问题：**输入/输出判定不能再只依赖文件名。**

## 1. v0.6.2 的分类模型

现在分两步：

```text
filename/content convention
        ↓
semantic_type：这个文件是什么？
        ↓
INCAR + KPOINTS + 文件组合 + workflow
        ↓
role：它在当前 Calculation 里做什么？
```

允许的 role：

```text
input
output
reference
intermediate
auxiliary
unknown
```

不再要求所有文件强行二选一 input/output。无法可靠判断时保留 `unknown`，避免错误自动化。

每条 `calculation_files` 关系新增：

```text
role_confidence
role_reason
role_source
classification_version
```

因此程序不仅给结论，还保存“为什么这样判”。

## 2. HSE / band 真实工作流

在确认的 band / HSE-band Calculation 中：

```text
KPATH.in               input      band_kpath
HIGH_SYMMETRY_POINTS   input      high_symmetry_points
INCAR                   input      parameters
POSCAR                  input      structure
KPOINTS                 input      kpoints
POTCAR                  input      potential

BAND.dat                output     band_structure_data
BAND_GAP                output     band_gap_result
KLINES.dat              output     band_kpath_data
KLABELS                 output     kpoint_labels
OUTCAR                  output     main_output
EIGENVAL                output     eigenvalues
PROCAR                  output     projected_bands
```

`HIGH_SYMMETRY_POINTS` 在没有 band 上下文时不会硬判为 output，而是安全地记为 `reference`。进入已经确认的 band/HSE-band Calculation 后，按照当前实验室工作流把它视为 `input/reference` 中的主角色 `input`，并保留原因和置信度。

同时识别显式 workflow 输入：

```text
FERMI_ENERGY.in
TRANSMAT.in
KPOINTS_MAPPING_TABLE.in
```

## 3. VASP 上下文规则

除 band 文件外，本版开始使用 INCAR 作为强证据。例如：

```text
ICHARG = 11
→ CHGCAR 在当前 Calculation 中判为 input

ISTART > 0
→ WAVECAR 在当前 Calculation 中判为 input
```

这比“CHGCAR/WAVECAR 永远是 output”更符合串联计算的实际情况。

## 4. 最推荐的真实数据测试

第一次先双击：

```text
START_HERE.bat
```

应该看到：

```text
Ran 60 tests
OK
```

然后双击：

```text
CHECK_IO_CLASSIFICATION.bat
```

粘贴你最熟悉的一次计算，例如：

```text
D:\SCI\Zr2CO2\HSEband
```

这一步只显示精简分类表，**不写数据库、不修改原始 VASP 目录**。表格包含：

```text
ROLE
PATH
SEMANTIC TYPE
CONF
SOURCE
REASON
```

重点检查：

```text
KPATH.in               input
HIGH_SYMMETRY_POINTS   input
BAND_GAP                output
BAND.dat                output
```

如果输入外层：

```text
D:\SCI\Zr2CO2
```

会只汇总递归发现的各 Calculation 与 role 数量，不刷出所有文件。要检查具体文件，再把某个 HSEband/relax/DOS 子目录交给 `CHECK_IO_CLASSIFICATION.bat`。

## 5. 正式入库与旧数据升级

确认后仍使用：

```text
AUTO_INGEST_PATH.bat
```

如果同一 Calculation 已经由 v0.6.0/v0.6.1 入库，重新导入时：

```text
fingerprint 相同
→ 不创建第二条 Calculation
→ 不重复复制 SHA256 对象
→ 原地刷新 v0.6.2 自动分类
```

但 `role_source = user_override` 的人工纠正不会被自动规则覆盖。

## 6. 看懂“为什么这样判”

正式入库后先运行：

```text
LIST_CALCULATIONS.bat
```

本版会直接显示 source path，方便找到 HSEband 对应的 `calculation_id`。

再运行：

```text
LIST_CALC_FILES.bat
```

可以看到 role / semantic_type / confidence / source。

对某一个文件想看完整解释：

```text
EXPLAIN_CALC_FILE.bat
```

例如输入：

```text
calculation_id = calc_xxx
relative path  = HIGH_SYMMETRY_POINTS
```

会显示 `role_reason` 和 `role_source`。

## 7. 人工纠正

如果某个实验室特殊流程程序仍判错：

```text
OVERRIDE_CALC_FILE.bat
```

可以把它人工设为：

```text
input / output / reference / intermediate / auxiliary / unknown
```

数据库记录：

```text
role_source = user_override
role_confidence = 1.0
```

之后重复导入同一 Calculation，自动分类不会覆盖你的人工判断。

要恢复自动判断：

```text
CLEAR_CALC_FILE_OVERRIDE.bat
```

然后重新导入同一个 Calculation。

## 8. 递归功能仍保持 v0.6.1 行为

外层目录继续支持：

```text
D:\SCI\Zr2CO2
  ├─ HSEband      → Calculation
  ├─ guang\...    → Calculation
  ├─ elastic\...  → Calculation
  └─ stru         → Calculation
```

父 Calculation 不会吞掉嵌套子 Calculation 的文件。

## 9. 存储原则没有改变

真实 VASP 工作目录仍保持原样，不拆 `input/` / `output/`：

```text
原始目录不动
     ↓
SHA256 object store 物理统一保存
     ↓
calculation_files 逻辑记录 role + semantic_type + evidence
```

需要时仍可：

```text
EXPORT_INPUT_SET.bat
EXPORT_OUTPUT_SET.bat
```

按逻辑角色恢复文件集合。
