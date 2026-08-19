from __future__ import annotations

import os
from pathlib import Path
import shutil
from typing import Any

from .calculations import CalculationService
from .classifier import classify_path, detect_vasp_folder
from .semantics import VALID_ROLES, build_vasp_context, classify_calculation_file
from .ingestion import IngestionService
from .parsers import detect_completion, infer_calculation, parse_incar, parse_kpoints, parse_poscar
from .repository import CatalogRepository
from .utils import new_id

INBOX_IGNORE_NAMES = {"PUT_FILES_HERE.txt", "Thumbs.db", ".DS_Store"}
DISCOVERY_IGNORE_DIRS = {".git", ".svn", ".hg", ".venv", "__pycache__", ".idea", ".vscode", "node_modules"}


class AutoIngestService:
    """Route files, one VASP Calculation, or a nested VASP collection.

    v0.6.2 deliberately keeps the v0.5/v0.6 storage model unchanged:
    CatalogRepository + SHA256 object storage remain the source of truth.  This
    service only discovers data units and routes each Calculation to the existing
    CalculationService.
    """

    def __init__(
        self,
        repository: CatalogRepository,
        ingestion: IngestionService,
        calculations: CalculationService,
    ) -> None:
        self.repository = repository
        self.ingestion = ingestion
        self.calculations = calculations

    @staticmethod
    def _vasp_file_plan(
        folder: Path,
        *,
        incar: dict[str, Any] | None = None,
        kpoints: dict[str, Any] | None = None,
        inferred: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], Any]:
        paths = CalculationService._scan_folder(folder)
        context = build_vasp_context(
            folder, paths=paths, incar_meta=incar or {"tags": {}},
            kpoints_meta=kpoints or {}, inferred=inferred or {},
        )
        rows: list[dict[str, Any]] = []
        for p in paths:
            rel = p.relative_to(folder).as_posix()
            decision = classify_calculation_file(p.name, context)
            rows.append(
                {
                    "path": rel,
                    "file_type": p.name,
                    **decision,
                    "size_bytes": p.stat().st_size,
                }
            )
        return rows, context

    @staticmethod
    def discover_vasp_folders(root: str | Path) -> list[Path]:
        """Recursively discover directories that are themselves VASP calculations.

        Discovery checks every directory independently.  It does not use folder names
        such as ``band`` or ``guang`` as truth; native VASP marker files are the strong
        evidence.  Nested calculations are allowed and returned as separate roots.
        """
        root = Path(root).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            return []

        found: list[Path] = []
        for current, dirnames, _ in os.walk(root):
            # Avoid traversing development/tooling directories, but do not make
            # assumptions about scientific folder names.
            dirnames[:] = [d for d in dirnames if d not in DISCOVERY_IGNORE_DIRS]
            current_path = Path(current)
            if current_path == root:
                continue
            try:
                if detect_vasp_folder(current_path).get("is_vasp"):
                    found.append(current_path)
            except OSError:
                continue

        found.sort(key=lambda p: p.relative_to(root).as_posix().casefold())
        return found

    def _single_vasp_plan(self, folder: Path, detection: dict[str, Any] | None = None) -> dict[str, Any]:
        detection = detection or detect_vasp_folder(folder)
        incar = parse_incar(folder / "INCAR") if (folder / "INCAR").exists() else {"tags": {}}
        kpoints = parse_kpoints(folder / "KPOINTS") if (folder / "KPOINTS").exists() else {}
        poscar = parse_poscar(folder / "POSCAR") if (folder / "POSCAR").exists() else {}
        inferred = infer_calculation(incar, kpoints)
        files, context = self._vasp_file_plan(folder, incar=incar, kpoints=kpoints, inferred=inferred)
        role_counts = {
            role: sum(1 for row in files if row["role"] == role)
            for role in sorted(VALID_ROLES)
        }
        return {
            "path": str(folder),
            "kind": "vasp_calculation",
            "action": "import_vasp_folder",
            "confidence": detection["confidence"],
            "markers": detection["markers"],
            "reason": detection["reason"],
            "formula": poscar.get("formula"),
            "atom_count": poscar.get("atom_count"),
            "calc_type": (inferred.get("calc_type") if inferred.get("calc_type") not in {None, "", "unknown"} else context.calc_type),
            "workflow": context.workflow,
            "workflow_evidence": list(context.evidence),
            "functional": inferred.get("functional") or context.functional,
            "soc": inferred.get("soc") if inferred.get("soc") is not None else context.soc,
            "calculation_status": detect_completion(folder),
            "discovered_files": len(files),
            "role_counts": role_counts,
            "files": files,
        }

    def inspect_path(self, path: str | Path) -> dict[str, Any]:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return {"path": str(p), "kind": "missing", "action": "none", "error": "path_not_found"}

        if p.is_file():
            category, subcategory = classify_path(p)
            return {
                "path": str(p),
                "kind": "file",
                "action": "ingest_file",
                "category": category,
                "subcategory": subcategory,
                "size_bytes": p.stat().st_size,
            }

        if not p.is_dir():
            return {"path": str(p), "kind": "unsupported", "action": "none"}

        detection = detect_vasp_folder(p)
        if detection["is_vasp"]:
            return self._single_vasp_plan(p, detection)

        nested = self.discover_vasp_folders(p)
        if nested:
            calculations: list[dict[str, Any]] = []
            total_files = 0
            total_roles = {role: 0 for role in sorted(VALID_ROLES)}
            for folder in nested:
                child_plan = self._single_vasp_plan(folder)
                child_plan["relative_path"] = folder.relative_to(p).as_posix()
                calculations.append(child_plan)
                total_files += int(child_plan["discovered_files"])
                for role in total_roles:
                    total_roles[role] += int(child_plan["role_counts"][role])

            return {
                "path": str(p),
                "kind": "vasp_collection",
                "action": "import_vasp_collection",
                "reason": "nested_VASP_calculations_detected",
                "calculations_found": len(calculations),
                "discovered_files": total_files,
                "role_counts": total_roles,
                "calculations": calculations,
            }

        return {
            "path": str(p),
            "kind": "unknown_directory",
            "action": "none",
            "confidence": detection["confidence"],
            "markers": detection["markers"],
            "reason": detection["reason"],
        }

    def ingest_path(self, path: str | Path, *, dry_run: bool = False, source_type: str = "auto_intake") -> dict[str, Any]:
        plan = self.inspect_path(path)
        if dry_run:
            return {"status": "dry_run", "written": False, "plan": plan}

        kind = plan.get("kind")
        p = Path(plan["path"])
        if kind == "file":
            result = self.ingestion.ingest_file(p, source_type=source_type, source_uri=str(p))
            return {
                "status": result.status,
                "written": True,
                "kind": "file",
                "file_id": result.file_id,
                "duplicate": result.duplicate,
                "sha256": result.sha256,
                "plan": plan,
            }

        if kind == "vasp_calculation":
            result = self.calculations.import_vasp_folder(p, source_type=source_type)
            return {
                "status": result.status,
                "written": True,
                "kind": "vasp_calculation",
                "calculation_id": result.calculation_id,
                "duplicate": result.status == "duplicate_calculation",
                "result": result.to_dict(),
                "plan": plan,
            }

        if kind == "vasp_collection":
            imported = 0
            duplicates = 0
            failed = 0
            results: list[dict[str, Any]] = []
            for child in plan["calculations"]:
                folder = Path(child["path"])
                try:
                    result = self.calculations.import_vasp_folder(folder, source_type=source_type)
                    duplicate = result.status == "duplicate_calculation"
                    if duplicate:
                        duplicates += 1
                    else:
                        imported += 1
                    results.append(
                        {
                            "relative_path": child["relative_path"],
                            "source_path": str(folder),
                            "status": result.status,
                            "calculation_id": result.calculation_id,
                            "duplicate": duplicate,
                            "result": result.to_dict(),
                        }
                    )
                except Exception as exc:
                    failed += 1
                    results.append(
                        {
                            "relative_path": child["relative_path"],
                            "source_path": str(folder),
                            "status": "failed",
                            "error": str(exc),
                        }
                    )

            status = "imported_collection" if failed == 0 else "partial_failure"
            return {
                "status": status,
                "written": imported > 0,
                "kind": "vasp_collection",
                "imported_calculations": imported,
                "duplicates": duplicates,
                "failed": failed,
                "results": results,
                "plan": plan,
            }

        return {"status": "skipped", "written": False, "kind": kind, "plan": plan}

    def ingest_inbox(
        self,
        inbox: str | Path,
        *,
        processed_root: str | Path,
        failed_root: str | Path,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        inbox = Path(inbox).expanduser().resolve()
        inbox.mkdir(parents=True, exist_ok=True)
        entries = [p for p in inbox.iterdir() if p.name not in INBOX_IGNORE_NAMES]
        entries.sort(key=lambda p: p.name.lower())

        batch_id = new_id("batch")
        processed_root = Path(processed_root) / batch_id
        failed_root = Path(failed_root) / batch_id

        summary: dict[str, Any] = {
            "batch_id": batch_id,
            "dry_run": dry_run,
            "discovered_items": len(entries),
            "imported_calculations": 0,
            "stored_files": 0,
            "duplicates": 0,
            "skipped": 0,
            "failed": 0,
            "details": [],
        }

        for item in entries:
            try:
                result = self.ingest_path(item, dry_run=dry_run, source_type="inbox_auto")
                detail = {"item": item.name, **result}
                summary["details"].append(detail)

                if dry_run:
                    continue

                if result["status"] == "skipped":
                    summary["skipped"] += 1
                    continue

                if result["status"] == "partial_failure":
                    # Keep the original collection in place so failed calculations
                    # can be inspected/retried without a destructive move.
                    summary["failed"] += int(result.get("failed", 1))
                    summary["imported_calculations"] += int(result.get("imported_calculations", 0))
                    summary["duplicates"] += int(result.get("duplicates", 0))
                    continue

                if result["kind"] == "vasp_collection":
                    summary["imported_calculations"] += int(result.get("imported_calculations", 0))
                    summary["duplicates"] += int(result.get("duplicates", 0))
                elif result.get("duplicate"):
                    summary["duplicates"] += 1
                elif result["kind"] == "vasp_calculation":
                    summary["imported_calculations"] += 1
                elif result["kind"] == "file":
                    summary["stored_files"] += 1

                target = processed_root / item.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(item), str(target))
                detail["archived_to"] = str(target)

                # Update Calculation source paths after the INBOX unit is archived.
                if result.get("calculation_id"):
                    self.repository.update_calculation_source_path(result["calculation_id"], str(target))
                elif result["kind"] == "vasp_collection":
                    for calc_result in result.get("results", []):
                        calc_id = calc_result.get("calculation_id")
                        rel = calc_result.get("relative_path")
                        if calc_id and rel:
                            self.repository.update_calculation_source_path(calc_id, str(target / Path(rel)))
            except Exception as exc:
                summary["failed"] += 1
                detail = {"item": item.name, "status": "failed", "error": str(exc)}
                summary["details"].append(detail)
                if dry_run:
                    continue
                target = failed_root / item.name
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.move(str(item), str(target))
                    detail["archived_to"] = str(target)
                except Exception:
                    pass

        return summary
