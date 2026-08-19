import io
import tempfile
import unittest
from pathlib import Path

from material_agent.app import build_services


class IngestionTests(unittest.TestCase):
    def test_same_name_different_content_is_not_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)/'data'
            _, repo, _, ingestion, _ = build_services(data)
            a = ingestion.ingest_stream(io.BytesIO(b'ENCUT=400\n'), filename='INCAR')
            b = ingestion.ingest_stream(io.BytesIO(b'ENCUT=520\n'), filename='INCAR')
            self.assertNotEqual(a.file_id, b.file_id)
            self.assertNotEqual(a.sha256, b.sha256)

    def test_different_name_same_content_is_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, repo, _, ingestion, _ = build_services(Path(tmp)/'data')
            a = ingestion.ingest_stream(io.BytesIO(b'same'), filename='A.cif')
            b = ingestion.ingest_stream(io.BytesIO(b'same'), filename='B.cif')
            self.assertEqual(a.file_id, b.file_id)
            self.assertTrue(b.duplicate)
            self.assertEqual(repo.count_events('duplicate_detected'), 1)

    def test_stream_api_for_future_web_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, ingestion, _ = build_services(Path(tmp)/'data')
            r = ingestion.ingest_stream(io.BytesIO(b'hello'), filename='upload.txt', source_type='web_upload')
            self.assertTrue(Path(r.stored_path).exists())
            self.assertEqual(r.source_type, 'web_upload')
