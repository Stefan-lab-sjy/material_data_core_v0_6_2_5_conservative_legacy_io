from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .utils import formula_from_symbols_counts


def _strip_inline_comment(value: str) -> str:
    """Remove common INCAR inline comments while preserving the value itself."""
    candidates = [i for i in (value.find('!'), value.find('#')) if i >= 0]
    if candidates:
        value = value[:min(candidates)]
    return value.strip()


def _split_semicolon_segments(line: str) -> list[str]:
    """Split INCAR assignments on semicolons outside parenthetical notes.

    Real laboratory INCAR files sometimes include human-readable notes such as
    ``IBRION = 2 (Algorithm: 0-MD; 1-Quasi-New; 2-CG)``.  A naive ``split(';')``
    would break the annotation into fake assignments.  Parentheses are not part
    of normal scalar tag syntax, so we treat semicolons inside them as annotation
    text and preserve the segment.
    """
    segments: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in line:
        if ch == '(':
            depth += 1
        elif ch == ')' and depth > 0:
            depth -= 1
        if ch == ';' and depth == 0:
            segment = ''.join(buf).strip()
            if segment:
                segments.append(segment)
            buf = []
        else:
            buf.append(ch)
    segment = ''.join(buf).strip()
    if segment:
        segments.append(segment)
    return segments


def _separate_parenthetical_annotation(raw_value: str) -> tuple[str, str | None]:
    """Separate a trailing human note from the scientific INCAR value.

    Examples::

        ``100 (Max ionic steps)`` -> ``("100", "Max ionic steps")``
        ``.FALSE. (Projection operators: automatic)`` ->
        ``(".FALSE.", "Projection operators: automatic")``

    Only a *trailing* parenthesized suffix preceded by whitespace is treated as
    annotation.  The raw value is retained separately by :func:`parse_incar`.
    """
    value = raw_value.strip()
    match = re.fullmatch(r"(.+?)\s+\((.*)\)\s*", value)
    if not match:
        return value, None
    scientific = match.group(1).strip()
    annotation = match.group(2).strip()
    return scientific, annotation or None


def parse_scalar(text: str) -> Any:
    s = text.strip()
    upper = s.upper()
    if upper in {".TRUE.", "TRUE", "T"}:
        return True
    if upper in {".FALSE.", "FALSE", "F"}:
        return False
    if re.fullmatch(r"[+-]?\d+", s):
        try:
            return int(s)
        except ValueError:
            pass
    if re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?", s):
        try:
            return float(s)
        except ValueError:
            pass
    return s


def parse_incar(path: Path) -> dict[str, Any]:
    """Parse practical INCAR syntax while preserving source fidelity.

    v0.6.2.5 retains support for both semicolon-separated tags and the annotation-heavy
    style used in many hand-maintained INCAR templates, for example::

        IBRION = 2        (Algorithm: 0-MD, 1-Quasi-New, 2-CG)
        NSW    = 100      (Max ionic steps)
        EDIFFG = -2E-02   (Ionic convergence, eV/AA)

    The parenthetical text is *not* scientific evidence.  ``tags`` contains the
    parsed VASP value (2, 100, -0.02), while ``raw_tags`` retains the exact
    right-hand-side text and ``annotations`` retains the human note.  This keeps
    workflow inference based on actual tag values rather than copied comments.
    """
    tags: dict[str, Any] = {}
    raw_tags: dict[str, str] = {}
    annotations: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {"tags": tags, "raw_tags": raw_tags, "annotations": annotations}

    for raw_line in text.splitlines():
        # ! and # are native/comment conventions.  Parenthetical descriptions are
        # handled separately because many real templates place them after values.
        line = _strip_inline_comment(raw_line.strip())
        if not line:
            continue
        for segment in _split_semicolon_segments(line):
            if not segment or '=' not in segment:
                continue
            key, raw_value = segment.split('=', 1)
            key = key.strip().upper()
            raw_value = raw_value.strip()
            if not key or not raw_value:
                continue

            scientific_value, annotation = _separate_parenthetical_annotation(raw_value)
            if not scientific_value:
                continue

            raw_tags[key] = raw_value
            tags[key] = parse_scalar(scientific_value)
            if annotation is not None:
                annotations[key] = annotation

    return {"tags": tags, "raw_tags": raw_tags, "annotations": annotations}


def parse_kpoints(path: Path) -> dict[str, Any]:
    try:
        lines = [x.strip() for x in path.read_text(encoding='utf-8', errors='ignore').splitlines()]
    except OSError:
        return {}
    mode = "unknown"
    joined = "\n".join(lines[:8]).lower()
    if "line-mode" in joined or "line mode" in joined:
        mode = "line"
    elif any(x.lower().startswith('g') for x in lines[2:4]):
        mode = "gamma"
    elif any(x.lower().startswith('m') for x in lines[2:4]):
        mode = "monkhorst-pack"
    return {"mode": mode, "comment": lines[0] if lines else ""}


def parse_poscar(path: Path) -> dict[str, Any]:
    try:
        lines = [x.strip() for x in path.read_text(encoding='utf-8', errors='ignore').splitlines() if x.strip()]
    except OSError:
        return {}
    if len(lines) < 7:
        return {}
    symbols = lines[5].split()
    try:
        counts = [int(x) for x in lines[6].split()]
    except ValueError:
        return {"comment": lines[0] if lines else ""}
    if not symbols or any(re.fullmatch(r"[+-]?\d+", s) for s in symbols):
        return {"comment": lines[0] if lines else "", "atom_count": sum(counts) if counts else None}
    formula = formula_from_symbols_counts(symbols, counts)
    result: dict[str, Any] = {
        "comment": lines[0],
        "elements": symbols,
        "counts": counts,
        "atom_count": sum(counts),
        "formula": formula,
    }
    try:
        result["scale"] = float(lines[1].split()[0])
        result["lattice"] = [[float(v) for v in lines[i].split()[:3]] for i in range(2, 5)]
    except Exception:
        pass
    return result


def infer_calculation(incar_meta: dict[str, Any], kpoints_meta: dict[str, Any]) -> dict[str, Any]:
    """Infer the backward-compatible coarse calculation type.

    `calc_type` intentionally stays compatible with the v0.5/v0.6 database
    vocabulary (relax/static/band/dos/...), while the richer `workflow` exposed
    by semantics.context uses names such as geometry_optimization and static_scf.
    """
    tags = incar_meta.get("tags", {}) if isinstance(incar_meta, dict) else {}
    calc_type = "unknown"
    if tags.get("LOPTICS") is True:
        calc_type = "optics"
    elif tags.get("LEPSILON") is True or tags.get("LCALCEPS") is True:
        calc_type = "dielectric"
    elif tags.get("IBRION") in {5, 6, 7, 8}:
        calc_type = "phonon"
    elif isinstance(tags.get("NSW"), int) and tags.get("NSW", 0) > 0 and tags.get("IBRION") == 0:
        calc_type = "md"
    elif isinstance(tags.get("NSW"), int) and tags.get("NSW", 0) > 0:
        calc_type = "relax"
    elif kpoints_meta.get("mode") == "line":
        calc_type = "band"
    elif tags.get("ICHARG") == 11 and (tags.get("LORBIT") is not None or tags.get("NEDOS") is not None):
        calc_type = "dos"
    elif tags.get("NSW") == 0 or tags.get("IBRION") == -1:
        calc_type = "static"

    functional: str | None = None
    if tags.get("LHFCALC") is True:
        hfscreen = tags.get("HFSCREEN")
        if isinstance(hfscreen, (int, float)) and abs(float(hfscreen) - 0.2) < 0.05:
            functional = "HSE06"
        else:
            functional = "hybrid"
    elif tags.get("METAGGA"):
        functional = str(tags.get("METAGGA"))
    elif str(tags.get("GGA", "")).upper() == "PE":
        functional = "PBE"
    elif tags.get("GGA"):
        functional = str(tags.get("GGA"))

    soc: bool | None = None
    if "LSORBIT" in tags:
        soc = bool(tags.get("LSORBIT"))

    return {"calc_type": calc_type, "functional": functional, "soc": soc}


def detect_completion(folder: Path) -> str:
    outcar = folder / "OUTCAR"
    if outcar.exists():
        try:
            with outcar.open('rb') as f:
                size = outcar.stat().st_size
                f.seek(max(0, size - 256 * 1024))
                tail = f.read().decode('utf-8', errors='ignore')
            if "General timing and accounting informations" in tail:
                return "completed"
        except OSError:
            pass
    vr = folder / "vasprun.xml"
    if vr.exists():
        try:
            with vr.open('rb') as f:
                size = vr.stat().st_size
                f.seek(max(0, size - 64 * 1024))
                tail = f.read().decode('utf-8', errors='ignore')
            if "</modeling>" in tail:
                return "completed"
        except OSError:
            pass
    return "imported"
