from __future__ import annotations

from pathlib import Path
from typing import Any

from .calculations import CalculationService
from .repository import CatalogRepository
from .recipe_library import RecipeLibrary


class MaterialAgentTools:
    """Stable tool layer between an Agent and the Material Data Core.

    The Agent should query through this class instead of reading SHA256 folders or
    issuing SQL directly.  A future web/LLM agent can call the same methods.
    """

    def __init__(self, repository: CatalogRepository, calculations: CalculationService):
        self.repository = repository
        self.calculations = calculations

    def list_materials(self) -> list[dict[str, Any]]:
        return self.repository.list_materials()

    def find_calculations(
        self,
        *,
        material: str | None = None,
        calc_type: str | None = None,
        functional: str | None = None,
        status: str | None = None,
        soc: bool | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self.repository.search_calculations(
            material_formula=material,
            calc_type=calc_type,
            functional=functional,
            status=status,
            soc=soc,
            limit=limit,
        )

    def get_calculation(self, calculation_id: str) -> dict[str, Any] | None:
        calc = self.repository.get_calculation(calculation_id)
        if calc is None:
            return None
        result = dict(calc)
        result["files"] = self.repository.list_calculation_files(calculation_id)
        return result

    def list_calculation_files(self, calculation_id: str) -> list[dict[str, Any]]:
        return self.repository.list_calculation_files(calculation_id)

    def get_calculation_file(self, calculation_id: str, file_type: str) -> dict[str, Any] | None:
        row = self.repository.get_calculation_file(calculation_id, file_type)
        if row is None:
            return None
        out = dict(row)
        calc = self.repository.get_calculation(calculation_id)
        if calc:
            out["material_formula"] = calc.get("material_formula")
            out["calc_type"] = calc.get("calc_type")
            out["functional"] = calc.get("functional")
            out["calculation_status"] = calc.get("status")
        return out

    def get_latest_calculation(
        self,
        *,
        material: str,
        calc_type: str | None = None,
        functional: str | None = None,
        status: str | None = None,
        soc: bool | None = None,
    ) -> dict[str, Any] | None:
        return self.repository.get_latest_calculation(
            material_formula=material,
            calc_type=calc_type,
            functional=functional,
            status=status,
            soc=soc,
        )

    def get_latest_calculation_file(
        self,
        *,
        material: str,
        calc_type: str,
        file_type: str,
        functional: str | None = None,
        status: str | None = None,
        soc: bool | None = None,
    ) -> dict[str, Any] | None:
        # Prefer a completed calculation when the caller did not explicitly choose a status.
        calc = self.get_latest_calculation(
            material=material,
            calc_type=calc_type,
            functional=functional,
            status=(status or "completed"),
            soc=soc,
        )
        if calc is None and status is None:
            calc = self.get_latest_calculation(
                material=material,
                calc_type=calc_type,
                functional=functional,
                status=None,
                soc=soc,
            )
        if calc is None:
            return None
        row = self.get_calculation_file(calc["calculation_id"], file_type)
        if row is None:
            return None
        out = dict(row)
        out["material_formula"] = calc.get("material_formula")
        out["calc_type"] = calc.get("calc_type")
        out["functional"] = calc.get("functional")
        out["calculation_status"] = calc.get("status")
        return out

    def compare_calculations(self, calc_a: str, calc_b: str) -> list[dict[str, Any]]:
        return self.calculations.compare_calculations(calc_a, calc_b)

    def export_calculation(self, calculation_id: str, destination: str | Path, *, inputs_only: bool = False) -> str:
        return str(self.calculations.export_files(calculation_id, destination, inputs_only=inputs_only))


    def list_recipes(self) -> list[dict[str, Any]]:
        return RecipeLibrary().list_recipes()

    def get_recipe(self, recipe_id: str) -> dict[str, Any]:
        return RecipeLibrary().get_recipe(recipe_id)

    def instantiate_recipe(self, recipe_id: str, destination: str | Path, *, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        return RecipeLibrary().instantiate(recipe_id, destination, overrides=overrides)

    @staticmethod
    def tool_manifest() -> list[dict[str, Any]]:
        """Machine-readable description for a future LLM/tool-calling layer."""
        return [
            {
                "name": "list_materials",
                "description": "List materials known by the catalog.",
                "arguments": {},
            },
            {
                "name": "find_calculations",
                "description": "Find calculations by material, calculation type, functional, status and SOC.",
                "arguments": {
                    "material": "optional formula such as SiS2",
                    "calc_type": "optional type such as relax/static/band/dos/optics/md",
                    "functional": "optional PBE/HSE06/...",
                    "status": "optional completed/imported/...",
                    "soc": "optional boolean",
                },
            },
            {
                "name": "get_calculation",
                "description": "Return one calculation and all logical files linked to it.",
                "arguments": {"calculation_id": "calc_..."},
            },
            {
                "name": "get_calculation_file",
                "description": "Get the exact file linked to one calculation, e.g. its INCAR or OSZICAR.",
                "arguments": {"calculation_id": "calc_...", "file_type": "INCAR/OSZICAR/OUTCAR/..."},
            },
            {
                "name": "get_latest_calculation_file",
                "description": "Get the latest matching calculation file by material and semantic calculation type.",
                "arguments": {"material": "SiS2", "calc_type": "optics", "file_type": "INCAR"},
            },
            {
                "name": "list_recipes",
                "description": "List reusable VASP calculation recipes used to create new run inputs.",
                "arguments": {},
            },
            {
                "name": "get_recipe",
                "description": "Read one recipe definition including required runtime inputs and expected outputs.",
                "arguments": {"recipe_id": "vasp.pbe.relax.2d.v1"},
            },
            {
                "name": "instantiate_recipe",
                "description": "Create actual input template files for a new calculation run; does not execute VASP.",
                "arguments": {"recipe_id": "vasp.pbe.relax.2d.v1", "destination": "run folder", "overrides": "optional parameters"},
            },
        ]
