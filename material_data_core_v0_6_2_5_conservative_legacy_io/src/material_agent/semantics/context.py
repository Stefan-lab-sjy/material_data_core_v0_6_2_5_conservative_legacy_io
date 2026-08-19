from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


BAND_OUTPUT_NAMES = {
    "band.dat",
    "band_reformatted.dat",
    "reformatted_band.dat",
    "band_gap",
    "klines.dat",
    "klabels",
}
DOS_OUTPUT_NAMES = {"tdos.dat", "itdos.dat", "dos.dat"}
ELECTRONIC_OUTPUT_NAMES = {
    "outcar", "vasprun.xml", "oszicar", "eigenval", "doscar", "procar",
    "chgcar", "wavecar", "locpot",
}


@dataclass(frozen=True)
class ClassificationContext:
    """Scientific evidence used to decide file role inside one Calculation."""

    workflow: str = "unknown"
    calc_type: str = "unknown"
    functional: str | None = None
    soc: bool | None = None
    incar_tags: dict[str, Any] = field(default_factory=dict)
    kpoints_mode: str = "unknown"
    filenames: frozenset[str] = field(default_factory=frozenset)
    folder_name: str = ""
    evidence: tuple[str, ...] = ()

    def has(self, filename: str) -> bool:
        return filename.casefold() in self.filenames

    @property
    def is_band(self) -> bool:
        return self.workflow in {"band", "band_structure", "hse_band"}

    @property
    def is_hybrid(self) -> bool:
        return self.functional in {"HSE06", "hybrid"}


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().upper() in {"TRUE", ".TRUE.", "T", "YES", "1"}
    return bool(value)


def _functional(tags: dict[str, Any]) -> str | None:
    if _truthy(tags.get("LHFCALC")):
        hfscreen = tags.get("HFSCREEN")
        if isinstance(hfscreen, (int, float)) and abs(float(hfscreen) - 0.2) < 0.05:
            return "HSE06"
        return "hybrid"
    if tags.get("METAGGA"):
        return str(tags.get("METAGGA"))
    if str(tags.get("GGA", "")).upper() == "PE":
        return "PBE"
    if tags.get("GGA"):
        return str(tags.get("GGA"))
    return None


def _soc(tags: dict[str, Any]) -> bool | None:
    if "LSORBIT" not in tags:
        return None
    return _truthy(tags.get("LSORBIT"))


def build_vasp_context(
    folder: str | Path,
    *,
    paths: Iterable[Path] | None = None,
    incar_meta: dict[str, Any] | None = None,
    kpoints_meta: dict[str, Any] | None = None,
    inferred: dict[str, Any] | None = None,
) -> ClassificationContext:
    """Build workflow context without relying on folder names as truth.

    v0.6.2.5 preserves the established workflow inference and distinguishes ionic relaxation from molecular dynamics before
    applying the static/band/DOS fallbacks. INCAR evidence remains primary; file
    combinations are only a fallback when users omit explicit default tags.
    """

    folder = Path(folder).expanduser().resolve()
    tags = dict((incar_meta or {}).get("tags", {}) or {})
    kpoints_meta = kpoints_meta or {}
    inferred = inferred or {}

    if paths is None:
        try:
            paths = [p for p in folder.iterdir() if p.is_file()]
        except OSError:
            paths = []
    names = frozenset(Path(p).name.casefold() for p in paths)

    functional = inferred.get("functional") or _functional(tags)
    soc = inferred.get("soc") if "soc" in inferred else _soc(tags)
    base_calc_type = str(inferred.get("calc_type") or "unknown")
    k_mode = str(kpoints_meta.get("mode") or "unknown")
    evidence: list[str] = []

    nsw = tags.get("NSW")
    ibrion = tags.get("IBRION")

    # Strong, task-specific INCAR evidence first.
    if _truthy(tags.get("LOPTICS")):
        workflow = "optics"
        evidence.append("INCAR:LOPTICS=true")
    elif tags.get("LEPSILON") is True or tags.get("LCALCEPS") is True:
        workflow = "dielectric"
        evidence.append("INCAR:LEPSILON/LCALCEPS")
    elif ibrion in {5, 6, 7, 8}:
        workflow = "phonon"
        evidence.append("INCAR:IBRION=5..8")
    elif isinstance(nsw, int) and nsw > 0 and ibrion == 0:
        # IBRION=0 means the ionic steps are molecular-dynamics steps, not a
        # geometry optimization. NSW therefore counts MD steps in this context.
        workflow = "molecular_dynamics"
        evidence.append(f"INCAR:NSW={nsw}>0")
        evidence.append("INCAR:IBRION=0")
        for key in ("POTIM", "MDALGO", "TEBEG", "TEEND", "SMASS"):
            if key in tags:
                evidence.append(f"INCAR:{key}={tags.get(key)}")
    elif isinstance(nsw, int) and nsw > 0:
        workflow = "geometry_optimization"
        evidence.append(f"INCAR:NSW={nsw}>0")
        if isinstance(ibrion, int):
            evidence.append(f"INCAR:IBRION={ibrion}")
        if "ISIF" in tags:
            evidence.append(f"INCAR:ISIF={tags.get('ISIF')}")
        if "EDIFFG" in tags:
            evidence.append(f"INCAR:EDIFFG={tags.get('EDIFFG')}")
    else:
        band_markers = sorted(names & BAND_OUTPUT_NAMES)
        pattern_band = any(n.startswith("pband") and n.endswith(".dat") for n in names)
        has_band_path = "kpath.in" in names or k_mode == "line"
        if has_band_path or band_markers or pattern_band:
            workflow = "hse_band" if functional in {"HSE06", "hybrid"} else "band_structure"
            if "kpath.in" in names:
                evidence.append("file:KPATH.in")
            if k_mode == "line":
                evidence.append("KPOINTS:line-mode")
            if band_markers:
                evidence.append("band_outputs:" + ",".join(band_markers[:4]))
            if pattern_band:
                evidence.append("file:PBAND*.dat")
            if workflow == "hse_band":
                evidence.append("INCAR:hybrid-functional")
        else:
            dos_markers = sorted(names & DOS_OUTPUT_NAMES)
            pattern_dos = any(n.startswith("pdos") and n.endswith(".dat") for n in names)
            incar_dos = tags.get("ICHARG") == 11 and (
                tags.get("LORBIT") is not None or tags.get("NEDOS") is not None
            )
            if incar_dos or dos_markers or pattern_dos:
                workflow = "dos"
                if incar_dos:
                    evidence.append("INCAR:ICHARG=11+DOS-tags")
                if dos_markers:
                    evidence.append("dos_outputs:" + ",".join(dos_markers[:4]))
                if pattern_dos:
                    evidence.append("file:PDOS*.dat")
            elif base_calc_type == "relax":
                workflow = "geometry_optimization"
                evidence.append("infer_calculation:relax")
            elif base_calc_type == "static":
                workflow = "static_scf"
                evidence.append("infer_calculation:static")
            elif base_calc_type == "band":
                workflow = "band_structure"
                evidence.append("infer_calculation:band")
            elif base_calc_type not in {"", "unknown"}:
                workflow = base_calc_type
                evidence.append("infer_calculation:" + base_calc_type)
            elif nsw == 0 or ibrion == -1:
                workflow = "static_scf"
                evidence.append("INCAR:static-flags")
            elif (names & ELECTRONIC_OUTPUT_NAMES) and not (isinstance(nsw, int) and nsw > 0):
                # Many real INCARs omit default NSW=0 / IBRION=-1.  Completed
                # electronic outputs plus no ionic-relaxation evidence provide a
                # useful, auditable fallback rather than leaving routine SCF runs
                # permanently unknown.
                workflow = "static_scf"
                evidence.append("files:electronic_outputs")
                evidence.append("no:ionic_relaxation_evidence")
            else:
                workflow = "unknown"

    legacy_map = {
        "geometry_optimization": "relax",
        "static_scf": "static",
        "band_structure": "band",
        "hse_band": "band",
        "molecular_dynamics": "md",
    }
    contextual_calc_type = legacy_map.get(workflow, workflow)

    return ClassificationContext(
        workflow=workflow,
        calc_type=contextual_calc_type,
        functional=functional,
        soc=soc,
        incar_tags=tags,
        kpoints_mode=k_mode,
        filenames=names,
        folder_name=folder.name,
        evidence=tuple(evidence),
    )
