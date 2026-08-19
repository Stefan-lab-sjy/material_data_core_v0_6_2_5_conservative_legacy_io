from __future__ import annotations

from pathlib import Path
import hashlib
import mimetypes
import os
from typing import BinaryIO, Any

from .classifier import classify_path
from .models import IngestResult
from .repository import CatalogRepository
from .storage import LocalObjectStorage
from .utils import utc_now, new_id, json_dumps


class IngestionService:
    """Single ingestion gateway used by CLI, future web upload, crawler and agents."""

    def __init__(self, repository: CatalogRepository, storage: LocalObjectStorage):
        self.repository = repository
        self.storage = storage

    def ingest_file(self, path: str | Path, *, source_type: str = "manual_upload",
                    source_uri: str | None = None, metadata: dict[str, Any] | None = None) -> IngestResult:
        path = Path(path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        if not path.is_file():
            raise ValueError(f"Not a file: {path}")
        with path.open('rb') as stream:
            return self.ingest_stream(
                stream, filename=path.name, source_type=source_type,
                source_uri=source_uri or str(path), metadata=metadata,
            )

    def ingest_stream(self, stream: BinaryIO, *, filename: str, source_type: str = "web_upload",
                      source_uri: str | None = None, metadata: dict[str, Any] | None = None) -> IngestResult:
        """Web-ready stream API: accepts any binary file-like object without requiring a fixed INBOX path."""
        temp = self.storage.new_temp_path()
        h = hashlib.sha256()
        size = 0
        try:
            with temp.open('wb') as out:
                while True:
                    chunk = stream.read(8 * 1024 * 1024)
                    if not chunk:
                        break
                    h.update(chunk)
                    out.write(chunk)
                    size += len(chunk)
                out.flush()
                os.fsync(out.fileno())
            digest = h.hexdigest()
            existing = self.repository.get_file_by_sha(digest)
            pseudo_path = Path(filename)
            category, subcategory = classify_path(pseudo_path)
            if existing:
                temp.unlink(missing_ok=True)
                self.repository.log_event(
                    "duplicate_detected", file_id=existing['file_id'], incoming_name=filename,
                    source_type=source_type, details={"source_uri": source_uri},
                )
                return IngestResult(
                    status="duplicate", file_id=existing['file_id'], sha256=digest,
                    original_name=filename, stored_path=existing['stored_path'],
                    category=existing['category'], subcategory=existing['subcategory'],
                    size_bytes=int(existing['size_bytes']), source_type=source_type, duplicate=True,
                )

            stored_path, created = self.storage.commit_temp(temp, digest)
            now = utc_now()
            file_id = new_id("file")
            mime_type = mimetypes.guess_type(filename)[0]
            record = {
                "file_id": file_id,
                "sha256": digest,
                "original_name": filename,
                "extension": pseudo_path.suffix.lower(),
                "mime_type": mime_type,
                "size_bytes": size,
                "category": category,
                "subcategory": subcategory,
                "stored_path": str(stored_path),
                "source_type": source_type,
                "source_uri": source_uri,
                "status": "stored",
                "parser_status": "pending",
                "metadata_json": json_dumps(metadata or {}),
                "created_at": now,
                "updated_at": now,
            }
            try:
                self.repository.insert_file(record)
            except Exception:
                # If the DB write failed after a new object was committed, remove only the object we created.
                if created:
                    stored_path.unlink(missing_ok=True)
                raise
            self.repository.log_event(
                "file_stored", file_id=file_id, incoming_name=filename, source_type=source_type,
                details={"source_uri": source_uri},
            )
            return IngestResult(
                status="stored", file_id=file_id, sha256=digest, original_name=filename,
                stored_path=str(stored_path), category=category, subcategory=subcategory,
                size_bytes=size, source_type=source_type, duplicate=False,
            )
        finally:
            temp.unlink(missing_ok=True)
