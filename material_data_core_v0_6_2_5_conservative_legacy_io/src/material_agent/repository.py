from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import json
from typing import Any

from .utils import utc_now, new_id, json_dumps


SCHEMA = r"""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS files (
    file_id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL UNIQUE,
    original_name TEXT NOT NULL,
    extension TEXT,
    mime_type TEXT,
    size_bytes INTEGER NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_uri TEXT,
    status TEXT NOT NULL,
    parser_status TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS materials (
    material_id TEXT PRIMARY KEY,
    formula TEXT NOT NULL,
    normalized_formula TEXT NOT NULL UNIQUE,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS structures (
    structure_id TEXT PRIMARY KEY,
    material_id TEXT,
    source_file_id TEXT,
    formula TEXT,
    atom_count INTEGER,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(material_id) REFERENCES materials(material_id),
    FOREIGN KEY(source_file_id) REFERENCES files(file_id)
);

CREATE TABLE IF NOT EXISTS calculations (
    calculation_id TEXT PRIMARY KEY,
    material_id TEXT,
    structure_id TEXT,
    calc_type TEXT NOT NULL,
    functional TEXT,
    soc INTEGER,
    status TEXT NOT NULL,
    source_path TEXT,
    fingerprint TEXT NOT NULL UNIQUE,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(material_id) REFERENCES materials(material_id),
    FOREIGN KEY(structure_id) REFERENCES structures(structure_id)
);

CREATE TABLE IF NOT EXISTS calculation_files (
    calculation_id TEXT NOT NULL,
    file_id TEXT NOT NULL,
    file_type TEXT NOT NULL,
    role TEXT NOT NULL,
    semantic_type TEXT NOT NULL DEFAULT 'unknown',
    retention_class TEXT NOT NULL,
    role_confidence REAL NOT NULL DEFAULT 0.5,
    role_reason TEXT NOT NULL DEFAULT '',
    role_source TEXT NOT NULL DEFAULT 'legacy',
    classification_version TEXT NOT NULL DEFAULT 'legacy',
    original_relative_path TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY(calculation_id, original_relative_path),
    FOREIGN KEY(calculation_id) REFERENCES calculations(calculation_id) ON DELETE CASCADE,
    FOREIGN KEY(file_id) REFERENCES files(file_id)
);

CREATE INDEX IF NOT EXISTS idx_calc_files_type ON calculation_files(calculation_id, file_type);
CREATE INDEX IF NOT EXISTS idx_calc_material_type ON calculations(material_id, calc_type);

CREATE TABLE IF NOT EXISTS ingest_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    file_id TEXT,
    calculation_id TEXT,
    incoming_name TEXT,
    source_type TEXT,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(file_id) REFERENCES files(file_id),
    FOREIGN KEY(calculation_id) REFERENCES calculations(calculation_id)
);
"""


class CatalogRepository:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_schema(self) -> None:
        with closing(self._connect()) as conn:
            conn.executescript(SCHEMA)
            # Backward-compatible v0.6 migration for catalogs created by v0.4/v0.5.
            columns = {r[1] for r in conn.execute("PRAGMA table_info(calculation_files)").fetchall()}
            if "semantic_type" not in columns:
                conn.execute("ALTER TABLE calculation_files ADD COLUMN semantic_type TEXT NOT NULL DEFAULT 'unknown'")
            if "role_confidence" not in columns:
                conn.execute("ALTER TABLE calculation_files ADD COLUMN role_confidence REAL NOT NULL DEFAULT 0.5")
            if "role_reason" not in columns:
                conn.execute("ALTER TABLE calculation_files ADD COLUMN role_reason TEXT NOT NULL DEFAULT ''")
            if "role_source" not in columns:
                conn.execute("ALTER TABLE calculation_files ADD COLUMN role_source TEXT NOT NULL DEFAULT 'legacy'")
            if "classification_version" not in columns:
                conn.execute("ALTER TABLE calculation_files ADD COLUMN classification_version TEXT NOT NULL DEFAULT 'legacy'")
            conn.commit()

    @staticmethod
    def _dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    def get_file_by_sha(self, sha256: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            return self._dict(conn.execute("SELECT * FROM files WHERE sha256=?", (sha256,)).fetchone())

    def get_file(self, file_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            return self._dict(conn.execute("SELECT * FROM files WHERE file_id=?", (file_id,)).fetchone())

    def insert_file(self, record: dict[str, Any]) -> None:
        cols = list(record.keys())
        sql = f"INSERT INTO files ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})"
        with closing(self._connect()) as conn:
            conn.execute(sql, tuple(record[c] for c in cols))
            conn.commit()

    def log_event(self, event_type: str, *, file_id: str | None = None, calculation_id: str | None = None,
                  incoming_name: str | None = None, source_type: str | None = None,
                  details: dict[str, Any] | None = None) -> str:
        event_id = new_id("evt")
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT INTO ingest_events VALUES (?,?,?,?,?,?,?,?)",
                (event_id, event_type, file_id, calculation_id, incoming_name, source_type,
                 json_dumps(details or {}), utc_now()),
            )
            conn.commit()
        return event_id

    def get_or_create_material(self, formula: str, normalized_formula: str, metadata: dict[str, Any] | None = None) -> str:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT material_id FROM materials WHERE normalized_formula=?", (normalized_formula,)).fetchone()
            if row:
                return str(row[0])
            material_id = new_id("mat")
            conn.execute(
                "INSERT INTO materials VALUES (?,?,?,?,?)",
                (material_id, formula, normalized_formula, json_dumps(metadata or {}), utc_now()),
            )
            conn.commit()
            return material_id

    def insert_structure(self, *, material_id: str | None, source_file_id: str | None,
                         formula: str | None, atom_count: int | None, metadata: dict[str, Any]) -> str:
        structure_id = new_id("str")
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT INTO structures VALUES (?,?,?,?,?,?,?)",
                (structure_id, material_id, source_file_id, formula, atom_count, json_dumps(metadata), utc_now()),
            )
            conn.commit()
        return structure_id

    def get_calculation_by_fingerprint(self, fingerprint: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            return self._dict(conn.execute("SELECT * FROM calculations WHERE fingerprint=?", (fingerprint,)).fetchone())

    def create_calculation(self, *, material_id: str | None, structure_id: str | None, calc_type: str,
                           functional: str | None, soc: bool | None, status: str, source_path: str,
                           fingerprint: str, metadata: dict[str, Any]) -> str:
        calculation_id = new_id("calc")
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT INTO calculations VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (calculation_id, material_id, structure_id, calc_type, functional,
                 None if soc is None else int(soc), status, source_path, fingerprint,
                 json_dumps(metadata), utc_now()),
            )
            conn.commit()
        return calculation_id

    def link_calculation_file(self, *, calculation_id: str, file_id: str, file_type: str,
                              role: str, semantic_type: str = "unknown", retention_class: str,
                              original_relative_path: str, metadata: dict[str, Any] | None = None,
                              role_confidence: float = 0.5, role_reason: str = "",
                              role_source: str = "legacy", classification_version: str = "legacy") -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO calculation_files
                (calculation_id,file_id,file_type,role,semantic_type,retention_class,
                 role_confidence,role_reason,role_source,classification_version,
                 original_relative_path,metadata_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (calculation_id, file_id, file_type, role, semantic_type, retention_class,
                 float(role_confidence), role_reason, role_source, classification_version,
                 original_relative_path, json_dumps(metadata or {})),
            )
            conn.commit()

    def update_calculation_file_semantics(
        self,
        calculation_id: str,
        original_relative_path: str,
        *,
        role: str,
        semantic_type: str,
        retention_class: str,
        role_confidence: float = 0.5,
        role_reason: str = "",
        role_source: str = "legacy",
        classification_version: str = "legacy",
        preserve_user_override: bool = True,
    ) -> bool:
        """Refresh logical classification without touching the stored object.

        Returns True when a row was updated.  A manual user override is protected
        from future automatic reclassification unless preserve_user_override=False.
        """
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT role_source FROM calculation_files WHERE calculation_id=? AND original_relative_path=?",
                (calculation_id, original_relative_path),
            ).fetchone()
            if row is None:
                return False
            if preserve_user_override and row[0] == "user_override":
                return False
            conn.execute(
                """
                UPDATE calculation_files
                SET role=?, semantic_type=?, retention_class=?, role_confidence=?,
                    role_reason=?, role_source=?, classification_version=?
                WHERE calculation_id=? AND original_relative_path=?
                """,
                (role, semantic_type, retention_class, float(role_confidence), role_reason,
                 role_source, classification_version, calculation_id, original_relative_path),
            )
            conn.commit()
            return True

    def set_calculation_file_override(
        self, calculation_id: str, original_relative_path: str, *,
        role: str, semantic_type: str | None = None, reason: str = "manual correction",
    ) -> None:
        """Persist a human correction. Automatic re-import will not overwrite it."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT semantic_type FROM calculation_files WHERE calculation_id=? AND original_relative_path=?",
                (calculation_id, original_relative_path),
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown calculation file: {calculation_id} / {original_relative_path}")
            semantic = semantic_type or str(row[0])
            conn.execute(
                """
                UPDATE calculation_files
                SET role=?, semantic_type=?, role_confidence=1.0, role_reason=?,
                    role_source='user_override', classification_version='user'
                WHERE calculation_id=? AND original_relative_path=?
                """,
                (role, semantic, reason, calculation_id, original_relative_path),
            )
            conn.commit()

    def clear_calculation_file_override(self, calculation_id: str, original_relative_path: str) -> None:
        """Mark an override as cleared so the next re-import may classify it again."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT 1 FROM calculation_files WHERE calculation_id=? AND original_relative_path=?",
                (calculation_id, original_relative_path),
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown calculation file: {calculation_id} / {original_relative_path}")
            conn.execute(
                """UPDATE calculation_files
                   SET role_source='override_cleared', role_confidence=0.0,
                       role_reason='manual override cleared; re-import to reclassify',
                       classification_version='pending'
                   WHERE calculation_id=? AND original_relative_path=?""",
                (calculation_id, original_relative_path),
            )
            conn.commit()

    def update_calculation_inference(
        self, calculation_id: str, *, calc_type: str, functional: str | None,
        soc: bool | None, workflow: str, evidence: list[str], classification_version: str,
    ) -> None:
        """Refresh calculation-level inference on duplicate re-import.

        This lets newer workflow rules repair legacy `unknown` Calculation rows
        without creating a duplicate Calculation or touching SHA256 objects.
        """
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT metadata_json FROM calculations WHERE calculation_id=?",
                (calculation_id,),
            ).fetchone()
            if row is None:
                raise KeyError(calculation_id)
            try:
                metadata = json.loads(row[0] or '{}')
                if not isinstance(metadata, dict):
                    metadata = {}
            except Exception:
                metadata = {}
            metadata['classification_context'] = {
                'workflow': workflow,
                'evidence': list(evidence),
                'classification_version': classification_version,
            }
            conn.execute(
                """UPDATE calculations
                   SET calc_type=?, functional=?, soc=?, metadata_json=?
                   WHERE calculation_id=?""",
                (calc_type, functional, None if soc is None else int(soc),
                 json_dumps(metadata), calculation_id),
            )
            conn.commit()

    def update_calculation_source_path(self, calculation_id: str, source_path: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute("UPDATE calculations SET source_path=? WHERE calculation_id=?", (source_path, calculation_id))
            conn.commit()

    def list_calculations(self) -> list[dict[str, Any]]:
        sql = """
        SELECT c.*, m.formula AS material_formula,
               (SELECT COUNT(*) FROM calculation_files cf WHERE cf.calculation_id=c.calculation_id) AS file_count
        FROM calculations c LEFT JOIN materials m ON c.material_id=m.material_id
        ORDER BY c.created_at DESC
        """
        with closing(self._connect()) as conn:
            return [dict(r) for r in conn.execute(sql).fetchall()]

    def get_calculation(self, calculation_id: str) -> dict[str, Any] | None:
        sql = """
        SELECT c.*, m.formula AS material_formula
        FROM calculations c LEFT JOIN materials m ON c.material_id=m.material_id
        WHERE c.calculation_id=?
        """
        with closing(self._connect()) as conn:
            return self._dict(conn.execute(sql, (calculation_id,)).fetchone())

    def list_calculation_files(self, calculation_id: str) -> list[dict[str, Any]]:
        """Return logical Calculation files with source-name fidelity.

        `files.original_name` belongs to the content-addressed object and can reflect
        the *first* name under which identical bytes were seen.  For a Calculation,
        the authoritative name is instead the basename of `original_relative_path`.
        v0.6.2.5 therefore exposes that exact source spelling as `original_name` and
        keeps the object-level name separately as `object_original_name`.
        """
        sql = """
        SELECT cf.calculation_id, cf.file_type, cf.role, cf.semantic_type, cf.retention_class,
               cf.role_confidence, cf.role_reason, cf.role_source, cf.classification_version,
               cf.original_relative_path, cf.metadata_json,
               f.file_id, f.sha256, f.original_name AS object_original_name, f.stored_path, f.category,
               f.subcategory, f.size_bytes
        FROM calculation_files cf JOIN files f ON f.file_id=cf.file_id
        WHERE cf.calculation_id=?
        ORDER BY CASE cf.role
                   WHEN 'input' THEN 0
                   WHEN 'reference' THEN 1
                   WHEN 'intermediate' THEN 2
                   WHEN 'output' THEN 3
                   WHEN 'auxiliary' THEN 4
                   ELSE 5 END,
                 cf.original_relative_path
        """
        with closing(self._connect()) as conn:
            rows = [dict(r) for r in conn.execute(sql, (calculation_id,)).fetchall()]
        for row in rows:
            source_name = Path(row['original_relative_path']).name
            row['original_name'] = source_name
            row['display_name'] = source_name
            # file_type is a logical Calculation field and should mirror the actual
            # source basename, not a normalized lookup key.
            row['file_type'] = source_name
        return rows

    def repair_calculation_file_name_case(self, calculation_id: str, actual_relative_path: str) -> bool:
        """Repair legacy lower-cased logical names from the real source path.

        Matching is case-insensitive only to locate the legacy row. The values
        written back preserve the exact spelling supplied by the source filesystem.
        Returns True when a row changed.
        """
        actual = Path(actual_relative_path).as_posix()
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT original_relative_path, file_type FROM calculation_files WHERE calculation_id=?",
                (calculation_id,),
            ).fetchall()
            match = None
            for row in rows:
                if Path(str(row[0])).as_posix().casefold() == actual.casefold():
                    match = row
                    break
            if match is None:
                return False
            old_path = str(match[0])
            expected_type = Path(actual).name
            if old_path == actual and str(match[1]) == expected_type:
                return False
            conn.execute(
                """UPDATE calculation_files
                   SET original_relative_path=?, file_type=?
                   WHERE calculation_id=? AND original_relative_path=?""",
                (actual, expected_type, calculation_id, old_path),
            )
            conn.commit()
            return True

    def get_calculation_file(self, calculation_id: str, file_type: str) -> dict[str, Any] | None:
        rows = self.list_calculation_files(calculation_id)
        matches = [r for r in rows if r['file_type'].upper() == file_type.upper()]
        if not matches:
            return None
        # Prefer top-level file if duplicates exist in nested directories.
        matches.sort(key=lambda r: (Path(r['original_relative_path']).parts.__len__(), r['original_relative_path']))
        return matches[0]

    def get_calculation_file_by_path(self, calculation_id: str, original_relative_path: str) -> dict[str, Any] | None:
        wanted = Path(original_relative_path).as_posix()
        rows = self.list_calculation_files(calculation_id)
        for row in rows:
            if Path(row['original_relative_path']).as_posix() == wanted:
                return row
        # Query matching may be case-insensitive, but the returned path/name always
        # preserves the source spelling stored in the catalog.
        folded = wanted.casefold()
        for row in rows:
            if Path(row['original_relative_path']).as_posix().casefold() == folded:
                return row
        return None

    def list_materials(self) -> list[dict[str, Any]]:
        sql = """
        SELECT m.*,
               (SELECT COUNT(*) FROM structures s WHERE s.material_id=m.material_id) AS structure_count,
               (SELECT COUNT(*) FROM calculations c WHERE c.material_id=m.material_id) AS calculation_count
        FROM materials m
        ORDER BY m.normalized_formula COLLATE NOCASE
        """
        with closing(self._connect()) as conn:
            return [dict(r) for r in conn.execute(sql).fetchall()]

    def find_material(self, formula: str) -> dict[str, Any] | None:
        normalized = "".join(str(formula).split())
        with closing(self._connect()) as conn:
            return self._dict(
                conn.execute(
                    "SELECT * FROM materials WHERE normalized_formula=? COLLATE NOCASE OR formula=? COLLATE NOCASE LIMIT 1",
                    (normalized, formula),
                ).fetchone()
            )

    def search_calculations(
        self,
        *,
        material_formula: str | None = None,
        calc_type: str | None = None,
        functional: str | None = None,
        status: str | None = None,
        soc: bool | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if material_formula:
            normalized = "".join(str(material_formula).split())
            where.append("(m.normalized_formula=? COLLATE NOCASE OR m.formula=? COLLATE NOCASE)")
            params.extend([normalized, material_formula])
        if calc_type:
            where.append("c.calc_type=? COLLATE NOCASE")
            params.append(calc_type)
        if functional:
            where.append("c.functional=? COLLATE NOCASE")
            params.append(functional)
        if status:
            where.append("c.status=? COLLATE NOCASE")
            params.append(status)
        if soc is not None:
            where.append("c.soc=?")
            params.append(int(soc))
        clause = " WHERE " + " AND ".join(where) if where else ""
        safe_limit = max(1, min(int(limit), 1000))
        sql = f"""
        SELECT c.*, m.formula AS material_formula,
               (SELECT COUNT(*) FROM calculation_files cf WHERE cf.calculation_id=c.calculation_id) AS file_count
        FROM calculations c
        LEFT JOIN materials m ON c.material_id=m.material_id
        {clause}
        ORDER BY c.created_at DESC
        LIMIT ?
        """
        params.append(safe_limit)
        with closing(self._connect()) as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def get_latest_calculation(
        self,
        *,
        material_formula: str,
        calc_type: str | None = None,
        functional: str | None = None,
        status: str | None = None,
        soc: bool | None = None,
    ) -> dict[str, Any] | None:
        rows = self.search_calculations(
            material_formula=material_formula,
            calc_type=calc_type,
            functional=functional,
            status=status,
            soc=soc,
            limit=1,
        )
        return rows[0] if rows else None

    def count_events(self, event_type: str | None = None) -> int:
        with closing(self._connect()) as conn:
            if event_type:
                return int(conn.execute("SELECT COUNT(*) FROM ingest_events WHERE event_type=?", (event_type,)).fetchone()[0])
            return int(conn.execute("SELECT COUNT(*) FROM ingest_events").fetchone()[0])
