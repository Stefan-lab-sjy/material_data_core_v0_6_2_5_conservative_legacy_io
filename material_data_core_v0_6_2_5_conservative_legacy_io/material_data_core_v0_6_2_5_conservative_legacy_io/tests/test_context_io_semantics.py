import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from material_agent.app import build_services
from material_agent.classifier import calculation_file_rule
from material_agent.semantics import build_vasp_context, classify_calculation_file
from material_agent.parsers import parse_incar, parse_kpoints, infer_calculation
from common import write_vasp_folder


class ContextAwareSemanticsTests(unittest.TestCase):
    def _hse_band(self, root: Path) -> Path:
        folder = write_vasp_folder(root, optics=False, extra=False)
        (folder / 'INCAR').write_text(
            "ENCUT=450\nEDIFF=1E-6\nNSW=0\nIBRION=-1\nLHFCALC=.TRUE.\nHFSCREEN=0.2\n",
            encoding='utf-8',
        )
        (folder / 'KPATH.in').write_text('KPATH\n20\nLine-Mode\nReciprocal\n', encoding='utf-8')
        (folder / 'HIGH_SYMMETRY_POINTS').write_text('GAMMA 0 0 0\n', encoding='utf-8')
        (folder / 'BAND.dat').write_text('band\n', encoding='utf-8')
        (folder / 'BAND_GAP').write_text('gap\n', encoding='utf-8')
        (folder / 'KLINES.dat').write_text('lines\n', encoding='utf-8')
        (folder / 'KLABELS').write_text('labels\n', encoding='utf-8')
        return folder

    def test_context_free_high_symmetry_is_reference_not_fake_output(self):
        row = calculation_file_rule('HIGH_SYMMETRY_POINTS')
        self.assertEqual(row['semantic_type'], 'high_symmetry_points')
        self.assertEqual(row['role'], 'reference')

    def test_hse_band_context_makes_kpath_and_high_symmetry_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = self._hse_band(Path(tmp) / 'HSEband')
            paths = list(folder.iterdir())
            incar = parse_incar(folder / 'INCAR')
            kp = parse_kpoints(folder / 'KPOINTS')
            ctx = build_vasp_context(folder, paths=paths, incar_meta=incar, kpoints_meta=kp,
                                     inferred=infer_calculation(incar, kp))
            self.assertEqual(ctx.workflow, 'hse_band')
            kpath = classify_calculation_file('KPATH.in', ctx)
            hs = classify_calculation_file('HIGH_SYMMETRY_POINTS', ctx)
            self.assertEqual(kpath['role'], 'input')
            self.assertGreaterEqual(kpath['role_confidence'], 0.9)
            self.assertEqual(hs['role'], 'input')
            self.assertEqual(hs['semantic_type'], 'high_symmetry_points')
            self.assertEqual(hs['role_source'], 'context_rule')

    def test_band_postprocessing_outputs_remain_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = self._hse_band(Path(tmp) / 'HSEband')
            incar = parse_incar(folder / 'INCAR')
            kp = parse_kpoints(folder / 'KPOINTS')
            ctx = build_vasp_context(folder, paths=list(folder.iterdir()), incar_meta=incar,
                                     kpoints_meta=kp, inferred=infer_calculation(incar, kp))
            for name in ['BAND.dat', 'BAND_GAP', 'KLINES.dat', 'KLABELS']:
                with self.subTest(name=name):
                    self.assertEqual(classify_calculation_file(name, ctx)['role'], 'output')

    def test_explicit_vaspkit_in_files_are_inputs(self):
        for name in ['FERMI_ENERGY.in', 'TRANSMAT.in', 'KPOINTS_MAPPING_TABLE.in']:
            with self.subTest(name=name):
                row = calculation_file_rule(name)
                self.assertEqual(row['role'], 'input')

    def test_unknown_file_stays_unknown(self):
        row = calculation_file_rule('mystery.private')
        self.assertEqual(row['role'], 'unknown')
        self.assertEqual(row['semantic_type'], 'unknown')
        self.assertLess(row['role_confidence'], 0.5)

    def test_integration_persists_explanation_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = self._hse_band(base / 'HSEband')
            _, repo, _, _, calcs = build_services(base / 'data')
            result = calcs.import_vasp_folder(folder)
            hs = repo.get_calculation_file(result.calculation_id, 'HIGH_SYMMETRY_POINTS')
            self.assertEqual(hs['role'], 'input')
            self.assertEqual(hs['role_source'], 'context_rule')
            self.assertEqual(hs['classification_version'], '0.6.2.5')
            self.assertGreater(float(hs['role_confidence']), 0.8)
            self.assertIn('high-symmetry', hs['role_reason'])

    def test_manual_override_survives_duplicate_reimport(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = self._hse_band(base / 'HSEband')
            _, repo, _, _, calcs = build_services(base / 'data')
            first = calcs.import_vasp_folder(folder)
            repo.set_calculation_file_override(
                first.calculation_id, 'HIGH_SYMMETRY_POINTS',
                role='reference', reason='lab convention for this dataset',
            )
            again = calcs.import_vasp_folder(folder)
            self.assertEqual(again.status, 'duplicate_calculation')
            row = repo.get_calculation_file_by_path(first.calculation_id, 'HIGH_SYMMETRY_POINTS')
            self.assertEqual(row['role'], 'reference')
            self.assertEqual(row['role_source'], 'user_override')
            self.assertEqual(float(row['role_confidence']), 1.0)

    def test_icharg_11_does_not_promote_chgcar_without_prerun_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = write_vasp_folder(Path(tmp) / 'dos', optics=False, extra=False)
            (folder / 'INCAR').write_text('NSW=0\nIBRION=-1\nICHARG=11\nLORBIT=11\nNEDOS=2000\n', encoding='utf-8')
            incar = parse_incar(folder / 'INCAR')
            kp = parse_kpoints(folder / 'KPOINTS')
            ctx = build_vasp_context(folder, paths=list(folder.iterdir()), incar_meta=incar,
                                     kpoints_meta=kp, inferred=infer_calculation(incar, kp))
            self.assertEqual(ctx.workflow, 'dos')
            row = classify_calculation_file('CHGCAR', ctx)
            self.assertEqual(row['role'], 'output')
            self.assertEqual(row['role_source'], 'conservative_history_rule')
            self.assertIn('ICHARG=11', row['role_reason'])
            self.assertIn('pre-run input manifest', row['role_reason'])

    def test_istart_does_not_promote_wavecar_without_prerun_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = write_vasp_folder(Path(tmp) / 'restart_like', optics=False, extra=False)
            (folder / 'INCAR').write_text('NSW=0\nIBRION=-1\nISTART=1\n', encoding='utf-8')
            incar = parse_incar(folder / 'INCAR')
            kp = parse_kpoints(folder / 'KPOINTS')
            ctx = build_vasp_context(folder, paths=list(folder.iterdir()), incar_meta=incar,
                                     kpoints_meta=kp, inferred=infer_calculation(incar, kp))
            row = classify_calculation_file('WAVECAR', ctx)
            self.assertEqual(row['role'], 'output')
            self.assertEqual(row['role_source'], 'conservative_history_rule')
            self.assertIn('ISTART=1', row['role_reason'])
            self.assertIn('pre-run input manifest', row['role_reason'])

    def test_duplicate_reimport_repairs_old_restart_input_guesses_in_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = write_vasp_folder(base / 'restart_like', optics=False, extra=False)
            (folder / 'INCAR').write_text('NSW=0\nIBRION=-1\nISTART=1\nICHARG=1\n', encoding='utf-8')
            _, repo, _, _, calcs = build_services(base / 'data')
            first = calcs.import_vasp_folder(folder)

            # Simulate v0.6.2.4-era guesses already stored in a user's catalog.
            with closing(sqlite3.connect(repo.db_path)) as conn:
                conn.execute(
                    "UPDATE calculation_files SET role='input', role_source='context_rule', classification_version='0.6.2.4' "
                    "WHERE calculation_id=? AND original_relative_path IN ('CHGCAR','WAVECAR')",
                    (first.calculation_id,),
                )
                conn.commit()

            again = calcs.import_vasp_folder(folder)
            self.assertEqual(again.status, 'duplicate_calculation')
            self.assertEqual(again.calculation_id, first.calculation_id)
            self.assertEqual(repo.get_calculation_file(first.calculation_id, 'CHGCAR')['role'], 'output')
            self.assertEqual(repo.get_calculation_file(first.calculation_id, 'WAVECAR')['role'], 'output')
            self.assertEqual(
                repo.get_calculation_file(first.calculation_id, 'CHGCAR')['classification_version'],
                '0.6.2.5',
            )


class SchemaV062Tests(unittest.TestCase):
    def test_v061_catalog_gets_explanation_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            # Creating a current repository is enough to assert all migration targets
            # exist; v0.6.1 databases lack precisely these columns.
            _, repo, _, _, _ = build_services(base / 'data')
            with closing(sqlite3.connect(repo.db_path)) as conn:
                cols = {r[1] for r in conn.execute('PRAGMA table_info(calculation_files)').fetchall()}
            for col in ['role_confidence', 'role_reason', 'role_source', 'classification_version']:
                self.assertIn(col, cols)


if __name__ == '__main__':
    unittest.main()
