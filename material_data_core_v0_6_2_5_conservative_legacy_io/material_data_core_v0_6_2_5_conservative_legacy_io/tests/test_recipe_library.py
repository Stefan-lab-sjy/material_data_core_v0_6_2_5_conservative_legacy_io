import json
import tempfile
import unittest
from pathlib import Path

from material_agent.recipe_library import RecipeLibrary


class RecipeLibraryTests(unittest.TestCase):
    def test_list_and_instantiate_recipe(self):
        project_root = Path(__file__).resolve().parents[1]
        library = RecipeLibrary(project_root / 'recipes')
        ids = {r['recipe_id'] for r in library.list_recipes()}
        self.assertIn('vasp.pbe.relax.2d.v1', ids)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'run'
            result = library.instantiate('vasp.pbe.relax.2d.v1', out, overrides={'ENCUT': 520})
            self.assertTrue((out / 'INCAR').exists())
            self.assertIn('ENCUT  = 520', (out / 'INCAR').read_text(encoding='utf-8'))
            manifest = json.loads((out / '.material-agent-run.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['recipe_id'], 'vasp.pbe.relax.2d.v1')
            self.assertEqual(manifest['parameters']['ENCUT'], 520)
            self.assertEqual(result['rendered_files'], ['INCAR'])


if __name__ == '__main__':
    unittest.main()
