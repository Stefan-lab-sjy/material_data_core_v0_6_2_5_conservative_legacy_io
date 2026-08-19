from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os


LOCAL_CONFIG_NAME = "material_agent.local.json"


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def local_config_path(project_root: Path | None = None) -> Path:
    root = project_root or default_project_root()
    return root / LOCAL_CONFIG_NAME


def read_local_config(project_root: Path | None = None) -> dict:
    path = local_config_path(project_root)
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def write_local_data_root(data_root: str | Path, project_root: Path | None = None) -> Path:
    root = project_root or default_project_root()
    target = Path(data_root).expanduser().resolve()
    # Accept either the data folder itself or an older project root containing data/catalog.db.
    if not (target / "catalog.db").exists() and (target / "data" / "catalog.db").exists():
        target = target / "data"
    target.mkdir(parents=True, exist_ok=True)
    path = local_config_path(root)
    path.write_text(json.dumps({"data_root": str(target)}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def clear_local_data_root(project_root: Path | None = None) -> None:
    path = local_config_path(project_root)
    if path.exists():
        path.unlink()


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_root: Path
    objects_root: Path
    temp_root: Path
    exports_root: Path
    db_path: Path
    inbox_root: Path

    @classmethod
    def load(cls, data_root: str | Path | None = None) -> "Settings":
        project_root = default_project_root()
        local_cfg = read_local_config(project_root)
        configured = (
            data_root
            or os.environ.get("MATERIAL_AGENT_DATA_ROOT")
            or local_cfg.get("data_root")
        )
        data = Path(configured).expanduser().resolve() if configured else (project_root / "data")
        return cls(
            project_root=project_root,
            data_root=data,
            objects_root=data / "objects" / "sha256",
            temp_root=data / "temp",
            exports_root=data / "exports",
            db_path=data / "catalog.db",
            inbox_root=project_root / "INBOX",
        )

    def ensure_dirs(self) -> None:
        for p in (self.data_root, self.objects_root, self.temp_root, self.exports_root, self.inbox_root):
            p.mkdir(parents=True, exist_ok=True)
