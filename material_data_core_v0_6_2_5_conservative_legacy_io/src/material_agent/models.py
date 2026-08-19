from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class IngestResult:
    status: str
    file_id: str
    sha256: str
    original_name: str
    stored_path: str
    category: str
    subcategory: str
    size_bytes: int
    source_type: str
    duplicate: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CalculationImportResult:
    status: str
    calculation_id: str
    material_id: str | None
    structure_id: str | None
    calc_type: str
    functional: str | None
    soc: bool | None
    calculation_status: str
    discovered_files: int
    linked_files: int
    new_objects: int
    reused_objects: int
    auxiliary_files: int
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
