import tempfile
import unittest
from pathlib import Path

from material_agent.agent_tools import MaterialAgentTools
from material_agent.app import build_services
from common import write_vasp_folder


class AgentToolsTests(unittest.TestCase):
    def _setup_two_calcs(self, base: Path):
        static = write_vasp_folder(base/'static', optics=False, extra=True, variant='A')
        optics = write_vasp_folder(base/'optics', optics=True, extra=True, variant='B')
        _, repo, _, _, calcs = build_services(base/'data')
        a = calcs.import_vasp_folder(static)
        b = calcs.import_vasp_folder(optics)
        return repo, calcs, a, b

    def test_list_materials_and_find_calculations(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo, calcs, a, b = self._setup_two_calcs(base)
            tools = MaterialAgentTools(repo, calcs)
            mats = tools.list_materials()
            self.assertEqual(len(mats), 1)
            self.assertEqual(mats[0]['formula'], 'SiS2')
            self.assertEqual(mats[0]['calculation_count'], 2)
            optics = tools.find_calculations(material='SiS2', calc_type='optics')
            self.assertEqual(len(optics), 1)
            self.assertEqual(optics[0]['calculation_id'], b.calculation_id)

    def test_exact_calculation_file_distinguishes_oszicar(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo, calcs, a, b = self._setup_two_calcs(base)
            tools = MaterialAgentTools(repo, calcs)
            osa = tools.get_calculation_file(a.calculation_id, 'OSZICAR')
            osb = tools.get_calculation_file(b.calculation_id, 'OSZICAR')
            self.assertIsNotNone(osa)
            self.assertIsNotNone(osb)
            self.assertNotEqual(osa['sha256'], osb['sha256'])
            self.assertNotEqual(osa['file_id'], osb['file_id'])

    def test_latest_semantic_file_gets_optics_incar(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo, calcs, a, b = self._setup_two_calcs(base)
            tools = MaterialAgentTools(repo, calcs)
            row = tools.get_latest_calculation_file(material='SiS2', calc_type='optics', file_type='INCAR')
            self.assertIsNotNone(row)
            self.assertEqual(row['calculation_id'], b.calculation_id)
            self.assertEqual(row['calc_type'], 'optics')
            self.assertEqual(row['file_type'], 'INCAR')

    def test_get_calculation_returns_all_logical_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo, calcs, a, _ = self._setup_two_calcs(base)
            tools = MaterialAgentTools(repo, calcs)
            calc = tools.get_calculation(a.calculation_id)
            self.assertIsNotNone(calc)
            names = {r['file_type'] for r in calc['files']}
            self.assertIn('INCAR', names)
            self.assertIn('OSZICAR', names)
            self.assertIn('OUTCAR', names)


if __name__ == '__main__':
    unittest.main()
