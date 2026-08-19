import sqlite3
import tempfile
import unittest
from pathlib import Path

from material_agent.repository import CatalogRepository


class SchemaMigrationTests(unittest.TestCase):
    def test_v05_calculation_files_table_gets_semantic_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'catalog.db'
            conn = sqlite3.connect(db)
            conn.execute('''
                CREATE TABLE calculation_files (
                    calculation_id TEXT NOT NULL,
                    file_id TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    role TEXT NOT NULL,
                    retention_class TEXT NOT NULL,
                    original_relative_path TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY(calculation_id, original_relative_path)
                )
            ''')
            conn.commit()
            conn.close()
            CatalogRepository(db)
            conn = sqlite3.connect(db)
            cols = {r[1] for r in conn.execute('PRAGMA table_info(calculation_files)').fetchall()}
            conn.close()
            self.assertIn('semantic_type', cols)


if __name__ == '__main__':
    unittest.main()
