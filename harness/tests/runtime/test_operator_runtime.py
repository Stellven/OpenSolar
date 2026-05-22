#!/usr/bin/env python3
"""test_operator_runtime.py — S6 Control Plane: Unit tests for operator runtime and leases."""

import os
import sys
import tempfile
import time
import json
import pytest
from pathlib import Path

# Insert lib path so we can import operator_runtime
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import operator_runtime as optime


@pytest.fixture(autouse=True)
def setup_teardown_env(monkeypatch):
    """Fixture to isolate run directories and environmental variables for test execution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        monkeypatch.setattr(optime, "OPERATOR_LEASE_DIR", tmp_path / "run" / "operator-leases")
        monkeypatch.setattr(optime, "OPERATOR_STATUS_DIR", tmp_path / "run" / "operator-status")
        
        # Point the registry to the real config in the harness dir
        monkeypatch.setattr(optime, "PHYSICAL_OPERATORS_PATH", ROOT / "config" / "physical-operators.json")
        
        yield


def test_operator_config_loading():
    """Verify registry loading works for known operators."""
    config = optime.get_operator_config("mini-claude-sonnet-builder")
    assert config is not None
    assert config["display_name"] == "Mac mini Claude Sonnet builder"
    assert config["enabled"] is True

    # Test unknown operator
    assert optime.get_operator_config("nonexistent-operator") is None


def test_operator_lease_lifecycle():
    """Test lease acquisition, update state, and release."""
    operator_id = "mini-claude-sonnet-builder"
    
    # 1. Ensure initially idle
    assert optime.get_operator_runtime_state(operator_id) == "idle"
    assert optime.get_operator_lease(operator_id) is None
    
    # 2. Acquire lease
    lease = optime.acquire_operator_lease(
        operator_id=operator_id,
        task_id="T001",
        sprint_id="sprint-test",
        node_id="N2",
        ttl_seconds=60,
        initial_state="leased"
    )
    
    assert lease["operator_id"] == operator_id
    assert lease["task_id"] == "T001"
    assert lease["state"] == "leased"
    
    # Check runtime state classified as leased
    assert optime.get_operator_runtime_state(operator_id) == "leased"
    
    # 3. Duplicate acquisition should fail
    with pytest.raises(RuntimeError, match="Duplicate active lease"):
        optime.acquire_operator_lease(
            operator_id=operator_id,
            task_id="T002",
            sprint_id="sprint-test",
            node_id="N2",
            ttl_seconds=60
        )
        
    # 4. Update lease state
    updated_lease = optime.update_operator_lease_state(operator_id, "running")
    assert updated_lease["state"] == "running"
    assert optime.get_operator_runtime_state(operator_id) == "running"
    
    # 5. Release lease
    released = optime.release_operator_lease(operator_id)
    assert released is True
    assert optime.get_operator_lease(operator_id) is None
    assert optime.get_operator_runtime_state(operator_id) == "idle"


def test_lease_expiration():
    """Verify expired leases are treated as inactive."""
    operator_id = "mini-claude-sonnet-builder"
    
    # Acquire a lease with negative TTL to immediately expire it
    lease = optime.acquire_operator_lease(
        operator_id=operator_id,
        task_id="T001",
        sprint_id="sprint-test",
        node_id="N2",
        ttl_seconds=-10
    )
    
    assert optime.get_operator_lease(operator_id) is None
    assert optime.get_operator_runtime_state(operator_id) == "idle"
    
    # Acquire should succeed since the previous lease is expired
    new_lease = optime.acquire_operator_lease(
        operator_id=operator_id,
        task_id="T002",
        sprint_id="sprint-test",
        node_id="N2",
        ttl_seconds=60
    )
    assert new_lease["task_id"] == "T002"
    assert optime.get_operator_runtime_state(operator_id) == "leased"


def test_status_override_states():
    """Test dynamic status overrides (cooldown, quota_exhausted, auth_expired)."""
    operator_id = "mini-claude-sonnet-builder"
    
    # Verify idle initially
    assert optime.get_operator_runtime_state(operator_id) == "idle"
    
    # Set quota_exhausted
    optime.set_operator_status(operator_id, "quota_exhausted")
    assert optime.get_operator_runtime_state(operator_id) == "quota_exhausted"
    
    # Set auth_expired
    optime.set_operator_status(operator_id, "auth_expired")
    assert optime.get_operator_runtime_state(operator_id) == "auth_expired"
    
    # Set cooldown
    optime.set_operator_status(operator_id, "cooldown", ttl_seconds=30)
    assert optime.get_operator_runtime_state(operator_id) == "cooldown"
    
    # Clear status override
    optime.clear_operator_status(operator_id)
    assert optime.get_operator_runtime_state(operator_id) == "idle"


def test_registry_disabled_state():
    """Verify that disabled operators in registry are classified as disabled."""
    operator_id = "mini-antigravity-gemini35-flash-high"
    
    # In registry, mini-antigravity-gemini35-flash-high is enabled: false
    assert optime.get_operator_runtime_state(operator_id) == "disabled"
    
    # Attempting to lease a disabled operator should fail
    with pytest.raises(RuntimeError, match="Cannot lease disabled operator"):
        optime.acquire_operator_lease(
            operator_id=operator_id,
            task_id="T001",
            sprint_id="sprint-test",
            node_id="N2",
            ttl_seconds=60
        )
