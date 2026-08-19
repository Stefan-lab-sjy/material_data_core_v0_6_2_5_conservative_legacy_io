import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from material_agent.app import build_services
from material_agent.parsers import parse_incar, parse_kpoints, infer_calculation
from material_agent.semantics import build_vasp_context
from common import write_vasp_folder


class WorkflowInferenceV0622Tests(unittest.TestCase):
    def test_geometry_optimization_uses_incar_not_folder_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = write_vasp_folder(Path(tmp) / 'anything', optics=False, extra=False)
            (folder / 'INCAR').write_text(
                'ENCUT=450\nIBRION=2 ; NSW=120 ; ISIF=2 ; EDIFFG=-0.01\n',
                encoding='utf-8',
            )
            incar = parse_incar(folder / 'INCAR')
            kp = parse_kpoints(folder / 'KPOINTS')
            inferred = infer_calculation(incar, kp)
            ctx = build_vasp_context(folder, paths=list(folder.iterdir()), incar_meta=incar,
                                     kpoints_meta=kp, inferred=inferred)
            self.assertEqual(inferred['calc_type'], 'relax')
            self.assertEqual(ctx.workflow, 'geometry_optimization')
            self.assertIn('INCAR:NSW=120>0', ctx.evidence)


    def test_geometry_optimization_with_real_template_annotations(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = write_vasp_folder(Path(tmp) / 'opt', optics=False, extra=False)
            (folder / 'INCAR').write_text(
                'ISTART = 0        (Read existing wavefunction, if there)\n'
                'ICHARG = 2        (Non-self-consistent: copied template note)\n'
                'ENCUT = 400       (Cut-off energy for plane wave basis set, in eV)\n'
                'NSW = 100         (Max ionic steps)\n'
                'IBRION = 2        (Algorithm: 0-MD, 1-Quasi-New, 2-CG)\n'
                'ISIF = 2          (Stress/relaxation: ions)\n'
                'EDIFFG = -2E-02   (Ionic convergence, eV/AA)\n',
                encoding='utf-8',
            )
            incar = parse_incar(folder / 'INCAR')
            kp = parse_kpoints(folder / 'KPOINTS')
            inferred = infer_calculation(incar, kp)
            ctx = build_vasp_context(folder, paths=list(folder.iterdir()), incar_meta=incar,
                                     kpoints_meta=kp, inferred=inferred)
            self.assertEqual(inferred['calc_type'], 'relax')
            self.assertEqual(ctx.workflow, 'geometry_optimization')
            self.assertIn('INCAR:NSW=100>0', ctx.evidence)
            self.assertIn('INCAR:IBRION=2', ctx.evidence)
            self.assertIn('INCAR:ISIF=2', ctx.evidence)
            self.assertIn('INCAR:EDIFFG=-0.02', ctx.evidence)

    def test_static_scf_explicit_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = write_vasp_folder(Path(tmp) / 'scr', optics=False, extra=False)
            (folder / 'INCAR').write_text('ENCUT=450\nNSW=0\nIBRION=-1\n', encoding='utf-8')
            incar = parse_incar(folder / 'INCAR')
            kp = parse_kpoints(folder / 'KPOINTS')
            inferred = infer_calculation(incar, kp)
            ctx = build_vasp_context(folder, paths=list(folder.iterdir()), incar_meta=incar,
                                     kpoints_meta=kp, inferred=inferred)
            self.assertEqual(inferred['calc_type'], 'static')
            self.assertEqual(ctx.workflow, 'static_scf')

    def test_static_scf_fallback_when_defaults_are_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = write_vasp_folder(Path(tmp) / 'not_named_scf', optics=False, extra=False)
            # Real INCARs often omit NSW=0 and IBRION=-1 because they are not needed
            # for a routine electronic run. The completed output set is supporting evidence.
            (folder / 'INCAR').write_text('ENCUT=450\nEDIFF=1E-6\nGGA=PE\n', encoding='utf-8')
            incar = parse_incar(folder / 'INCAR')
            kp = parse_kpoints(folder / 'KPOINTS')
            inferred = infer_calculation(incar, kp)
            ctx = build_vasp_context(folder, paths=list(folder.iterdir()), incar_meta=incar,
                                     kpoints_meta=kp, inferred=inferred)
            self.assertEqual(ctx.workflow, 'static_scf')
            self.assertIn('files:electronic_outputs', ctx.evidence)

    def test_folder_name_scr_is_not_used_as_scientific_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = write_vasp_folder(Path(tmp) / 'scr', optics=False, extra=False)
            (folder / 'INCAR').write_text('IBRION=2\nNSW=30\n', encoding='utf-8')
            incar = parse_incar(folder / 'INCAR')
            kp = parse_kpoints(folder / 'KPOINTS')
            ctx = build_vasp_context(folder, paths=list(folder.iterdir()), incar_meta=incar,
                                     kpoints_meta=kp, inferred=infer_calculation(incar, kp))
            self.assertEqual(ctx.workflow, 'geometry_optimization')


class FilenameFidelityV0622Tests(unittest.TestCase):
    def test_calculation_query_preserves_exact_source_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = write_vasp_folder(base / 'calc', optics=False, extra=False)
            (folder / 'KPATH.in').write_text('k path\n', encoding='utf-8')
            (folder / 'HIGH_SYMMETRY_POINTS').write_text('GAMMA 0 0 0\n', encoding='utf-8')
            _, repo, _, _, calcs = build_services(base / 'data')
            result = calcs.import_vasp_folder(folder)
            rows = repo.list_calculation_files(result.calculation_id)
            by_path = {r['original_relative_path']: r for r in rows}
            for exact in ['INCAR', 'POSCAR', 'KPOINTS', 'POTCAR', 'OUTCAR',
                          'KPATH.in', 'HIGH_SYMMETRY_POINTS', 'vasprun.xml']:
                with self.subTest(exact=exact):
                    self.assertIn(exact, by_path)
                    self.assertEqual(by_path[exact]['file_type'], Path(exact).name)
                    self.assertEqual(by_path[exact]['original_name'], Path(exact).name)
                    self.assertEqual(by_path[exact]['display_name'], Path(exact).name)

    def test_same_sha_different_logical_names_keep_each_source_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = write_vasp_folder(base / 'calc', optics=False, extra=False)
            # Force POSCAR and CONTCAR to be byte-identical, thus one SHA256 object.
            (folder / 'CONTCAR').write_bytes((folder / 'POSCAR').read_bytes())
            _, repo, _, _, calcs = build_services(base / 'data')
            result = calcs.import_vasp_folder(folder)
            pos = repo.get_calculation_file(result.calculation_id, 'POSCAR')
            con = repo.get_calculation_file(result.calculation_id, 'CONTCAR')
            self.assertEqual(pos['file_id'], con['file_id'])
            self.assertEqual(pos['sha256'], con['sha256'])
            self.assertEqual(pos['original_name'], 'POSCAR')
            self.assertEqual(con['original_name'], 'CONTCAR')
            # Object-level first-seen name is preserved separately and is not used
            # as the logical Calculation display name.
            self.assertIn('object_original_name', pos)
            self.assertIn('object_original_name', con)

    def test_duplicate_reimport_repairs_legacy_lowercase_logical_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = write_vasp_folder(base / 'calc', optics=False, extra=False)
            (folder / 'KPATH.in').write_text('k path\n', encoding='utf-8')
            _, repo, _, _, calcs = build_services(base / 'data')
            first = calcs.import_vasp_folder(folder)

            # Simulate a legacy catalog that normalized logical names to lowercase.
            with closing(sqlite3.connect(repo.db_path)) as conn:
                conn.execute(
                    "UPDATE calculation_files SET original_relative_path='kpath.in', file_type='kpath.in' "
                    "WHERE calculation_id=? AND original_relative_path='KPATH.in'",
                    (first.calculation_id,),
                )
                conn.commit()

            again = calcs.import_vasp_folder(folder)
            self.assertEqual(again.status, 'duplicate_calculation')
            row = repo.get_calculation_file_by_path(first.calculation_id, 'KPATH.in')
            self.assertIsNotNone(row)
            self.assertEqual(row['original_relative_path'], 'KPATH.in')
            self.assertEqual(row['file_type'], 'KPATH.in')
            self.assertEqual(row['original_name'], 'KPATH.in')


class MolecularDynamicsV0624Tests(unittest.TestCase):
    def _context_for(self, folder: Path):
        incar = parse_incar(folder / 'INCAR')
        kp = parse_kpoints(folder / 'KPOINTS')
        inferred = infer_calculation(incar, kp)
        ctx = build_vasp_context(
            folder, paths=list(folder.iterdir()), incar_meta=incar,
            kpoints_meta=kp, inferred=inferred,
        )
        return incar, inferred, ctx

    def test_ibrion_zero_positive_nsw_is_molecular_dynamics(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = write_vasp_folder(Path(tmp) / 'dongli', optics=False, extra=False)
            (folder / 'INCAR').write_text(
                'GGA = PE\n'
                'NSW = 5000 (MD steps)\n'
                'IBRION = 0 (molecular dynamics)\n'
                'ISIF = 2\n'
                'POTIM = 1.0\n'
                'TEBEG = 300\n'
                'TEEND = 300\n',
                encoding='utf-8',
            )
            incar, inferred, ctx = self._context_for(folder)
            self.assertEqual(incar['tags']['NSW'], 5000)
            self.assertEqual(incar['tags']['IBRION'], 0)
            self.assertEqual(inferred['calc_type'], 'md')
            self.assertEqual(ctx.calc_type, 'md')
            self.assertEqual(ctx.workflow, 'molecular_dynamics')
            self.assertEqual(ctx.functional, 'PBE')
            self.assertIn('INCAR:NSW=5000>0', ctx.evidence)
            self.assertIn('INCAR:IBRION=0', ctx.evidence)
            self.assertIn('INCAR:POTIM=1.0', ctx.evidence)
            self.assertIn('INCAR:TEBEG=300', ctx.evidence)

    def test_folder_name_opt_does_not_turn_md_into_relaxation(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = write_vasp_folder(Path(tmp) / 'opt', optics=False, extra=False)
            (folder / 'INCAR').write_text('NSW=1000\nIBRION=0\nPOTIM=0.5\n', encoding='utf-8')
            _incar, inferred, ctx = self._context_for(folder)
            self.assertEqual(inferred['calc_type'], 'md')
            self.assertEqual(ctx.workflow, 'molecular_dynamics')

    def test_ibrion_two_positive_nsw_remains_geometry_optimization(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = write_vasp_folder(Path(tmp) / 'anything', optics=False, extra=False)
            (folder / 'INCAR').write_text('NSW=120\nIBRION=2\nISIF=2\nEDIFFG=-0.01\n', encoding='utf-8')
            _incar, inferred, ctx = self._context_for(folder)
            self.assertEqual(inferred['calc_type'], 'relax')
            self.assertEqual(ctx.workflow, 'geometry_optimization')

    def test_icharg_keeps_chg_and_chgcar_as_outputs_for_completed_history_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = write_vasp_folder(Path(tmp) / 'band', optics=False, extra=False)
            (folder / 'INCAR').write_text('NSW=0\nIBRION=-1\nICHARG=1\n', encoding='utf-8')
            (folder / 'CHG').write_text('charge\n', encoding='utf-8')
            incar, inferred, ctx = self._context_for(folder)
            from material_agent.semantics import classify_calculation_file
            chg = classify_calculation_file('CHG', ctx)
            chgcar = classify_calculation_file('CHGCAR', ctx)
            self.assertEqual(chg['role'], 'output')
            self.assertEqual(chgcar['role'], 'output')
            self.assertEqual(chgcar['role_source'], 'conservative_history_rule')

    def test_completed_static_folder_base_inputs_are_only_four_core_vasp_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = write_vasp_folder(Path(tmp) / 'static', optics=False, extra=False)
            (folder / 'INCAR').write_text('NSW=0\nIBRION=-1\nISTART=1\nICHARG=1\n', encoding='utf-8')
            incar, inferred, ctx = self._context_for(folder)
            from material_agent.semantics import classify_calculation_file
            roles = {p.name: classify_calculation_file(p.name, ctx)['role'] for p in folder.iterdir() if p.is_file()}
            inputs = {name for name, role in roles.items() if role == 'input'}
            self.assertEqual(inputs, {'INCAR', 'POSCAR', 'KPOINTS', 'POTCAR'})
            self.assertEqual(roles['CHGCAR'], 'output')
            self.assertEqual(roles['WAVECAR'], 'output')


if __name__ == '__main__':
    unittest.main()
