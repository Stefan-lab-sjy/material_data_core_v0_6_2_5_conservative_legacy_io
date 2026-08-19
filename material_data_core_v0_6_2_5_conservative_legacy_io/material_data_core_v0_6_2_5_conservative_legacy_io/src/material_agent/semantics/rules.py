from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from .context import ClassificationContext

CLASSIFICATION_VERSION = "0.6.2.5"
VALID_ROLES = {"input", "output", "reference", "intermediate", "auxiliary", "unknown"}

# semantic_type answers "what is this file?".  Role answers "what does it do in
# this Calculation?" and is decided later using context.
#
# Tuple: semantic_type, retention_class, default_role, default_confidence, reason
_EXACT_IDENTITIES: dict[str, tuple[str, str, str, float, str]] = {
    # VASP native inputs
    "incar": ("parameters", "core", "input", 1.00, "native VASP control input"),
    "kpoints": ("kpoints", "core", "input", 1.00, "native VASP k-point input"),
    "poscar": ("structure", "core", "input", 1.00, "native VASP structure input"),
    "potcar": ("potential", "conditional", "input", 1.00, "native VASP potential input"),

    # VASP native outputs
    "outcar": ("main_output", "core", "output", 1.00, "native VASP main output"),
    "contcar": ("structure", "core", "output", 1.00, "native VASP final structure output"),
    "oszicar": ("convergence_log", "core", "output", 1.00, "native VASP convergence output"),
    "xdatcar": ("trajectory", "conditional", "output", 0.99, "native VASP trajectory output"),
    "chgcar": ("charge_density", "conditional", "output", 0.88, "normally written by VASP; may also seed later runs"),
    "chg": ("charge_density", "large", "output", 0.88, "normally written by VASP; may also seed later runs"),
    "wavecar": ("wavefunction", "large", "output", 0.88, "normally written by VASP; may also seed later runs"),
    "waveder": ("wavefunction_derivative", "large", "output", 0.96, "VASP wavefunction-derivative output"),
    "doscar": ("density_of_states", "conditional", "output", 0.99, "native VASP DOS output"),
    "eigenval": ("eigenvalues", "conditional", "output", 0.99, "native VASP eigenvalue output"),
    "procar": ("projected_bands", "conditional", "output", 0.99, "native VASP projection output"),
    "locpot": ("local_potential", "conditional", "output", 0.99, "native VASP local-potential output"),
    "ibzkpt": ("irreducible_kpoints", "auxiliary", "output", 0.98, "native VASP generated irreducible k-points"),
    "pcdat": ("pair_correlation", "auxiliary", "output", 0.96, "native VASP pair-correlation output"),
    "report": ("runtime_log", "auxiliary", "output", 0.96, "native VASP runtime output"),
    "elfcar": ("electron_localization", "conditional", "output", 0.99, "native VASP ELF output"),
    "aeccar0": ("augmentation_charge", "large", "output", 0.99, "native VASP all-electron charge output"),
    "aeccar1": ("augmentation_charge", "large", "output", 0.99, "native VASP all-electron charge output"),
    "aeccar2": ("augmentation_charge", "large", "output", 0.99, "native VASP all-electron charge output"),
    "vasprun.xml": ("structured_output", "core", "output", 1.00, "native VASP structured output"),

    # VASPKIT / workflow files. Context may replace the default role below.
    "kpath.in": ("band_kpath", "auxiliary", "reference", 0.72, "band-path definition; role depends on workflow stage"),
    "high_symmetry_points": ("high_symmetry_points", "auxiliary", "reference", 0.72, "high-symmetry-point reference; role depends on workflow stage"),
    "primcell.vasp": ("primitive_structure", "auxiliary", "intermediate", 0.90, "standardized primitive structure produced during k-path preparation"),
    "transmat.in": ("transformation_matrix", "auxiliary", "input", 0.98, "explicit transformation-matrix input"),
    "kpoints_mapping_table.in": ("kpoint_mapping_table", "auxiliary", "input", 0.98, "explicit k-point mapping input"),
    "fermi_energy.in": ("fermi_energy_override", "auxiliary", "input", 0.99, "explicit Fermi-energy override input"),

    "band.dat": ("band_structure_data", "auxiliary", "output", 0.99, "band-structure post-processing output"),
    "band_reformatted.dat": ("band_structure_data", "auxiliary", "output", 0.99, "reformatted band-structure output"),
    "reformatted_band.dat": ("band_structure_data", "auxiliary", "output", 0.99, "reformatted band-structure output"),
    "band_gap": ("band_gap_result", "auxiliary", "output", 0.99, "band-gap analysis output"),
    "fermi_energy": ("fermi_energy", "auxiliary", "output", 0.82, "Fermi-energy result file; no .in suffix"),
    "klabels": ("kpoint_labels", "auxiliary", "output", 0.98, "band-plot label output"),
    "klines.dat": ("band_kpath_data", "auxiliary", "output", 0.98, "band-plot k-line output"),
    "tdos.dat": ("total_dos", "auxiliary", "output", 0.99, "total DOS post-processing output"),
    "itdos.dat": ("integrated_total_dos", "auxiliary", "output", 0.99, "integrated total DOS output"),
    "dos.dat": ("total_dos", "auxiliary", "output", 0.96, "DOS post-processing output"),
    "symmetry": ("symmetry_analysis", "auxiliary", "output", 0.88, "symmetry-analysis result"),
    "pot": ("potential_profile", "auxiliary", "output", 0.78, "potential post-processing result"),
    "selected_atom_list": ("selection_record", "auxiliary", "output", 0.95, "post-processing selection record"),
}

# pattern, semantic_type, retention, default_role, confidence, reason
_PATTERN_IDENTITIES: list[tuple[str, str, str, str, float, str]] = [
    ("pdos*.dat", "projected_dos", "auxiliary", "output", 0.98, "projected DOS family"),
    ("pband*.dat", "projected_band_data", "auxiliary", "output", 0.98, "projected band family"),
    ("band_*.dat", "band_structure_data", "auxiliary", "output", 0.95, "band-data family"),
    ("dos_*.dat", "density_of_states_data", "auxiliary", "output", 0.92, "DOS-data family"),
]


def semantic_identity(filename: str) -> dict[str, Any]:
    key = Path(filename).name.casefold()
    exact = _EXACT_IDENTITIES.get(key)
    if exact:
        semantic, retention, role, confidence, reason = exact
        return {
            "semantic_type": semantic,
            "retention_class": retention,
            "default_role": role,
            "default_confidence": confidence,
            "identity_reason": reason,
            "identity_source": "exact_rule",
        }
    for pattern, semantic, retention, role, confidence, reason in _PATTERN_IDENTITIES:
        if fnmatchcase(key, pattern):
            return {
                "semantic_type": semantic,
                "retention_class": retention,
                "default_role": role,
                "default_confidence": confidence,
                "identity_reason": reason,
                "identity_source": "pattern_rule",
            }
    return {
        "semantic_type": "unknown",
        "retention_class": "auxiliary",
        "default_role": "unknown",
        "default_confidence": 0.20,
        "identity_reason": "no known semantic rule",
        "identity_source": "fallback",
    }


def _context_role(identity: dict[str, Any], filename: str, context: ClassificationContext | None) -> dict[str, Any]:
    role = str(identity["default_role"])
    confidence = float(identity["default_confidence"])
    reason = str(identity["identity_reason"])
    source = str(identity["identity_source"])
    key = Path(filename).name.casefold()

    if context is None:
        return {"role": role, "role_confidence": confidence, "role_reason": reason, "role_source": source}

    semantic = identity["semantic_type"]
    workflow = context.workflow
    tags = context.incar_tags

    # --- Context-sensitive band inputs -------------------------------------
    if semantic == "band_kpath":
        if workflow in {"band", "band_structure", "hse_band"}:
            role = "input"
            confidence = 0.99
            reason = f"{workflow} workflow uses KPATH.in as band-path input/reference"
            source = "context_rule"
        else:
            role = "reference"
            confidence = 0.76
            reason = "KPATH.in is recognized, but current Calculation is not confidently a band workflow"
            source = "context_rule"

    elif semantic == "high_symmetry_points":
        if workflow in {"band", "band_structure", "hse_band"}:
            # In a completed band Calculation directory this file is commonly
            # carried forward from k-path preparation and used as an input/reference
            # artifact.  We choose primary role=input for the user's workflow while
            # retaining the explanation so the decision is auditable.
            role = "input"
            confidence = 0.90
            reason = f"{workflow} context: high-symmetry-point definition is treated as an input/reference artifact"
            source = "context_rule"
        else:
            role = "reference"
            confidence = 0.80
            reason = "high-symmetry-point definition is a reference artifact outside a confirmed band Calculation"
            source = "context_rule"

    # Explicit .in files stay inputs regardless of workflow.
    elif key.endswith(".in") and semantic != "unknown":
        role = "input"
        confidence = max(confidence, 0.96)
        reason = "recognized explicit .in workflow input"
        source = "context_rule"

    # Historical-folder imports are completed-directory snapshots.  ICHARG/ISTART
    # may *suggest* that CHGCAR/WAVECAR were dependencies, but the final folder
    # cannot prove those files existed before the run.  Keep their observable
    # role as output unless a future pre-run input manifest or a user override
    # provides direct provenance.
    elif key == "chgcar" and semantic == "charge_density" and tags.get("ICHARG") in {1, 11}:
        role = "output"
        confidence = max(confidence, 0.90)
        reason = (
            f"completed-folder snapshot: INCAR ICHARG={tags.get('ICHARG')} may imply a restart/non-SCF "
            "dependency, but without a pre-run input manifest CHGCAR is conservatively kept as output"
        )
        source = "conservative_history_rule"

    elif semantic == "wavefunction" and isinstance(tags.get("ISTART"), int) and tags.get("ISTART", 0) > 0:
        role = "output"
        confidence = max(confidence, 0.90)
        reason = (
            f"completed-folder snapshot: INCAR ISTART={tags.get('ISTART')} may imply a restart dependency, "
            "but without a pre-run input manifest WAVECAR is conservatively kept as output"
        )
        source = "conservative_history_rule"

    # Unrecognized files remain unknown instead of being forced into auxiliary.
    elif semantic == "unknown":
        role = "unknown"
        confidence = 0.20
        reason = "no semantic or workflow rule matched; classification intentionally left unknown"
        source = "fallback"

    return {"role": role, "role_confidence": confidence, "role_reason": reason, "role_source": source}


def classify_calculation_file(filename: str, context: ClassificationContext | None = None) -> dict[str, Any]:
    identity = semantic_identity(filename)
    role_info = _context_role(identity, filename, context)
    return {
        "role": role_info["role"],
        "semantic_type": identity["semantic_type"],
        "retention_class": identity["retention_class"],
        "role_confidence": round(float(role_info["role_confidence"]), 3),
        "role_reason": role_info["role_reason"],
        "role_source": role_info["role_source"],
        "classification_version": CLASSIFICATION_VERSION,
    }
