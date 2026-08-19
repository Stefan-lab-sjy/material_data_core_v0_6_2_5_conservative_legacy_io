from __future__ import annotations

from pathlib import Path
import hashlib
import os
import json
import shutil
from typing import Any

from .classifier import detect_vasp_folder
from .semantics import build_vasp_context, classify_calculation_file
from .ingestion import IngestionService
from .models import CalculationImportResult
from .parsers import parse_incar, parse_kpoints, parse_poscar, infer_calculation, detect_completion
from .repository import CatalogRepository
from .utils import normalized_formula, json_dumps

IGNORE_NAMES = {"Thumbs.db", ".DS_Store"}
IGNORE_SUFFIXES = {".lock", ".tmp", ".swp"}


class CalculationService:
    def __init__(self, repository: CatalogRepository, ingestion: IngestionService):
        self.repository = repository
        self.ingestion = ingestion

    @staticmethod
    def _scan_folder(folder: Path) -> list[Path]:
        """Scan files belonging to exactly one Calculation.

        v0.6.1+ Calculation boundaries: when a child directory is itself
        detected as another VASP calculation, that child subtree is excluded from
        the parent calculation. This prevents a parent calculation from swallowing
        files belonging to nested band/DOS/optics calculations. Non-calculation
        subdirectories are still scanned because they may contain legitimate
        post-processing files belonging to the current calculation.
        """
        folder = Path(folder).expanduser().resolve()
        result: list[Path] = []

        for current, dirnames, filenames in os.walk(folder):
            current_path = Path(current)

            # Prune child calculation roots before os.walk descends into them.
            kept_dirs: list[str] = []
            for dirname in dirnames:
                child = current_path / dirname
                if dirname in {'.git', '.svn', '__pycache__', '.venv'}:
                    continue
                try:
                    if detect_vasp_folder(child).get('is_vasp'):
                        continue
                except OSError:
                    pass
                kept_dirs.append(dirname)
            dirnames[:] = kept_dirs

            for filename in filenames:
                p = current_path / filename
                if p.name in IGNORE_NAMES or p.suffix.lower() in IGNORE_SUFFIXES:
                    continue
                result.append(p)

        result.sort(key=lambda p: p.relative_to(folder).as_posix().lower())
        return result

    @staticmethod
    def _calc_fingerprint(folder: Path, file_records: list[tuple[Path, Any]]) -> str:
        h = hashlib.sha256()
        for path, result in sorted(file_records, key=lambda x: x[0].relative_to(folder).as_posix()):
            rel = path.relative_to(folder).as_posix()
            h.update(rel.encode('utf-8', errors='surrogatepass'))
            h.update(b'\0')
            h.update(result.sha256.encode('ascii'))
            h.update(b'\n')
        return h.hexdigest()

    def import_vasp_folder(self, folder: str | Path, *, source_type: str = "vasp_folder") -> CalculationImportResult:
        folder = Path(folder).expanduser().resolve()
        if not folder.exists() or not folder.is_dir():
            raise ValueError(f"Not a folder: {folder}")
        paths = self._scan_folder(folder)
        if not paths:
            raise ValueError(f"Folder is empty: {folder}")

        # Build scientific context before assigning file roles.  This is the key
        # v0.6.2 change: a workflow file is no longer classified by its basename
        # alone.  The same context is reused during duplicate semantic refresh.
        incar_meta = parse_incar(folder / 'INCAR') if (folder / 'INCAR').exists() else {"tags": {}}
        kpoints_meta = parse_kpoints(folder / 'KPOINTS') if (folder / 'KPOINTS').exists() else {}
        poscar_meta = parse_poscar(folder / 'POSCAR') if (folder / 'POSCAR').exists() else {}
        inferred = infer_calculation(incar_meta, kpoints_meta)
        classification_context = build_vasp_context(
            folder, paths=paths, incar_meta=incar_meta, kpoints_meta=kpoints_meta, inferred=inferred
        )
        effective_calc_type = (
            inferred.get('calc_type') if inferred.get('calc_type') not in {None, '', 'unknown'}
            else classification_context.calc_type
        )
        effective_functional = inferred.get('functional') or classification_context.functional
        effective_soc = inferred.get('soc') if inferred.get('soc') is not None else classification_context.soc
        calc_status = detect_completion(folder)

        file_records: list[tuple[Path, Any]] = []
        new_objects = 0
        reused_objects = 0
        for p in paths:
            rel = p.relative_to(folder).as_posix()
            result = self.ingestion.ingest_file(
                p, source_type=source_type, source_uri=str(p),
                metadata={"original_relative_path": rel, "calculation_folder": str(folder)},
            )
            file_records.append((p, result))
            if result.duplicate:
                reused_objects += 1
            else:
                new_objects += 1

        fingerprint = self._calc_fingerprint(folder, file_records)
        existing_calc = self.repository.get_calculation_by_fingerprint(fingerprint)
        if existing_calc:
            # Semantic rules can improve over time. Re-importing the exact
            # same Calculation must therefore refresh role/semantic_type in-place
            # without creating a new Calculation or copying objects again.
            existing_id = existing_calc['calculation_id']
            # v0.6.2.5 filename fidelity: older catalogs may contain normalized or
            # lower-cased logical names. Re-importing the unchanged Calculation uses
            # the real source tree as authority and repairs only display/path casing;
            # SHA256 objects and calculation identity remain untouched.
            filename_repairs = 0
            for source_path, _result in file_records:
                actual_rel = source_path.relative_to(folder).as_posix()
                if self.repository.repair_calculation_file_name_case(existing_id, actual_rel):
                    filename_repairs += 1

            self.repository.update_calculation_inference(
                existing_id, calc_type=effective_calc_type, functional=effective_functional,
                soc=effective_soc, workflow=classification_context.workflow,
                evidence=list(classification_context.evidence),
                classification_version='0.6.2.5',
            )
            rows = self.repository.list_calculation_files(existing_id)
            semantic_updates = 0
            for row in rows:
                decision = classify_calculation_file(Path(row['original_relative_path']).name, classification_context)
                changed = any([
                    row['role'] != decision['role'],
                    row['semantic_type'] != decision['semantic_type'],
                    row['retention_class'] != decision['retention_class'],
                    abs(float(row.get('role_confidence') or 0.0) - float(decision['role_confidence'])) > 1e-9,
                    (row.get('role_reason') or '') != decision['role_reason'],
                    (row.get('role_source') or '') != decision['role_source'],
                    (row.get('classification_version') or '') != decision['classification_version'],
                ])
                if changed:
                    updated = self.repository.update_calculation_file_semantics(
                        existing_id, row['original_relative_path'],
                        role=decision['role'], semantic_type=decision['semantic_type'],
                        retention_class=decision['retention_class'],
                        role_confidence=decision['role_confidence'], role_reason=decision['role_reason'],
                        role_source=decision['role_source'],
                        classification_version=decision['classification_version'],
                        preserve_user_override=True,
                    )
                    if updated:
                        semantic_updates += 1

            self.repository.log_event(
                "calculation_duplicate_detected", calculation_id=existing_id,
                incoming_name=folder.name, source_type=source_type,
                details={
                    "source_path": str(folder),
                    "fingerprint": fingerprint,
                    "semantic_updates": semantic_updates,
                    "filename_repairs": filename_repairs,
                },
            )
            rows = self.repository.list_calculation_files(existing_id)
            aux = sum(1 for r in rows if r['role'] not in {'input', 'output'})
            return CalculationImportResult(
                status="duplicate_calculation", calculation_id=existing_calc['calculation_id'],
                material_id=existing_calc['material_id'], structure_id=existing_calc['structure_id'],
                calc_type=effective_calc_type, functional=effective_functional,
                soc=effective_soc,
                calculation_status=existing_calc['status'], discovered_files=len(paths),
                linked_files=len(rows), new_objects=new_objects, reused_objects=reused_objects,
                auxiliary_files=aux, fingerprint=fingerprint,
            )

        formula = poscar_meta.get('formula')
        material_id: str | None = None
        structure_id: str | None = None
        poscar_file_id: str | None = None
        for p, r in file_records:
            if p.relative_to(folder).as_posix() == 'POSCAR':
                poscar_file_id = r.file_id
                break
        if formula:
            nf = normalized_formula(formula)
            material_id = self.repository.get_or_create_material(formula, nf or formula, {"source": "POSCAR"})
        if poscar_meta:
            structure_id = self.repository.insert_structure(
                material_id=material_id, source_file_id=poscar_file_id,
                formula=formula, atom_count=poscar_meta.get('atom_count'), metadata=poscar_meta,
            )

        recipe_manifest = None
        recipe_manifest_path = folder / ".material-agent-run.json"
        if recipe_manifest_path.exists():
            try:
                value = json.loads(recipe_manifest_path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    recipe_manifest = value
            except Exception:
                recipe_manifest = {"parse_error": True}

        calculation_metadata = {
            "incar": incar_meta,
            "kpoints": kpoints_meta,
            "poscar": poscar_meta,
            "classification_context": {
                "workflow": classification_context.workflow,
                "evidence": list(classification_context.evidence),
                "classification_version": "0.6.2.5",
            },
        }
        if recipe_manifest is not None:
            calculation_metadata["recipe"] = recipe_manifest

        calculation_id = self.repository.create_calculation(
            material_id=material_id, structure_id=structure_id,
            calc_type=effective_calc_type, functional=effective_functional, soc=effective_soc,
            status=calc_status, source_path=str(folder), fingerprint=fingerprint,
            metadata=calculation_metadata,
        )

        auxiliary_files = 0
        for p, result in file_records:
            rel = p.relative_to(folder).as_posix()
            file_type = p.name
            decision = classify_calculation_file(file_type, classification_context)
            role = decision['role']
            if role not in {'input', 'output'}:
                auxiliary_files += 1
            metadata: dict[str, Any] = {}
            if rel == 'INCAR':
                metadata = incar_meta
            elif rel == 'KPOINTS':
                metadata = kpoints_meta
            elif rel == 'POSCAR':
                metadata = poscar_meta
            self.repository.link_calculation_file(
                calculation_id=calculation_id, file_id=result.file_id, file_type=file_type,
                role=role, semantic_type=decision['semantic_type'],
                retention_class=decision['retention_class'],
                original_relative_path=rel, metadata=metadata,
                role_confidence=decision['role_confidence'],
                role_reason=decision['role_reason'], role_source=decision['role_source'],
                classification_version=decision['classification_version'],
            )
        self.repository.log_event(
            "calculation_imported", calculation_id=calculation_id, incoming_name=folder.name,
            source_type=source_type, details={"source_path": str(folder), "fingerprint": fingerprint,
                                                "files": len(file_records)},
        )
        return CalculationImportResult(
            status="imported", calculation_id=calculation_id, material_id=material_id,
            structure_id=structure_id, calc_type=effective_calc_type,
            functional=effective_functional, soc=effective_soc, calculation_status=calc_status,
            discovered_files=len(paths), linked_files=len(file_records), new_objects=new_objects,
            reused_objects=reused_objects, auxiliary_files=auxiliary_files, fingerprint=fingerprint,
        )

    def export_files(self, calculation_id: str, dest: str | Path, *, inputs_only: bool = False, role: str | None = None) -> Path:
        rows = self.repository.list_calculation_files(calculation_id)
        if not rows:
            raise KeyError(f"Unknown calculation_id: {calculation_id}")
        if inputs_only and role is not None:
            raise ValueError("Use either inputs_only=True or role=..., not both")
        selected_role = "input" if inputs_only else role
        if selected_role is not None and selected_role not in {"input", "output", "reference", "intermediate", "auxiliary", "unknown"}:
            raise ValueError(f"Unsupported calculation file role: {selected_role}")
        dest = Path(dest).expanduser().resolve()
        dest.mkdir(parents=True, exist_ok=True)
        selected = [r for r in rows if selected_role is None or r['role'] == selected_role]
        for r in selected:
            rel = Path(r['original_relative_path'])
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(r['stored_path'], target)
        return dest

    def verify_calculation_against_folder(self, calculation_id: str, folder: str | Path) -> list[dict[str, Any]]:
        """Verify every logical file of a calculation against an original folder by relative path + SHA256."""
        folder = Path(folder).expanduser().resolve()
        if not folder.exists() or not folder.is_dir():
            raise ValueError(f"Not a folder: {folder}")
        db_rows = self.repository.list_calculation_files(calculation_id)
        if not db_rows:
            raise KeyError(f"Unknown calculation_id: {calculation_id}")

        db_by_path = {r['original_relative_path']: r for r in db_rows}
        source_paths = self._scan_folder(folder)
        source_by_path = {p.relative_to(folder).as_posix(): p for p in source_paths}
        keys = sorted(set(db_by_path) | set(source_by_path))
        results: list[dict[str, Any]] = []
        for rel in keys:
            row = db_by_path.get(rel)
            src = source_by_path.get(rel)
            src_sha = None
            if src is not None:
                h = hashlib.sha256()
                with src.open('rb') as f:
                    for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
                        h.update(chunk)
                src_sha = h.hexdigest()

            if row is None:
                status = 'NOT_LINKED'
            elif src is None:
                status = 'MISSING_SOURCE'
            elif src_sha != row['sha256']:
                status = 'HASH_MISMATCH'
            else:
                status = 'MATCH'

            results.append({
                'path': rel,
                'file_type': (row['file_type'] if row else Path(rel).name),
                'role': (row['role'] if row else None),
                'db_sha256': (row['sha256'] if row else None),
                'source_sha256': src_sha,
                'file_id': (row['file_id'] if row else None),
                'status': status,
            })
        return results

    def compare_calculations(self, calc_a: str, calc_b: str) -> list[dict[str, Any]]:
        a_rows = self.repository.list_calculation_files(calc_a)
        b_rows = self.repository.list_calculation_files(calc_b)
        if not a_rows:
            raise KeyError(calc_a)
        if not b_rows:
            raise KeyError(calc_b)
        a = {r['original_relative_path']: r for r in a_rows}
        b = {r['original_relative_path']: r for r in b_rows}
        keys = sorted(set(a) | set(b))
        result: list[dict[str, Any]] = []
        for key in keys:
            ra, rb = a.get(key), b.get(key)
            result.append({
                "path": key,
                "file_type": (ra or rb)['file_type'],
                "sha256_a": ra['sha256'] if ra else None,
                "sha256_b": rb['sha256'] if rb else None,
                "same": bool(ra and rb and ra['sha256'] == rb['sha256']),
                "present_a": ra is not None,
                "present_b": rb is not None,
            })
        return result
