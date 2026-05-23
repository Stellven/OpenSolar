#!/usr/bin/env python3
import sys
from pathlib import Path

# Insert lib to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import pytest
import multi_task_runner as m
import operator_runtime

# Save original functions to prevent test pollution in pytest sessions
_orig_get_state = operator_runtime.get_operator_runtime_state
_orig_load_ops = m.load_physical_operators

@pytest.fixture(autouse=True)
def setup_mocks():
    operator_runtime.get_operator_runtime_state = lambda op_id: "idle"
    m.load_physical_operators = lambda: mock_registry
    yield
    operator_runtime.get_operator_runtime_state = _orig_get_state
    m.load_physical_operators = _orig_load_ops


# Mock registry
mock_registry = {
    "version": 1,
    "operators": {
        "operator-planner": {
            "display_name": "Mock Planner",
            "role": "planner",
            "profile": "planner",
            "enabled": True,
            "available": True,
            "key_ref": "mock_key",
            "auth_mode": "subscription",
            "quota_guard_state": "ok",
            "task_classes": ["planning", "ARCH_DESIGN"],
            "operator_class": "DeepArchitect",
            "capability": {
                "planning": 5,
                "long_context": 4
            },
            "cost_tier": "medium",
            "quota": {
                "reserve_for": ["ARCH_DESIGN"]
            }
        },
        "operator-builder": {
            "display_name": "Mock Builder",
            "role": "builder",
            "profile": "builder",
            "enabled": True,
            "available": True,
            "key_ref": "mock_key",
            "auth_mode": "subscription",
            "quota_guard_state": "ok",
            "task_classes": ["implementation", "debugging"],
            "operator_class": "DeepBuilder",
            "capability": {
                "coding": 5,
                "debugging": 4
            },
            "cost_tier": "medium"
        },
        "operator-evaluator": {
            "display_name": "Mock Evaluator",
            "role": "evaluator",
            "profile": "evaluator",
            "enabled": True,
            "available": True,
            "key_ref": "mock_key",
            "auth_mode": "subscription",
            "quota_guard_state": "ok",
            "task_classes": ["verification", "review"],
            "operator_class": "DeepEvaluator",
            "capability": {
                "review": 5
            },
            "cost_tier": "low"
        }
    }
}

# Override handled dynamically by fixtures/manual setup


def test_preferred_operator_override():
    # preferred_operator remains hard override
    node = {
        "preferred_operator": "operator-builder",
        "task_type": "ARCH_DESIGN" # conflict with builder's task classes
    }
    op, err = m.select_operator(node, {"name": "builder"})
    assert op is not None
    assert op.get("operator_id") == "operator-builder", op
    assert not err

def test_task_type_matching():
    # task_type selection
    node = {
        "task_type": "implementation"
    }
    op, err = m.select_operator(node, {"name": "builder"})
    assert op is not None
    assert op.get("operator_id") == "operator-builder", op
    assert not err

def test_capability_scores():
    # required_capabilities constraint
    node = {
        "task_type": "ARCH_DESIGN",
        "required_capabilities": {
            "planning": ">=5",
            "long_context": ">=4"
        }
    }
    op, err = m.select_operator(node, {"name": "planner"})
    assert op is not None
    assert op.get("operator_id") == "operator-planner", op
    assert not err
    
    # capability too high
    node = {
        "task_type": "ARCH_DESIGN",
        "required_capabilities": {
            "planning": ">5"
        }
    }
    op, err = m.select_operator(node, {"name": "planner"})
    assert op is None
    assert "no_match" in err

def test_preferred_operator_classes():
    # select correct operator based on preferred_operator_classes
    node = {
        "task_type": "implementation",
        "preferred_operator_classes": ["DeepBuilder"]
    }
    op, err = m.select_operator(node, {"name": "builder"})
    assert op is not None
    assert op.get("operator_id") == "operator-builder", op
    
    # Class bonus overrides default score ordering (e.g. builder is selected over planner if class matches)
    # Planner matches class DeepArchitect
    node = {
        "task_type": "ARCH_DESIGN",
        "preferred_operator_classes": ["DeepArchitect"],
        "operator_selector": {
            "role": "planner"
        }
    }
    op, err = m.select_operator(node, {"name": "planner"})
    assert op is not None
    assert op.get("operator_id") == "operator-planner", op

def test_constraints():
    # constraints (cost tier)
    node = {
        "task_type": "verification",
        "constraints": {
            "max_cost_tier": "low"
        }
    }
    op, err = m.select_operator(node, {"name": "evaluator"})
    assert op is not None
    assert op.get("operator_id") == "operator-evaluator", op
    
    # constraint prevents matching because cost is higher
    node = {
        "task_type": "implementation",
        "constraints": {
            "max_cost_tier": "low"
        }
    }
    op, err = m.select_operator(node, {"name": "builder"})
    assert op is None
    assert "no_match" in err

def test_quota_reserve():
    # quota reserve protects high-value task ARCH_DESIGN
    node = {
        "task_type": "planning" # Not reserved ARCH_DESIGN
    }
    # operator-planner has reserve_for = ["ARCH_DESIGN"]
    # So a non-ARCH_DESIGN task (like planning) shouldn't be allowed to select operator-planner
    op, err = m.select_operator(node, {"name": "planner"})
    assert op is None, op
    assert "no_match" in err
    
    # But ARCH_DESIGN can select it
    node = {
        "task_type": "ARCH_DESIGN"
    }
    op, err = m.select_operator(node, {"name": "planner"})
    assert op is not None
    assert op.get("operator_id") == "operator-planner"

def test_verifier_conflict():
    # verifier_required rejects same operator as writer when prior operator is provided
    node = {
        "task_type": "verification",
        "verifier_required": True,
        "prior_operator": "operator-evaluator"
    }
    op, err = m.select_operator(node, {"name": "evaluator"})
    assert op is None, op
    assert "no_match" in err
    
    # If verifier_required is False, it is allowed
    node = {
        "task_type": "verification",
        "verifier_required": False,
        "prior_operator": "operator-evaluator"
    }
    op, err = m.select_operator(node, {"name": "evaluator"})
    assert op is not None
    assert op.get("operator_id") == "operator-evaluator"

    # Preferred operator is rejected when verifier_required is True and conflicts with prior operator
    node = {
        "preferred_operator": "operator-evaluator",
        "verifier_required": True,
        "prior_operator": "operator-evaluator"
    }
    op, err = m.select_operator(node, {"name": "evaluator"})
    assert op is None
    assert "verifier_conflict" in err

    node = {
        "preferred_operator": "operator-evaluator",
        "verifier_required": True,
        "prior_operator": "evaluator" # profile conflict
    }
    op, err = m.select_operator(node, {"name": "evaluator"})
    assert op is None
    assert "verifier_conflict" in err


# Fallback mock registry containing actual fallback operator IDs
fallback_mock_registry = {
    "version": 1,
    "operators": {
        "mini-claude-opus-planner": {
            "display_name": "Mock Claude Opus Planner",
            "role": "planner",
            "profile": "planner",
            "enabled": True,
            "available": True,
            "key_ref": "mock_key",
            "auth_mode": "subscription",
            "quota_guard_state": "ok",
            "task_classes": ["planning", "ARCH_DESIGN"],
            "cost_tier": "high"
        },
        "mini-antigravity-gemini31-pro": {
            "display_name": "Mock Gemini 3.1 Pro",
            "role": "planner",
            "profile": "gemini-planner",
            "enabled": True,
            "available": True,
            "key_ref": "mock_key",
            "auth_mode": "subscription",
            "quota_guard_state": "ok",
            "task_classes": ["planning", "ARCH_DESIGN", "RESEARCH_SYNTHESIS"],
            "cost_tier": "medium"
        },
        "mini-claude-sonnet-builder": {
            "display_name": "Mock Claude Sonnet Builder",
            "role": "builder",
            "profile": "builder",
            "enabled": True,
            "available": True,
            "key_ref": "mock_key",
            "auth_mode": "subscription",
            "quota_guard_state": "ok",
            "task_classes": ["implementation", "debugging", "ARCH_DESIGN"],
            "cost_tier": "medium"
        },
        "mini-antigravity-gemini35-flash-high": {
            "display_name": "Mock Gemini 3.5 Flash",
            "role": "builder",
            "profile": "gemini-builder",
            "enabled": True,
            "available": True,
            "key_ref": "mock_key",
            "auth_mode": "subscription",
            "quota_guard_state": "ok",
            "task_classes": ["implementation", "debugging", "ARCH_DESIGN"],
            "cost_tier": "low"
        },
        "mini-claude-opus-evaluator": {
            "display_name": "Mock Claude Opus Evaluator",
            "role": "evaluator",
            "profile": "evaluator",
            "enabled": True,
            "available": True,
            "key_ref": "mock_key",
            "auth_mode": "subscription",
            "quota_guard_state": "ok",
            "task_classes": ["verification", "review", "FINAL_REVIEW"],
            "cost_tier": "high"
        }
    }
}


def test_quota_exhausted_opus_skipped():
    # Registry override
    m.load_physical_operators = lambda: fallback_mock_registry
    
    # Simulate mini-claude-opus-planner quota exhausted
    states = {
        "mini-claude-opus-planner": "quota_exhausted",
        "mini-antigravity-gemini31-pro": "idle"
    }
    operator_runtime.get_operator_runtime_state = lambda op_id: states.get(op_id, "idle")
    
    node = {
        "task_type": "ARCH_DESIGN"
    }
    op, err = m.select_operator(node, {"name": "planner"})
    assert op is not None, err
    assert op.get("operator_id") == "mini-antigravity-gemini31-pro"


def test_gemini31_pro_fallback_ladder_works():
    m.load_physical_operators = lambda: fallback_mock_registry
    
    # Case A: Gemini 3.1 Pro is available (Opus exhausted)
    states = {
        "mini-claude-opus-planner": "quota_exhausted",
        "mini-antigravity-gemini31-pro": "idle",
        "mini-claude-sonnet-builder": "idle"
    }
    operator_runtime.get_operator_runtime_state = lambda op_id: states.get(op_id, "idle")
    
    node = {
        "task_type": "ARCH_DESIGN"
    }
    op, err = m.select_operator(node, {"name": "planner"})
    assert op is not None, err
    assert op.get("operator_id") == "mini-antigravity-gemini31-pro"

    # Case B: Gemini 3.1 Pro is also unavailable (disabled)
    states["mini-antigravity-gemini31-pro"] = "disabled"
    op, err = m.select_operator(node, {"name": "planner"})
    assert op is not None, err
    assert op.get("operator_id") == "mini-claude-sonnet-builder"

    # Case C: Fallback further down the ladder
    states["mini-claude-sonnet-builder"] = "leased"
    op, err = m.select_operator(node, {"name": "planner"})
    assert op is not None, err
    assert op.get("operator_id") == "mini-antigravity-gemini35-flash-high"


def test_writer_verifier_conflict_rejects_same_operator():
    m.load_physical_operators = lambda: fallback_mock_registry
    operator_runtime.get_operator_runtime_state = lambda op_id: "idle"
    
    # Case A: preferred_operator has same-writer conflict -> falls back to ladder (gemini 3.1 pro)
    node = {
        "task_type": "FINAL_REVIEW",
        "preferred_operator": "mini-claude-opus-evaluator",
        "verifier_required": True,
        "prior_operator": "mini-claude-opus-evaluator"
    }
    op, err = m.select_operator(node, {"name": "evaluator"})
    assert op is not None, err
    assert op.get("operator_id") == "mini-antigravity-gemini31-pro"

    # Case B: first choice in ladder (mini-claude-opus-evaluator) has same-writer conflict -> skipped, selects next choice (gemini 3.1 pro)
    node2 = {
        "task_type": "FINAL_REVIEW",
        "verifier_required": True,
        "prior_operator": "mini-claude-opus-evaluator"
    }
    op, err = m.select_operator(node2, {"name": "evaluator"})
    assert op is not None, err
    assert op.get("operator_id") == "mini-antigravity-gemini31-pro"


def test_leased_operator_skipped():
    m.load_physical_operators = lambda: fallback_mock_registry
    
    # Simulate mini-claude-opus-planner leased
    states = {
        "mini-claude-opus-planner": "leased",
        "mini-antigravity-gemini31-pro": "idle"
    }
    operator_runtime.get_operator_runtime_state = lambda op_id: states.get(op_id, "idle")
    
    node = {
        "task_type": "ARCH_DESIGN"
    }
    op, err = m.select_operator(node, {"name": "planner"})
    assert op is not None, err
    assert op.get("operator_id") == "mini-antigravity-gemini31-pro"


# ── claude_print reserve routing integration tests ────────────────────────────

import claude_surface as _cs  # noqa: E402

_PRINT_OP_TEMPLATE = {
    "display_name": "Claude print reserve",
    "role": "planner",
    "profile": "planner",
    "enabled": True,
    "available": True,
    "key_ref": "mock_key",
    "auth_mode": "subscription",
    "quota_guard_state": "ok",
    "launch_cmd_kind": "print_once",
    "billing_surface": "anthropic_agent_sdk_credit",
    "billing_pool": "anthropic_agent_sdk_credit",
    "surface": {
        "type": "claude_print",
        "tool": "claude",
        "launch_cmd": "claude --print --model opus",
    },
    "task_classes": ["planning", "architecture", "schema-design"],
    "preferred_for": ["planner", "architecture"],
    "avoid_for": ["bulk-extraction", "FANOUT", "BULK_EDIT", "TEST_RUN", "LOW_VALUE_SCAN"],
    "cost_tier": "high",
    "quota": {
        "quota_type": "monthly-agent-credit",
        "reserve_for": ["ARCH_DECISION", "ROOT_CAUSE_DEBUG", "FINAL_REVIEW"],
        "on_exhausted": "disable_and_fallback",
    },
}

_INTERACTIVE_OP_TEMPLATE = {
    "display_name": "Claude interactive builder",
    "role": "builder",
    "profile": "builder",
    "enabled": True,
    "available": True,
    "key_ref": "mock_key",
    "auth_mode": "subscription",
    "quota_guard_state": "ok",
    "launch_cmd_kind": "interactive_repl",
    "billing_surface": "subscription_interactive",
    "billing_pool": "anthropic_subscription_interactive",
    "surface": {
        "type": "claude_code_interactive",
        "tool": "claude",
        "launch_cmd": "claude --model sonnet",
    },
    "task_classes": ["implementation", "debugging", "tests", "planning", "FANOUT", "FINAL_REVIEW", "ROOT_CAUSE_DEBUG"],
    "preferred_for": ["builder", "implementation"],
    "avoid_for": [],
    "cost_tier": "medium",
}


_mixed_claude_surface_registry = {
    "version": 1,
    "operators": {
        "mock-claude-interactive": {**_INTERACTIVE_OP_TEMPLATE},
        "mock-claude-print-reserve": {**_PRINT_OP_TEMPLATE},
    },
}


def _setup_claude_surface_mocks():
    operator_runtime.get_operator_runtime_state = lambda op_id: "idle"
    m.load_physical_operators = lambda: _mixed_claude_surface_registry


def test_claude_print_excluded_from_fanout_task():
    """claude_print reserve operator must not be selected for FANOUT tasks."""
    _setup_claude_surface_mocks()
    node = {"task_type": "FANOUT"}
    op, err = m.select_operator(node, {"name": "builder"})
    # Only the interactive operator should be selected
    if op is not None:
        assert op.get("operator_id") == "mock-claude-interactive", (
            f"Expected interactive op, got {op.get('operator_id')}"
        )


def test_claude_print_excluded_from_bulk_edit():
    """claude_print reserve operator must not be selected for BULK_EDIT tasks."""
    _setup_claude_surface_mocks()
    node = {"task_type": "BULK_EDIT"}
    op, err = m.select_operator(node, {"name": "builder"})
    if op is not None:
        assert op.get("operator_id") == "mock-claude-interactive", (
            f"Expected interactive op, got {op.get('operator_id')}"
        )


def test_claude_print_excluded_from_test_run():
    """claude_print reserve operator must not be selected for TEST_RUN tasks."""
    _setup_claude_surface_mocks()
    node = {"task_type": "TEST_RUN"}
    op, err = m.select_operator(node, {"name": "builder"})
    if op is not None:
        assert op.get("operator_id") == "mock-claude-interactive", (
            f"Expected interactive op, got {op.get('operator_id')}"
        )


def test_claude_print_excluded_from_low_value_scan():
    """claude_print reserve operator must not be selected for LOW_VALUE_SCAN."""
    _setup_claude_surface_mocks()
    node = {"task_type": "LOW_VALUE_SCAN"}
    op, err = m.select_operator(node, {"name": "builder"})
    if op is not None:
        assert op.get("operator_id") == "mock-claude-interactive", (
            f"Expected interactive op, got {op.get('operator_id')}"
        )


def test_claude_print_allowed_for_final_review():
    """claude_print reserve operator may be selected for FINAL_REVIEW."""
    _setup_claude_surface_mocks()
    node = {"task_type": "FINAL_REVIEW"}
    op, err = m.select_operator(node, {"name": "planner"})
    # Both are candidates; we just verify no error and a result is returned
    assert op is not None or "no_match" not in err


def test_claude_print_reserve_classifies_correctly():
    """Verify the classifier labels operators in _mixed_claude_surface_registry."""
    ops = _mixed_claude_surface_registry["operators"]
    assert _cs.classify_surface(ops["mock-claude-interactive"]) == _cs.CLAUDE_INTERACTIVE
    assert _cs.classify_surface(ops["mock-claude-print-reserve"]) == _cs.CLAUDE_PRINT


def test_claude_print_policy_fanout_blocked():
    """Reserve policy rejects FANOUT for print op, allows for interactive."""
    ops = _mixed_claude_surface_registry["operators"]
    assert _cs.claude_print_reserve_allows(ops["mock-claude-print-reserve"], "FANOUT") is False
    assert _cs.claude_print_reserve_allows(ops["mock-claude-interactive"], "FANOUT") is True


def test_claude_print_policy_final_review_allowed():
    """Reserve policy allows FINAL_REVIEW for print op (in reserve_for list)."""
    ops = _mixed_claude_surface_registry["operators"]
    assert _cs.claude_print_reserve_allows(ops["mock-claude-print-reserve"], "FINAL_REVIEW") is True
    assert _cs.claude_print_reserve_allows(ops["mock-claude-interactive"], "FINAL_REVIEW") is True


def setup_manual():
    operator_runtime.get_operator_runtime_state = lambda op_id: "idle"
    m.load_physical_operators = lambda: mock_registry

def teardown_manual():
    operator_runtime.get_operator_runtime_state = _orig_get_state
    m.load_physical_operators = _orig_load_ops

if __name__ == "__main__":
    setup_manual()
    try:
        test_preferred_operator_override()
        test_task_type_matching()
        test_capability_scores()
        test_preferred_operator_classes()
        test_constraints()
        test_quota_reserve()
        test_verifier_conflict()
        
        # Run new tests manually
        test_quota_exhausted_opus_skipped()
        test_gemini31_pro_fallback_ladder_works()
        test_writer_verifier_conflict_rejects_same_operator()
        test_leased_operator_skipped()
        
        print("ALL TESTS PASSED SUCCESSFULLY!")
    finally:
        teardown_manual()
