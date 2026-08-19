from __future__ import annotations

from pathlib import Path
from typing import Any

from .semantics import ClassificationContext, classify_calculation_file, semantic_identity

# Native VASP anchors used only for detecting Calculation roots.
VASP_INPUTS = {"INCAR", "KPOINTS", "POSCAR", "POTCAR"}
VASP_OUTPUTS = {
    "OUTCAR", "CONTCAR", "OSZICAR", "XDATCAR", "CHGCAR", "CHG", "WAVECAR",
    "WAVEDER", "DOSCAR", "EIGENVAL", "PROCAR", "LOCPOT", "IBZKPT", "PCDAT",
    "REPORT", "ELFCAR", "AECCAR0", "AECCAR1", "AECCAR2", "vasprun.xml",
}

STRUCTURE_EXTS = {".cif", ".xyz", ".vasp", ".xsf", ".pdb", ".mol", ".mol2"}
TABLE_EXTS = {".csv", ".tsv", ".xlsx", ".xls", ".parquet"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".svg", ".webp"}
DOCUMENT_EXTS = {".pdf", ".doc", ".docx", ".txt", ".md", ".rtf"}
ARCHIVE_EXTS = {".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz"}

# Backward-compatible symbol used by older tests/callers.
VASP_SEMANTIC_TYPES = {
    name: semantic_identity(name)["semantic_type"]
    for name in sorted(VASP_INPUTS | VASP_OUTPUTS)
}


def calculation_file_rule(filename: str, context: ClassificationContext | None = None) -> dict[str, Any]:
    """Return context-aware role/semantic/retention classification.

    Without a context this function remains safe and deterministic, which keeps
    older callers working. CalculationService and Auto Intake pass a context in
    v0.6.2 so ambiguous workflow files are not classified by filename alone.
    """
    return classify_calculation_file(filename, context)


def classify_path(path: Path) -> tuple[str, str]:
    name = path.name
    suffix = path.suffix.lower()
    identity = semantic_identity(name)
    if identity["semantic_type"] != "unknown":
        role = calculation_file_rule(name)["role"]
        return "calculation", f"calculation_{role}"
    if suffix in STRUCTURE_EXTS:
        return "structure", "structure_file"
    if suffix in TABLE_EXTS:
        return "table", "table_file"
    if suffix in IMAGE_EXTS:
        return "image", "image_file"
    if suffix in DOCUMENT_EXTS:
        return "document", "document_file"
    if suffix in ARCHIVE_EXTS:
        return "archive", "archive_file"
    return "other", "unknown"


def vasp_role(filename: str, context: ClassificationContext | None = None) -> str:
    return calculation_file_rule(filename, context)["role"]


def vasp_semantic_type(filename: str, context: ClassificationContext | None = None) -> str:
    return calculation_file_rule(filename, context)["semantic_type"]


def retention_class(filename: str, context: ClassificationContext | None = None) -> str:
    return calculation_file_rule(filename, context)["retention_class"]


def detect_vasp_folder(folder: Path) -> dict[str, Any]:
    """Conservatively decide whether *folder itself* is one VASP Calculation."""
    folder = Path(folder)
    if not folder.is_dir():
        return {"is_vasp": False, "confidence": 0.0, "markers": [], "reason": "not_a_directory"}

    try:
        names = {p.name for p in folder.iterdir() if p.is_file()}
    except OSError:
        return {"is_vasp": False, "confidence": 0.0, "markers": [], "reason": "unreadable_directory"}

    known = VASP_INPUTS | VASP_OUTPUTS
    markers = sorted(names & known)
    has_structure = "POSCAR" in names or "CONTCAR" in names
    has_control = "INCAR" in names
    has_output_anchor = "OUTCAR" in names or "vasprun.xml" in names
    input_count = len(names & VASP_INPUTS)

    if "POSCAR" in names and has_control:
        return {"is_vasp": True, "confidence": 1.0, "markers": markers, "reason": "POSCAR+INCAR"}
    if has_structure and has_output_anchor:
        return {"is_vasp": True, "confidence": 0.95, "markers": markers, "reason": "structure+VASP_output"}
    if input_count >= 3:
        return {"is_vasp": True, "confidence": 0.9, "markers": markers, "reason": "multiple_VASP_inputs"}
    if has_control and has_output_anchor:
        return {"is_vasp": True, "confidence": 0.85, "markers": markers, "reason": "INCAR+VASP_output"}

    return {
        "is_vasp": False,
        "confidence": min(0.7, 0.15 * len(markers)),
        "markers": markers,
        "reason": "insufficient_VASP_markers",
    }
