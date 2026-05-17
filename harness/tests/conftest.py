"""Conftest for survey gate tests — patches broken import chain.

Must run at module level (before collection) because the import chain is
triggered during test module import, not during fixture setup.
"""

import sys
import types

if "research.evaluator" not in sys.modules:
    _mod = types.ModuleType("research.evaluator")
    _mod.audit_sources = lambda *a, **k: {}
    sys.modules["research.evaluator"] = _mod
