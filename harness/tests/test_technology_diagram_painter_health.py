from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_painter_records_original_image_health(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SOLAR_OPERATOR_RESULTS_DIR", str(tmp_path / "run" / "operator-results"))
    monkeypatch.setenv("SOLAR_OPERATOR_HEALTH_DIR", str(tmp_path / "run" / "operator-health"))
    mod = _load_module(
        "technology_diagram_painter_operator_health_test",
        ROOT / "tools" / "technology_diagram_painter_operator.py",
    )

    task_dir = tmp_path / "task"
    response = {
        "status": "success",
        "source": "network-image-response",
        "image_path": str(task_dir / "request" / "generated_diagram.png"),
        "url": "https://chatgpt.com/backend-api/estuary/content?id=file_123",
        "width": 1536,
        "height": 864,
        "bytes": 755836,
        "request_dir": str(task_dir / "request"),
    }

    result = mod.record_operator_result(
        response,
        operator_id="technology-diagram-painter",
        task_dir=task_dir,
        task_id="task-original-image",
    )

    assert result["original_image_ok"] is True
    assert (task_dir / "operator-results" / "result.json").exists()
    canonical = tmp_path / "run" / "operator-results" / "technology-diagram-painter" / "task-original-image" / "result.json"
    health = tmp_path / "run" / "operator-health" / "technology-diagram-painter.json"
    assert json.loads(canonical.read_text(encoding="utf-8"))["source"] == "network-image-response"
    health_payload = json.loads(health.read_text(encoding="utf-8"))
    assert health_payload["health_status"] == "ok"
    assert health_payload["original_image_ok"] is True
    assert health_payload["width"] == 1536


def test_status_summary_exposes_painter_health(tmp_path: Path) -> None:
    mod = _load_module(
        "solar_status_server_painter_health_test",
        ROOT / "lib" / "symphony" / "status-server.py",
    )
    harness = tmp_path / "harness"
    mod.HARNESS_DIR = harness

    _write_json(
        harness / "config" / "physical-operators.json",
        {
            "version": 1,
            "operators": {
                "technology-diagram-painter": {
                    "role": "visual-generator",
                    "backend": "browser_agent",
                    "provider": "chatgpt",
                    "model": "gpt-image",
                    "enabled": True,
                    "available": True,
                }
            },
        },
    )
    _write_json(
        harness / "run" / "operator-health" / "technology-diagram-painter.json",
        {
            "operator_id": "technology-diagram-painter",
            "task_id": "task-original-image",
            "status": "success",
            "result_kind": "technology_diagram",
            "source": "network-image-response",
            "original_image_ok": True,
            "width": 1536,
            "height": 864,
            "bytes": 755836,
            "updated_at": "2026-05-31T00:00:00Z",
        },
    )
    _write_json(
        harness / "run" / "operator-results" / "technology-diagram-painter" / "task-original-image" / "result.json",
        {
            "operator_id": "technology-diagram-painter",
            "task_id": "task-original-image",
            "status": "success",
            "result_kind": "technology_diagram",
            "source": "network-image-response",
            "original_image_ok": True,
            "width": 1536,
            "height": 864,
            "bytes": 755836,
            "finished_at": "2026-05-31T00:00:00Z",
        },
    )

    summary = mod._physical_operator_summary(limit=4)
    item = summary["items"][0]
    recent = summary["recent_results"][0]
    assert item["operator_id"] == "technology-diagram-painter"
    assert item["latest_health"]["original_image_ok"] is True
    assert recent["result_kind"] == "technology_diagram"
    assert recent["original_image_ok"] is True
    assert summary["sources"]["health"].endswith("run/operator-health")


def test_chatgpt_readiness_failure_reason_is_actionable() -> None:
    mod = _load_module(
        "technology_diagram_painter_wrapper_readiness_test",
        ROOT / "scripts" / "browser_agent_technology_diagram_painter_wrapper.py",
    )

    assert mod._readiness_failure_reason({"login_wall": True}) == "chatgpt_login_wall_detected"
    assert mod._readiness_failure_reason({"challenge_wall": True}) == "chatgpt_cloudflare_challenge_detected"
    assert mod._readiness_failure_reason({"challenge_wall": True, "loading_wall": True}) == "chatgpt_cloudflare_challenge_detected"
    assert mod._readiness_failure_reason({"loading_wall": True}) == "chatgpt_loading_timeout"
    assert mod._readiness_failure_reason({"composer_visible": False}) == "composer_not_found_after_recovery"
    assert mod._is_nonfatal_chatgpt_toast("Failed to copy to clipboard.") is True
    assert mod._is_nonfatal_chatgpt_toast("Usage limit reached") is False


def test_operator_defaults_headless_and_retries_headed_for_auth_recovery(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SOLAR_OPERATOR_RESULTS_DIR", str(tmp_path / "run" / "operator-results"))
    monkeypatch.setenv("SOLAR_OPERATOR_HEALTH_DIR", str(tmp_path / "run" / "operator-health"))
    monkeypatch.delenv("BROWSER_AGENT_HEADLESS", raising=False)
    monkeypatch.setenv("TECH_DIAGRAM_ALLOW_HEADED_RECOVERY", "true")

    fake_wrapper = tmp_path / "fake_tech_diagram_wrapper.py"
    fake_wrapper.write_text(
        "import json, os, pathlib, sys\n"
        "req_dir = pathlib.Path(os.environ['BROWSER_AGENT_REQUEST_DIR'])\n"
        "req_dir.mkdir(parents=True, exist_ok=True)\n"
        "headless = os.environ.get('BROWSER_AGENT_HEADLESS')\n"
        "(req_dir / 'env.json').write_text(json.dumps({'headless': headless}) + '\\n')\n"
        "if headless == 'true':\n"
        "    print('chatgpt_cloudflare_challenge_detected', file=sys.stderr)\n"
        "    sys.exit(1)\n"
        "image = req_dir / 'generated_diagram.png'\n"
        "image.write_bytes(b'png')\n"
        "(req_dir / 'result.json').write_text(json.dumps({\n"
        "    'status': 'success',\n"
        "    'source': 'network-image-response',\n"
        "    'image_path': str(image),\n"
        "    'url': 'https://chatgpt.com/backend-api/estuary/content?id=file_test',\n"
        "    'width': 1024,\n"
        "    'height': 768,\n"
        "    'bytes': 3,\n"
        "    'request_dir': str(req_dir),\n"
        "}) + '\\n')\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BROWSER_AGENT_TECH_DIAGRAM_CMD", f"{sys.executable} {fake_wrapper}")

    mod = _load_module(
        "technology_diagram_painter_operator_auth_recovery_test",
        ROOT / "tools" / "technology_diagram_painter_operator.py",
    )

    task_dir = tmp_path / "task"
    result = mod.run_request(
        {
            "input_text": "Agent runtime evidence plane",
            "prompt": "draw",
            "timeout_seconds": 5,
            "max_retries": 1,
        },
        task_dir=task_dir,
    )

    assert result["status"] == "success"
    recovery = json.loads((task_dir / "auth-recovery.json").read_text(encoding="utf-8"))
    assert recovery["reason"] == "chatgpt_cloudflare_challenge_detected"
    assert recovery["action"] == "retry_headed_once"
    headless_env = json.loads((task_dir / "tech-diagram-request" / "env.json").read_text(encoding="utf-8"))
    headed_env = json.loads((task_dir / "tech-diagram-request" / "headed-recovery" / "env.json").read_text(encoding="utf-8"))
    assert headless_env["headless"] == "true"
    assert headed_env["headless"] == "false"
