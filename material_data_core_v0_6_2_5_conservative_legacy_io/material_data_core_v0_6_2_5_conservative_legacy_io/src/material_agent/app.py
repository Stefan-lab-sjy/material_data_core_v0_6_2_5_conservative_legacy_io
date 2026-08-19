from __future__ import annotations

from pathlib import Path

from .config import Settings
from .repository import CatalogRepository
from .storage import LocalObjectStorage
from .ingestion import IngestionService
from .calculations import CalculationService


def build_services(data_root: str | Path | None = None):
    settings = Settings.load(data_root)
    settings.ensure_dirs()
    repo = CatalogRepository(settings.db_path)
    storage = LocalObjectStorage(settings.objects_root, settings.temp_root)
    ingestion = IngestionService(repo, storage)
    calculations = CalculationService(repo, ingestion)
    return settings, repo, storage, ingestion, calculations
