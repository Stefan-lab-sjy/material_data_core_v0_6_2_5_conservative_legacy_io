from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from .agent_tools import MaterialAgentTools


CALC_ALIASES = {
    "光学": "optics",
    "光学性质": "optics",
    "optics": "optics",
    "static": "static",
    "静态": "static",
    "静态计算": "static",
    "band": "band",
    "能带": "band",
    "能带计算": "band",
    "dos": "dos",
    "态密度": "dos",
    "relax": "relax",
    "优化": "relax",
    "结构优化": "relax",
    "phonon": "phonon",
    "声子": "phonon",
    "dielectric": "dielectric",
    "介电": "dielectric",
}

FILE_TYPES = {
    "INCAR", "KPOINTS", "POSCAR", "POTCAR", "OUTCAR", "CONTCAR", "OSZICAR",
    "XDATCAR", "CHGCAR", "CHG", "WAVECAR", "WAVEDER", "DOSCAR", "EIGENVAL",
    "PROCAR", "LOCPOT", "IBZKPT", "PCDAT", "REPORT", "ELFCAR", "AECCAR0",
    "AECCAR1", "AECCAR2", "VASPRUN.XML",
}


@dataclass
class AgentReply:
    text: str
    tool_name: str | None = None
    data: Any = None


class MaterialAgentRuntime:
    """First deterministic Agent runtime.

    This layer intentionally has no external LLM dependency.  It proves that an
    Agent can plan simple requests and call stable MaterialAgentTools.  A future
    LLM planner can replace `_plan` without changing the tools or data core.
    """

    def __init__(self, tools: MaterialAgentTools):
        self.tools = tools

    @staticmethod
    def help_text() -> str:
        return (
            "Available commands:\n"
            "  materials                         - list materials\n"
            "  calculations                      - list calculations\n"
            "  find SiS2 optics                  - find calculations\n"
            "  show calc_xxx                     - calculation summary\n"
            "  files calc_xxx                    - list calculation files\n"
            "  get calc_xxx INCAR                - exact file from a calculation\n"
            "  latest SiS2 optics INCAR          - latest matching calculation file\n"
            "\nChinese aliases are also accepted, for example:\n"
            "  列出材料\n"
            "  找 SiS2 光学\n"
            "  最新 SiS2 光学 INCAR\n"
            "  获取 calc_xxx OSZICAR\n"
            "\nType exit to quit."
        )

    @staticmethod
    def _canonical_calc_type(token: str | None) -> str | None:
        if not token:
            return None
        t = token.strip().lower()
        return CALC_ALIASES.get(t, t)

    @staticmethod
    def _canonical_file_type(token: str) -> str:
        if token.lower() == "vasprun.xml":
            return "vasprun.xml"
        return token.upper()

    def ask(self, message: str) -> AgentReply:
        text = " ".join(message.strip().split())
        if not text:
            return AgentReply("Please enter a command. Type help for examples.")
        lower = text.lower()

        if lower in {"help", "?", "帮助", "菜单"}:
            return AgentReply(self.help_text())
        if lower in {"materials", "list materials", "列出材料", "材料列表", "所有材料"}:
            rows = self.tools.list_materials()
            if not rows:
                return AgentReply("No materials are stored yet.", "list_materials", rows)
            lines = ["Materials:"]
            for r in rows:
                lines.append(f"  {r['formula']:<12} calculations={r['calculation_count']} structures={r['structure_count']}  {r['material_id']}")
            return AgentReply("\n".join(lines), "list_materials", rows)
        if lower in {"calculations", "list calculations", "列出计算", "计算列表", "所有计算"}:
            rows = self.tools.find_calculations()
            return AgentReply(self._format_calculations(rows), "find_calculations", rows)

        m = re.match(r"^(?:show|查看)\s+(calc_[A-Za-z0-9]+)$", text, re.I)
        if m:
            calc = self.tools.get_calculation(m.group(1))
            if calc is None:
                return AgentReply(f"Calculation not found: {m.group(1)}", "get_calculation", None)
            return AgentReply(self._format_calculation(calc), "get_calculation", calc)

        m = re.match(r"^(?:files|文件)\s+(calc_[A-Za-z0-9]+)$", text, re.I)
        if m:
            rows = self.tools.list_calculation_files(m.group(1))
            if not rows:
                return AgentReply(f"No files found for: {m.group(1)}", "list_calculation_files", rows)
            return AgentReply(self._format_files(m.group(1), rows), "list_calculation_files", rows)

        m = re.match(r"^(?:get|获取)\s+(calc_[A-Za-z0-9]+)\s+([^\s]+)$", text, re.I)
        if m:
            ft = self._canonical_file_type(m.group(2))
            row = self.tools.get_calculation_file(m.group(1), ft)
            if row is None:
                return AgentReply(f"{ft} was not found in {m.group(1)}.", "get_calculation_file", None)
            return AgentReply(self._format_file(row), "get_calculation_file", row)

        m = re.match(r"^(?:latest|最新)\s+([^\s]+)\s+([^\s]+)\s+([^\s]+)$", text, re.I)
        if m:
            material = m.group(1)
            calc_type = self._canonical_calc_type(m.group(2)) or m.group(2)
            file_type = self._canonical_file_type(m.group(3))
            row = self.tools.get_latest_calculation_file(material=material, calc_type=calc_type, file_type=file_type)
            if row is None:
                return AgentReply(
                    f"No matching {file_type} found for material={material}, calc_type={calc_type}.",
                    "get_latest_calculation_file",
                    None,
                )
            return AgentReply(self._format_file(row), "get_latest_calculation_file", row)

        m = re.match(r"^(?:find|找|查找)\s+([^\s]+)(?:\s+([^\s]+))?$", text, re.I)
        if m:
            material = m.group(1)
            calc_type = self._canonical_calc_type(m.group(2))
            rows = self.tools.find_calculations(material=material, calc_type=calc_type)
            return AgentReply(self._format_calculations(rows), "find_calculations", rows)

        # Natural-language-ish semantic fallback.  We deliberately keep this deterministic:
        # detect a material already known to the catalog, a calculation-type alias and a file type.
        known_material = None
        for mat in self.tools.list_materials():
            formula = str(mat.get("formula") or "")
            if formula and formula.lower() in lower:
                known_material = formula
                break
        known_calc_type = None
        # Match longer aliases first so 光学性质 wins over 光学.
        for alias in sorted(CALC_ALIASES, key=len, reverse=True):
            if alias.lower() in lower:
                known_calc_type = CALC_ALIASES[alias]
                break
        known_file_type = None
        for ft in sorted(FILE_TYPES, key=len, reverse=True):
            if ft.lower() in lower:
                known_file_type = self._canonical_file_type(ft)
                break
        if known_material and known_calc_type and known_file_type:
            row = self.tools.get_latest_calculation_file(
                material=known_material, calc_type=known_calc_type, file_type=known_file_type
            )
            if row:
                return AgentReply(self._format_file(row), "get_latest_calculation_file", row)
        if known_material and known_calc_type:
            rows = self.tools.find_calculations(material=known_material, calc_type=known_calc_type)
            return AgentReply(self._format_calculations(rows), "find_calculations", rows)
        if known_material and any(k in lower for k in ("计算", "calculation", "calculations")):
            rows = self.tools.find_calculations(material=known_material)
            return AgentReply(self._format_calculations(rows), "find_calculations", rows)

        # Natural-ish fallback: extract calc id + known file type.
        calc_match = re.search(r"calc_[A-Za-z0-9]+", text, re.I)
        file_match = None
        for token in re.findall(r"[A-Za-z0-9_.]+", text):
            if token.upper() in FILE_TYPES:
                file_match = token
                break
        if calc_match and file_match:
            cid = calc_match.group(0)
            ft = self._canonical_file_type(file_match)
            row = self.tools.get_calculation_file(cid, ft)
            if row:
                return AgentReply(self._format_file(row), "get_calculation_file", row)

        return AgentReply(
            "I could not map that request to a tool yet. This v0.5 runtime is rule-based.\n\n" + self.help_text()
        )

    @staticmethod
    def _format_calculations(rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "No matching calculations found."
        lines = ["Calculations:"]
        for r in rows:
            lines.append(
                f"  {r['calculation_id']}  material={r.get('material_formula') or '-'} "
                f"type={r.get('calc_type') or '-'} functional={r.get('functional') or '-'} "
                f"status={r.get('status') or '-'} files={r.get('file_count', '-')}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_calculation(calc: dict[str, Any]) -> str:
        rows = calc.get("files") or []
        lines = [
            f"Calculation: {calc['calculation_id']}",
            f"Material   : {calc.get('material_formula') or '-'}",
            f"Type       : {calc.get('calc_type') or '-'}",
            f"Functional : {calc.get('functional') or '-'}",
            f"Status     : {calc.get('status') or '-'}",
            f"Files      : {len(rows)}",
        ]
        if rows:
            lines.append("")
            lines.append("Logical files:")
            for r in rows:
                lines.append(f"  [{r['role']:<9}] {r['original_relative_path']:<28} sha={r['sha256'][:12]}")
        return "\n".join(lines)

    @staticmethod
    def _format_files(calculation_id: str, rows: list[dict[str, Any]]) -> str:
        lines = [f"Files for {calculation_id}:"]
        for r in rows:
            lines.append(f"  [{r['role']:<9}] {r['original_relative_path']:<28} sha={r['sha256'][:12]} file_id={r['file_id']}")
        return "\n".join(lines)

    @staticmethod
    def _format_file(row: dict[str, Any]) -> str:
        return "\n".join([
            f"Calculation : {row.get('calculation_id') or '-'}",
            f"Material    : {row.get('material_formula') or '-'}",
            f"Calc type   : {row.get('calc_type') or '-'}",
            f"File type   : {row.get('file_type') or row.get('original_name') or '-'}",
            f"Role        : {row.get('role') or '-'}",
            f"File ID     : {row.get('file_id') or '-'}",
            f"SHA256      : {row.get('sha256') or '-'}",
            f"Stored path : {row.get('stored_path') or '-'}",
        ])
