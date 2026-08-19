import tempfile
import unittest
import sqlite3
from contextlib import closing
from pathlib import Path

from material_agent.app import build_services
from material_agent.auto_intake import AutoIngestService
from common import write_vasp_folder


class AutoIntakeTests(unittest.TestCase):
    def _services(self, root: Path):
        settings, repo, storage, ingestion, calcs = build_services(root)
        return settings, repo, AutoIngestService(repo, ingestion, calcs)

    def test_inspect_realistic_vasp_folder_keeps_io_logical(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = write_vasp_folder(base / 'calc', optics=True, extra=True)
            _, _, auto = self._services(base / 'data')
            plan = auto.inspect_path(folder)
            self.assertEqual(plan['kind'], 'vasp_calculation')
            self.assertEqual(plan['formula'], 'SiS2')
            by_name = {r['file_type']: r for r in plan['files']}
            self.assertEqual(by_name['INCAR']['role'], 'input')
            self.assertEqual(by_name['INCAR']['semantic_type'], 'parameters')
            self.assertEqual(by_name['OUTCAR']['role'], 'output')
            self.assertEqual(by_name['OUTCAR']['semantic_type'], 'main_output')
            self.assertEqual(by_name['CONTCAR']['semantic_type'], 'structure')

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = write_vasp_folder(base / 'calc', optics=False, extra=False)
            _, repo, auto = self._services(base / 'data')
            result = auto.ingest_path(folder, dry_run=True)
            self.assertEqual(result['status'], 'dry_run')
            self.assertFalse(result['written'])
            self.assertEqual(repo.list_calculations(), [])

    def test_auto_ingest_vasp_uses_calculation_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = write_vasp_folder(base / 'calc', optics=True, extra=True)
            _, repo, auto = self._services(base / 'data')
            result = auto.ingest_path(folder)
            self.assertEqual(result['kind'], 'vasp_calculation')
            self.assertEqual(result['status'], 'imported')
            rows = repo.list_calculation_files(result['calculation_id'])
            by_name = {r['file_type']: r for r in rows}
            self.assertEqual(by_name['INCAR']['role'], 'input')
            self.assertEqual(by_name['INCAR']['semantic_type'], 'parameters')
            self.assertEqual(by_name['OUTCAR']['role'], 'output')
            self.assertEqual(by_name['OUTCAR']['semantic_type'], 'main_output')

    def test_auto_ingest_plain_file_uses_file_ingestion(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            file = base / 'paper.pdf'
            file.write_bytes(b'%PDF-demo')
            _, _, auto = self._services(base / 'data')
            result = auto.ingest_path(file)
            self.assertEqual(result['kind'], 'file')
            self.assertEqual(result['status'], 'stored')

    def test_inbox_treats_vasp_folder_as_one_unit_and_moves_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            inbox = base / 'INBOX'
            folder = write_vasp_folder(inbox / 'SiS2_static', optics=False, extra=False)
            settings, repo, auto = self._services(base / 'data')
            result = auto.ingest_inbox(
                inbox,
                processed_root=settings.data_root / 'staging' / 'processed',
                failed_root=settings.data_root / 'staging' / 'failed',
            )
            self.assertEqual(result['imported_calculations'], 1)
            self.assertEqual(len(repo.list_calculations()), 1)
            self.assertFalse(folder.exists())
            detail = result['details'][0]
            self.assertTrue(Path(detail['archived_to']).is_dir())
            calc = repo.get_calculation(detail['calculation_id'])
            self.assertEqual(Path(calc['source_path']), Path(detail['archived_to']))

    def test_unknown_directory_is_not_destroyed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            inbox = base / 'INBOX'
            unknown = inbox / 'project_notes'
            unknown.mkdir(parents=True)
            (unknown / 'note.foo').write_text('x', encoding='utf-8')
            settings, repo, auto = self._services(base / 'data')
            result = auto.ingest_inbox(
                inbox,
                processed_root=settings.data_root / 'staging' / 'processed',
                failed_root=settings.data_root / 'staging' / 'failed',
            )
            self.assertEqual(result['skipped'], 1)
            self.assertTrue(unknown.exists())
            self.assertEqual(repo.list_calculations(), [])

    def test_vaspkit_semantics_recognize_kpath_and_band_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = write_vasp_folder(base / 'HSEband', optics=False, extra=False)
            (folder / 'KPATH.in').write_text('20\nLine-mode path\n', encoding='utf-8')
            (folder / 'BAND.dat').write_text('band data\n', encoding='utf-8')
            (folder / 'BAND_GAP').write_text('1.23 eV\n', encoding='utf-8')
            (folder / 'FERMI_ENERGY').write_text('0.50 eV\n', encoding='utf-8')
            (folder / 'KLABELS').write_text('G M K G\n', encoding='utf-8')
            _, repo, auto = self._services(base / 'data')

            plan = auto.inspect_path(folder)
            by_name = {r['file_type']: r for r in plan['files']}
            self.assertEqual(by_name['KPATH.in']['role'], 'input')
            self.assertEqual(by_name['KPATH.in']['semantic_type'], 'band_kpath')
            self.assertEqual(by_name['BAND.dat']['role'], 'output')
            self.assertEqual(by_name['BAND.dat']['semantic_type'], 'band_structure_data')
            self.assertEqual(by_name['BAND_GAP']['role'], 'output')
            self.assertEqual(by_name['BAND_GAP']['semantic_type'], 'band_gap_result')
            self.assertEqual(by_name['FERMI_ENERGY']['semantic_type'], 'fermi_energy')
            self.assertEqual(by_name['KLABELS']['semantic_type'], 'kpoint_labels')

            result = auto.ingest_path(folder)
            rows = repo.list_calculation_files(result['calculation_id'])
            db_by_name = {r['file_type']: r for r in rows}
            self.assertEqual(db_by_name['KPATH.in']['role'], 'input')
            self.assertEqual(db_by_name['KPATH.in']['semantic_type'], 'band_kpath')

    def test_duplicate_reimport_refreshes_old_semantic_classification(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = write_vasp_folder(base / 'HSEband', optics=False, extra=False)
            (folder / 'KPATH.in').write_text('band path\n', encoding='utf-8')
            _, repo, auto = self._services(base / 'data')

            first = auto.ingest_path(folder)
            calc_id = first['calculation_id']

            # Simulate the same row as it existed after v0.6.0: preserved file,
            # but no knowledge that KPATH.in is an input.
            with closing(sqlite3.connect(repo.db_path)) as conn:
                conn.execute(
                    "UPDATE calculation_files SET role='auxiliary', semantic_type='unknown' "
                    "WHERE calculation_id=? AND original_relative_path='KPATH.in'",
                    (calc_id,),
                )
                conn.commit()

            old = repo.get_calculation_file(calc_id, 'KPATH.in')
            self.assertEqual(old['role'], 'auxiliary')
            self.assertEqual(old['semantic_type'], 'unknown')

            second = auto.ingest_path(folder)
            self.assertEqual(second['status'], 'duplicate_calculation')
            self.assertEqual(second['calculation_id'], calc_id)
            refreshed = repo.get_calculation_file(calc_id, 'KPATH.in')
            self.assertEqual(refreshed['role'], 'input')
            self.assertEqual(refreshed['semantic_type'], 'band_kpath')

    def test_nested_project_is_detected_as_vasp_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / 'Zr2CO2'
            write_vasp_folder(project / 'HSEband', optics=False, extra=False, variant='A')
            write_vasp_folder(project / 'elastic' / 'xx', optics=False, extra=False, variant='B')
            (project / 'Zr2CO2.cif').write_text('structure', encoding='utf-8')
            _, _, auto = self._services(base / 'data')

            plan = auto.inspect_path(project)
            self.assertEqual(plan['kind'], 'vasp_collection')
            self.assertEqual(plan['calculations_found'], 2)
            rels = {row['relative_path'] for row in plan['calculations']}
            self.assertEqual(rels, {'HSEband', 'elastic/xx'})

    def test_collection_ingest_imports_each_nested_calculation(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / 'Zr2CO2'
            write_vasp_folder(project / 'HSEband', optics=False, extra=False, variant='A')
            write_vasp_folder(project / 'guang' / 'optics_run', optics=True, extra=False, variant='B')
            _, repo, auto = self._services(base / 'data')

            dry = auto.ingest_path(project, dry_run=True)
            self.assertEqual(dry['plan']['kind'], 'vasp_collection')
            self.assertEqual(repo.list_calculations(), [])

            result = auto.ingest_path(project)
            self.assertEqual(result['kind'], 'vasp_collection')
            self.assertEqual(result['status'], 'imported_collection')
            self.assertEqual(result['imported_calculations'], 2)
            self.assertEqual(result['failed'], 0)
            self.assertEqual(len(repo.list_calculations()), 2)

    def test_parent_calculation_does_not_swallow_nested_calculation(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            parent = write_vasp_folder(base / 'project' / 'relax', optics=False, extra=False, variant='A')
            child = write_vasp_folder(parent / 'band', optics=False, extra=False, variant='B')
            (child / 'KPATH.in').write_text('band path\n', encoding='utf-8')
            _, repo, auto = self._services(base / 'data')

            # Directly importing the parent must stop at the nested Calculation boundary.
            result = auto.ingest_path(parent)
            parent_rows = repo.list_calculation_files(result['calculation_id'])
            parent_paths = {r['original_relative_path'] for r in parent_rows}
            self.assertIn('INCAR', parent_paths)
            self.assertNotIn('band/INCAR', parent_paths)
            self.assertNotIn('band/KPATH.in', parent_paths)

            # The surrounding project can still discover both calculations independently.
            plan = auto.inspect_path(base / 'project')
            self.assertEqual(plan['kind'], 'vasp_collection')
            rels = {row['relative_path'] for row in plan['calculations']}
            self.assertEqual(rels, {'relax', 'relax/band'})


if __name__ == '__main__':
    unittest.main()
