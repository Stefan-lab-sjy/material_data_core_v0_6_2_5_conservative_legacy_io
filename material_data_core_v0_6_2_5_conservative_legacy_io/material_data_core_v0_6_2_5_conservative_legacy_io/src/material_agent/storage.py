from __future__ import annotations

from pathlib import Path
import os
import shutil
import tempfile


class LocalObjectStorage:
    def __init__(self, objects_root: Path, temp_root: Path):
        self.objects_root = Path(objects_root)
        self.temp_root = Path(temp_root)
        self.objects_root.mkdir(parents=True, exist_ok=True)
        self.temp_root.mkdir(parents=True, exist_ok=True)

    def object_path(self, sha256: str) -> Path:
        return self.objects_root / sha256[:2] / sha256

    def commit_temp(self, temp_path: Path, sha256: str) -> tuple[Path, bool]:
        target = self.object_path(sha256)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            temp_path.unlink(missing_ok=True)
            return target, False
        # Atomic replace on the same filesystem. temp_root lives under data_root by default.
        try:
            os.replace(temp_path, target)
        except OSError:
            # Cross-device fallback for custom temp roots.
            with temp_path.open('rb') as src, target.open('xb') as dst:
                shutil.copyfileobj(src, dst, length=8 * 1024 * 1024)
            temp_path.unlink(missing_ok=True)
        return target, True

    def new_temp_path(self) -> Path:
        fd, name = tempfile.mkstemp(prefix='ingest_', dir=self.temp_root)
        os.close(fd)
        return Path(name)
