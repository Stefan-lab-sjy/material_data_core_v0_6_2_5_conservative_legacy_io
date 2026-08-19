from __future__ import annotations

from pathlib import Path
import json
from string import Template
from typing import Any

from .config import default_project_root
from .utils import utc_now


class RecipeLibrary:
    """Filesystem recipe library used to create *new* calculation inputs.

    Recipes are deliberately separate from archived Calculation inputs.  Once a recipe
    is instantiated, the resulting real INCAR/KPOINTS/etc. live in the run directory and
    are later captured by normal SHA256 ingestion.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root).expanduser().resolve() if root else (default_project_root() / "recipes")

    def _recipe_dirs(self) -> list[Path]:
        if not self.root.exists():
            return []
        return sorted({p.parent for p in self.root.rglob("recipe.json")}, key=lambda p: p.as_posix())

    def _load_dir(self, directory: Path) -> dict[str, Any]:
        path = directory / "recipe.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not data.get("recipe_id"):
            raise ValueError(f"Invalid recipe: {path}")
        data = dict(data)
        data["recipe_dir"] = str(directory)
        return data

    def list_recipes(self) -> list[dict[str, Any]]:
        result = []
        for d in self._recipe_dirs():
            try:
                r = self._load_dir(d)
            except Exception:
                continue
            result.append({
                "recipe_id": r.get("recipe_id"),
                "version": r.get("version"),
                "code": r.get("code"),
                "task_type": r.get("task_type"),
                "method": r.get("method"),
                "dimensionality": r.get("dimensionality"),
                "description": r.get("description"),
                "recipe_dir": r.get("recipe_dir"),
            })
        return result

    def get_recipe(self, recipe_id: str) -> dict[str, Any]:
        for d in self._recipe_dirs():
            r = self._load_dir(d)
            if str(r.get("recipe_id")) == recipe_id:
                return r
        raise KeyError(recipe_id)

    def instantiate(
        self,
        recipe_id: str,
        destination: str | Path,
        *,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        recipe = self.get_recipe(recipe_id)
        source_dir = Path(recipe["recipe_dir"])
        destination = Path(destination).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)

        params: dict[str, Any] = dict(recipe.get("default_parameters") or {})
        params.update(overrides or {})
        rendered: list[str] = []

        templates = recipe.get("template_files") or {}
        if not isinstance(templates, dict):
            raise ValueError(f"recipe {recipe_id}: template_files must be an object")
        for output_name, template_name in templates.items():
            src = source_dir / str(template_name)
            if not src.exists():
                raise FileNotFoundError(src)
            text = src.read_text(encoding="utf-8")
            value_map = {k: str(v) for k, v in params.items()}
            rendered_text = Template(text).safe_substitute(value_map)
            target = destination / str(output_name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered_text, encoding="utf-8")
            rendered.append(str(output_name))

        manifest = {
            "schema_version": 1,
            "recipe_id": recipe.get("recipe_id"),
            "recipe_version": recipe.get("version"),
            "code": recipe.get("code"),
            "task_type": recipe.get("task_type"),
            "method": recipe.get("method"),
            "dimensionality": recipe.get("dimensionality"),
            "parameters": params,
            "required_runtime_inputs": recipe.get("required_runtime_inputs", []),
            "expected_outputs": recipe.get("expected_outputs", []),
            "created_at": utc_now(),
        }
        (destination / ".material-agent-run.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {
            "recipe_id": recipe_id,
            "destination": str(destination),
            "rendered_files": rendered,
            "manifest": str(destination / ".material-agent-run.json"),
            "required_runtime_inputs": manifest["required_runtime_inputs"],
        }
