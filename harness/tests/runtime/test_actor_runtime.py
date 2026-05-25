"""Tests for actor_runtime.py — Submit protocol integration."""
import json
import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "lib"))

from actor_runtime import ActorRuntime
from capability_token import CapabilityToken
from evidence_ledger import EvidenceLedger

def _make_runtime(td):
    return ActorRuntime(
        harness_dir=Path(td),
        mailbox_base=Path(td) / "actors",
        evidence_ledger=EvidenceLedger(Path(td) / "run" / "actor-evidence"),
    )

def test_submit_returns_lease_and_paths():
    with tempfile.TemporaryDirectory() as td:
        rt = _make_runtime(td)
        envelope = {"task_id": "t1", "action": "run"}
        # Need to set up actor in profiles or use logical_operator with bindings
        # For this test, use direct actor_id
        # Create a minimal actor config
        actors_dir = Path(td) / "config"
        actors_dir.mkdir(parents=True, exist_ok=True)
        actors_data = {"actors": {"test-actor": {"actor_id": "test-actor", "capability_profile": {}, "risk_profile": {}, "cost_profile": {}}}}
        (actors_dir / "agent-actors.json").write_text(json.dumps(actors_data))

        rt2 = ActorRuntime(
            harness_dir=Path(td),
            mailbox_base=Path(td) / "actors",
            profiles_path=actors_dir / "agent-actors.json",
        )
        result = rt2.submit(envelope, actor_id="test-actor", sprint_id="s1", node_id="n1")
        assert result.success
        assert result.lease is not None
        assert result.inbox_path is not None
        assert result.outbox_path is not None
        assert result.evidence_ledger_path is not None
        assert result.scheduler_decision is not None
        print("PASS: submit_returns_lease_and_paths")

def test_submit_writes_mailbox_inbox():
    with tempfile.TemporaryDirectory() as td:
        actors_dir = Path(td) / "config"
        actors_dir.mkdir(parents=True, exist_ok=True)
        actors_data = {"actors": {"a1": {"actor_id": "a1", "capability_profile": {}, "risk_profile": {}, "cost_profile": {}}}}
        (actors_dir / "agent-actors.json").write_text(json.dumps(actors_data))

        rt = ActorRuntime(
            harness_dir=Path(td),
            mailbox_base=Path(td) / "actors",
            profiles_path=actors_dir / "agent-actors.json",
        )
        envelope = {"task_id": "t1", "action": "build"}
        result = rt.submit(envelope, actor_id="a1", sprint_id="s1", node_id="n1")
        assert result.success
        # Verify inbox file exists
        inbox_path = Path(result.inbox_path)
        assert inbox_path.exists()
        data = json.loads(inbox_path.read_text())
        assert data["task_id"] == "t1"
        print("PASS: submit_writes_mailbox_inbox")

def test_submit_with_capability_token():
    with tempfile.TemporaryDirectory() as td:
        actors_dir = Path(td) / "config"
        actors_dir.mkdir(parents=True, exist_ok=True)
        actors_data = {"actors": {"a1": {"actor_id": "a1", "capability_profile": {}, "risk_profile": {}, "cost_profile": {}}}}
        (actors_dir / "agent-actors.json").write_text(json.dumps(actors_data))

        rt = ActorRuntime(
            harness_dir=Path(td),
            mailbox_base=Path(td) / "actors",
            profiles_path=actors_dir / "agent-actors.json",
        )
        token = CapabilityToken(
            token_id="tok1", scopes=["file:write"],
            expires_at="2099-01-01T00:00:00Z", actor_id="a1",
        )
        result = rt.submit({"task_id": "t2"}, actor_id="a1", capability_token=token)
        assert result.success
        print("PASS: submit_with_capability_token")

def test_submit_expired_token_fails():
    with tempfile.TemporaryDirectory() as td:
        rt = ActorRuntime(harness_dir=Path(td))
        token = CapabilityToken(
            token_id="tok-exp", scopes=["file:write"],
            expires_at="2020-01-01T00:00:00Z", actor_id="a1",
        )
        result = rt.submit({"task_id": "t3"}, actor_id="a1", capability_token=token)
        assert not result.success
        assert "capability_token_invalid" in result.error
        print("PASS: submit_expired_token_fails")

def test_no_tmux_in_runtime():
    import actor_runtime
    src = Path(actor_runtime.__file__).read_text()
    assert "tmux send-keys" not in src
    assert "send_keys" not in src
    print("PASS: no_tmux_in_runtime")


def test_submit_materializes_execution_plan_metadata():
    with tempfile.TemporaryDirectory() as td:
        actors_dir = Path(td) / "config"
        actors_dir.mkdir(parents=True, exist_ok=True)
        actors_data = {"actors": {"test-actor": {"actor_id": "test-actor", "capability_profile": {}, "risk_profile": {}, "cost_profile": {}}}}
        (actors_dir / "agent-actors.json").write_text(json.dumps(actors_data))

        rt = ActorRuntime(
            harness_dir=Path(td),
            mailbox_base=Path(td) / "actors",
            profiles_path=actors_dir / "agent-actors.json",
            evidence_ledger=EvidenceLedger(Path(td) / "run" / "actor-evidence"),
        )
        envelope = {
            "task_id": "t-plan",
            "objective": "Implement execution plan artifacts",
            "task_type": "implementation",
            "task_graph_node": {
                "id": "N2",
                "goal": "Implement execution plan artifacts",
                "logical_operator": "ImplementationWorker",
                "type": "implementation",
            },
        }
        result = rt.submit(envelope, actor_id="test-actor", sprint_id="s1", node_id="N2")
        assert result.success

        inbox_path = Path(result.inbox_path)
        payload = json.loads(inbox_path.read_text(encoding="utf-8"))
        assert payload["capsule_plan_ir"]["schema_version"] == "solar.capsule_plan_node.v1"
        assert payload["physical_plan_ir"]["schema_version"] == "solar.physical_plan_node.v1"
        assert Path(payload["plan_artifacts"]["capsule_plan_ir_path"]).exists()
        assert Path(payload["plan_artifacts"]["physical_plan_ir_path"]).exists()

if __name__ == "__main__":
    test_submit_returns_lease_and_paths()
    test_submit_writes_mailbox_inbox()
    test_submit_with_capability_token()
    test_submit_expired_token_fails()
    test_no_tmux_in_runtime()
    print("\n5/5 passed")
