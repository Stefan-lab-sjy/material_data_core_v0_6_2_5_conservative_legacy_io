import tempfile
import unittest
from pathlib import Path

from material_agent.parsers import parse_incar, parse_poscar, infer_calculation


class ParserTests(unittest.TestCase):
    def test_incar_strips_comments_and_types_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'INCAR'
            p.write_text('ENCUT = 400 ! comment\nEDIFF = 1E-6 # x\nLOPTICS = .TRUE.\n', encoding='utf-8')
            tags = parse_incar(p)['tags']
            self.assertEqual(tags['ENCUT'], 400)
            self.assertAlmostEqual(tags['EDIFF'], 1e-6)
            self.assertIs(tags['LOPTICS'], True)

    def test_optics_inference(self):
        meta = {'tags': {'LOPTICS': True, 'GGA': 'PE'}}
        r = infer_calculation(meta, {'mode': 'gamma'})
        self.assertEqual(r['calc_type'], 'optics')
        self.assertEqual(r['functional'], 'PBE')

    def test_poscar_formula(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'POSCAR'
            p.write_text('SiS2\n1\n3 0 0\n0 3 0\n0 0 20\nSi S\n1 2\nDirect\n0 0 0\n0 0 0\n0 0 0\n', encoding='utf-8')
            r = parse_poscar(p)
            self.assertEqual(r['formula'], 'SiS2')
            self.assertEqual(r['atom_count'], 3)


class RealWorldIncarSyntaxTests(unittest.TestCase):
    def test_semicolon_separated_assignments_are_all_parsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'INCAR'
            p.write_text(
                'ENCUT = 500 ; EDIFF = 1E-6\n'
                'IBRION = 2 ; NSW = 200 ; ISIF = 2 ; EDIFFG = -0.01 ! relax\n',
                encoding='utf-8',
            )
            tags = parse_incar(p)['tags']
            self.assertEqual(tags['ENCUT'], 500)
            self.assertAlmostEqual(tags['EDIFF'], 1e-6)
            self.assertEqual(tags['IBRION'], 2)
            self.assertEqual(tags['NSW'], 200)
            self.assertEqual(tags['ISIF'], 2)
            self.assertAlmostEqual(tags['EDIFFG'], -0.01)

    def test_parenthetical_annotations_are_not_part_of_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'INCAR'
            p.write_text(
                'Global Parameters\n'
                'ISTART = 0        (Read existing wavefunction, if there)\n'
                'ICHARG = 2        (Non-self-consistent: copied template note)\n'
                'LREAL = .FALSE.   (Projection operators: automatic)\n'
                'ENCUT = 400       (Cut-off energy for plane wave basis set, in eV)\n'
                'NSW = 100         (Max ionic steps)\n'
                'IBRION = 2        (Algorithm: 0-MD; 1-Quasi-New; 2-CG)\n'
                'ISIF = 2          (Stress/relaxation: ions)\n'
                'EDIFFG = -2E-02   (Ionic convergence, eV/AA)\n',
                encoding='utf-8',
            )
            meta = parse_incar(p)
            tags = meta['tags']
            self.assertEqual(tags['ISTART'], 0)
            self.assertEqual(tags['ICHARG'], 2)
            self.assertIs(tags['LREAL'], False)
            self.assertEqual(tags['ENCUT'], 400)
            self.assertEqual(tags['NSW'], 100)
            self.assertEqual(tags['IBRION'], 2)
            self.assertEqual(tags['ISIF'], 2)
            self.assertAlmostEqual(tags['EDIFFG'], -0.02)
            self.assertEqual(meta['raw_tags']['NSW'], '100         (Max ionic steps)')
            self.assertEqual(meta['annotations']['NSW'], 'Max ionic steps')
            self.assertIn('0-MD; 1-Quasi-New; 2-CG', meta['annotations']['IBRION'])

    def test_parenthetical_note_cannot_change_workflow_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'INCAR'
            p.write_text(
                'ICHARG = 2 (Non-self-consistent: GGA/LDA band structures)\n'
                'NSW = 100 (Max ionic steps)\n'
                'IBRION = 2 (Conjugate-gradient ionic relaxation)\n'
                'ISIF = 2 (Relax ions)\n',
                encoding='utf-8',
            )
            meta = parse_incar(p)
            result = infer_calculation(meta, {'mode': 'gamma'})
            self.assertEqual(result['calc_type'], 'relax')
