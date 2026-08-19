import tempfile
import unittest
from pathlib import Path
from material_agent.app import build_services


class StorageTests(unittest.TestCase):
    def test_object_path_is_content_addressed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            f = base/'x.txt'; f.write_text('abc', encoding='utf-8')
            settings, _, _, ingestion, _ = build_services(base/'data')
            r = ingestion.ingest_file(f)
            p = Path(r.stored_path)
            self.assertEqual(p.name, r.sha256)
            self.assertEqual(p.parent.name, r.sha256[:2])
