import tempfile
import unittest
from pathlib import Path

from material_agent.agent_runtime import MaterialAgentRuntime
from material_agent.agent_tools import MaterialAgentTools
from material_agent.app import build_services
from common import write_vasp_folder


class AgentRuntimeTests(unittest.TestCase):
    def _runtime(self, base: Path):
        static = write_vasp_folder(base/'static', optics=False, extra=True, variant='A')
        optics = write_vasp_folder(base/'optics', optics=True, extra=True, variant='B')
        _, repo, _, _, calcs = build_services(base/'data')
        a = calcs.import_vasp_folder(static)
        b = calcs.import_vasp_folder(optics)
        return MaterialAgentRuntime(MaterialAgentTools(repo, calcs)), a, b

    def test_chinese_find_optics(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _, b = self._runtime(Path(tmp))
            reply = runtime.ask('找 SiS2 光学')
            self.assertEqual(reply.tool_name, 'find_calculations')
            self.assertIn(b.calculation_id, reply.text)

    def test_latest_chinese_optics_incar(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _, b = self._runtime(Path(tmp))
            reply = runtime.ask('最新 SiS2 光学 INCAR')
            self.assertEqual(reply.tool_name, 'get_latest_calculation_file')
            self.assertIsNotNone(reply.data)
            self.assertEqual(reply.data['calculation_id'], b.calculation_id)
            self.assertEqual(reply.data['file_type'], 'INCAR')

    def test_get_specific_oszicar(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, a, _ = self._runtime(Path(tmp))
            reply = runtime.ask(f'获取 {a.calculation_id} OSZICAR')
            self.assertEqual(reply.tool_name, 'get_calculation_file')
            self.assertIsNotNone(reply.data)
            self.assertEqual(reply.data['file_type'], 'OSZICAR')
            self.assertIn(reply.data['sha256'], reply.text)


    def test_natural_chinese_sentence_routes_to_optics_incar(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _, b = self._runtime(Path(tmp))
            reply = runtime.ask('请给我 SiS2 光学性质计算使用的 INCAR')
            self.assertEqual(reply.tool_name, 'get_latest_calculation_file')
            self.assertIsNotNone(reply.data)
            self.assertEqual(reply.data['calculation_id'], b.calculation_id)

    def test_help_for_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _, _ = self._runtime(Path(tmp))
            reply = runtime.ask('随便问一个当前不支持的问题')
            self.assertIn('rule-based', reply.text)
            self.assertIn('latest SiS2 optics INCAR', reply.text)


if __name__ == '__main__':
    unittest.main()
