import tempfile
import unittest
from pathlib import Path

from material_agent.app import build_services
from common import write_vasp_folder


class CalculationTests(unittest.TestCase):
    def test_complete_folder_ingest_includes_unknown_auxiliary(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = write_vasp_folder(base/'calc', optics=True, extra=True)
            _, repo, _, _, calcs = build_services(base/'data')
            r = calcs.import_vasp_folder(folder)
            rows = repo.list_calculation_files(r.calculation_id)
            names = {x['file_type'] for x in rows}
            self.assertIn('REPORT', names)
            self.assertIn('WAVEDER', names)
            self.assertEqual(r.discovered_files, len(rows))
            self.assertGreaterEqual(r.auxiliary_files, 1)

    def test_static_and_optics_incar_are_distinct_but_poscar_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            static = write_vasp_folder(base/'static', optics=False, extra=False)
            optics = write_vasp_folder(base/'optics', optics=True, extra=False)
            _, repo, _, _, calcs = build_services(base/'data')
            a = calcs.import_vasp_folder(static)
            b = calcs.import_vasp_folder(optics)
            ia = repo.get_calculation_file(a.calculation_id, 'INCAR')
            ib = repo.get_calculation_file(b.calculation_id, 'INCAR')
            pa = repo.get_calculation_file(a.calculation_id, 'POSCAR')
            pb = repo.get_calculation_file(b.calculation_id, 'POSCAR')
            self.assertNotEqual(ia['sha256'], ib['sha256'])
            self.assertNotEqual(ia['file_id'], ib['file_id'])
            self.assertEqual(pa['sha256'], pb['sha256'])
            self.assertEqual(pa['file_id'], pb['file_id'])
            self.assertEqual(a.calc_type, 'static')
            self.assertEqual(b.calc_type, 'optics')

    def test_compare_calculations_reports_differences(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            a_folder = write_vasp_folder(base/'a', optics=False, extra=False)
            b_folder = write_vasp_folder(base/'b', optics=True, extra=False)
            _, _, _, _, calcs = build_services(base/'data')
            a = calcs.import_vasp_folder(a_folder)
            b = calcs.import_vasp_folder(b_folder)
            rows = calcs.compare_calculations(a.calculation_id, b.calculation_id)
            by_path = {r['path']: r for r in rows}
            self.assertFalse(by_path['INCAR']['same'])
            self.assertTrue(by_path['POSCAR']['same'])

    def test_reimport_same_calculation_returns_existing_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = write_vasp_folder(base/'calc', optics=True)
            _, repo, _, _, calcs = build_services(base/'data')
            a = calcs.import_vasp_folder(folder)
            b = calcs.import_vasp_folder(folder)
            self.assertEqual(a.calculation_id, b.calculation_id)
            self.assertEqual(b.status, 'duplicate_calculation')
            self.assertEqual(len(repo.list_calculations()), 1)

    def test_export_full_calculation_restores_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = write_vasp_folder(base/'calc', optics=True)
            _, _, _, _, calcs = build_services(base/'data')
            r = calcs.import_vasp_folder(folder)
            out = calcs.export_files(r.calculation_id, base/'export', inputs_only=False)
            self.assertTrue((out/'INCAR').exists())
            self.assertTrue((out/'REPORT').exists())
            self.assertEqual((out/'INCAR').read_bytes(), (folder/'INCAR').read_bytes())


class ComprehensiveVaspFileIdentityTests(unittest.TestCase):
    def test_all_major_vasp_outputs_are_content_addressed_not_filename_deduped(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            a_folder = write_vasp_folder(base/'static', optics=False, extra=True, variant='A')
            b_folder = write_vasp_folder(base/'optics', optics=True, extra=True, variant='B')
            _, repo, _, _, calcs = build_services(base/'data')
            a = calcs.import_vasp_folder(a_folder)
            b = calcs.import_vasp_folder(b_folder)

            # Same filename + different bytes MUST be distinct physical objects.
            different_names = [
                'INCAR', 'OUTCAR', 'OSZICAR', 'CONTCAR', 'DOSCAR', 'EIGENVAL',
                'PROCAR', 'CHGCAR', 'WAVECAR', 'XDATCAR', 'vasprun.xml',
                'REPORT', 'WAVEDER', 'CUSTOM_NOTE.foo',
            ]
            for name in different_names:
                with self.subTest(file=name):
                    ra = repo.get_calculation_file(a.calculation_id, name)
                    rb = repo.get_calculation_file(b.calculation_id, name)
                    self.assertIsNotNone(ra)
                    self.assertIsNotNone(rb)
                    self.assertNotEqual(ra['sha256'], rb['sha256'])
                    self.assertNotEqual(ra['file_id'], rb['file_id'])

            # Same bytes across calculations SHOULD reuse the object but keep two calculation links.
            for name in ['KPOINTS', 'POSCAR', 'POTCAR']:
                with self.subTest(file=name):
                    ra = repo.get_calculation_file(a.calculation_id, name)
                    rb = repo.get_calculation_file(b.calculation_id, name)
                    self.assertEqual(ra['sha256'], rb['sha256'])
                    self.assertEqual(ra['file_id'], rb['file_id'])

    def test_verify_calculation_checks_every_file_by_relative_path_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = write_vasp_folder(base/'calc', optics=True, extra=True, variant='A')
            _, _, _, _, calcs = build_services(base/'data')
            result = calcs.import_vasp_folder(folder)
            rows = calcs.verify_calculation_against_folder(result.calculation_id, folder)
            self.assertTrue(rows)
            self.assertTrue(all(r['status'] == 'MATCH' for r in rows))
            self.assertIn('OSZICAR', {r['file_type'] for r in rows})

            # Mutating only OSZICAR must be detected specifically as a hash mismatch.
            (folder/'OSZICAR').write_text('changed after import\n', encoding='utf-8')
            rows2 = calcs.verify_calculation_against_folder(result.calculation_id, folder)
            by_path = {r['path']: r for r in rows2}
            self.assertEqual(by_path['OSZICAR']['status'], 'HASH_MISMATCH')
            for path, row in by_path.items():
                if path != 'OSZICAR':
                    self.assertEqual(row['status'], 'MATCH')
