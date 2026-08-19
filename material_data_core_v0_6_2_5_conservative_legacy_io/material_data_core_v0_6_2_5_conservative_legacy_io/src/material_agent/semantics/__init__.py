"""Context-aware semantics for scientific calculation files.

v0.6.2.5 keeps physical storage unchanged and classifies the relationship between a
stored file and one Calculation.  The public helpers here intentionally return
plain dictionaries so older callers remain easy to integrate.
"""

from .context import ClassificationContext, build_vasp_context
from .rules import (
    CLASSIFICATION_VERSION,
    VALID_ROLES,
    classify_calculation_file,
    semantic_identity,
)

__all__ = [
    "CLASSIFICATION_VERSION",
    "VALID_ROLES",
    "ClassificationContext",
    "build_vasp_context",
    "classify_calculation_file",
    "semantic_identity",
]
