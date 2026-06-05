#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import importlib.util
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any


HARNESS_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = HARNESS_ROOT / "tools"


def _load_watchdog():
    spec = importlib.util.spec_from_file_location(
        "operator_health_watchdog_cli", TOOLS_DIR / "operator_health_watchdog.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_main(monkeypatch, argv: list[str], module) -> tuple[int, str, str]:
    monkeypatch.setattr(module, "sys", module.sys)
    monkeypatch.setattr(module.sys, "argv", argv)
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        rc = int(module.main())
    return rc, stdout.getvalue(), stderr.getvalue()


def test_parser_displays_status_and_install_commands():
    watchdog = _load_watchdog()
    help_text = watchdog._build_parser().format_help()
    assert "run" in help_text
    assert "status" in help_text
    assert "install-launchagent" in help_text


def test_load_core_resolves_lib_imports():
    watchdog = _load_watchdog()
    core = watchdog._load_core()

    assert core.SCHEMA_VERSION == "operator_health_watchdog.v1"
    assert hasattr(core, "run_watchdog")


def test_main_dispatches_run_once_with_json(monkeypatch):
    watchdog = _load_watchdog()
    got: dict[str, Any] = {}

    def fake_run_once(*, apply: bool, max_age_minutes: int, lock_path: Path, latest_path: Path, history_path: Path):
        got.update(
            {
                "apply": apply,
                "max_age_minutes": max_age_minutes,
                "lock_path": lock_path,
                "latest_path": latest_path,
                "history_path": history_path,
            }
        )
        return {"ok": True}

    monkeypatch.setattr(watchdog, "command_run_once", fake_run_once)
    rc, out, _ = _run_main(monkeypatch, ["operator-health-watchdog", "run", "--once", "--json"], watchdog)

    assert rc == 0
    payload = json.loads(out.strip())
    assert payload["ok"] is True
    assert got["apply"] is False
    assert got["max_age_minutes"] == 45
    assert got["lock_path"] == watchdog.LOCK_PATH
    assert got["latest_path"] == watchdog.LATEST_REPORT_PATH
    assert got["history_path"] == watchdog.HISTORY_PATH


def test_main_preserves_legacy_root_json_apply(monkeypatch):
    watchdog = _load_watchdog()
    got: dict[str, Any] = {}

    def fake_run_once(*, apply: bool, max_age_minutes: int, lock_path: Path, latest_path: Path, history_path: Path):
        got.update(
            {
                "apply": apply,
                "max_age_minutes": max_age_minutes,
                "lock_path": lock_path,
                "latest_path": latest_path,
                "history_path": history_path,
            }
        )
        return {"ok": True, "legacy": True}

    monkeypatch.setattr(watchdog, "command_run_once", fake_run_once)
    rc, out, _ = _run_main(
        monkeypatch,
        ["operator-health-watchdog", "--json", "--apply", "--max-age-minutes", "12"],
        watchdog,
    )

    assert rc == 0
    payload = json.loads(out.strip())
    assert payload["legacy"] is True
    assert got["apply"] is True
    assert got["max_age_minutes"] == 12
    assert got["lock_path"] == watchdog.LOCK_PATH
    assert got["latest_path"] == watchdog.LATEST_REPORT_PATH
    assert got["history_path"] == watchdog.HISTORY_PATH


def test_main_dispatches_loop_with_same_paths_as_once(monkeypatch):
    watchdog = _load_watchdog()
    got: dict[str, Any] = {}

    def fake_run_loop(*, interval: int, apply: bool, max_age_minutes: int, lock_path: Path, latest_path: Path, history_path: Path):
        got.update(
            {
                "interval": interval,
                "apply": apply,
                "max_age_minutes": max_age_minutes,
                "lock_path": lock_path,
                "latest_path": latest_path,
                "history_path": history_path,
            }
        )
        return [{"ok": True}]

    monkeypatch.setattr(watchdog, "command_run_loop", fake_run_loop)
    rc, out, _ = _run_main(monkeypatch, ["operator-health-watchdog", "run", "--loop", "--interval", "8", "--json"], watchdog)

    assert rc == 0
    payload = json.loads(out.strip())
    assert payload["ok"] is True
    assert got["interval"] == 8
    assert got["lock_path"] == watchdog.LOCK_PATH
    assert got["latest_path"] == watchdog.LATEST_REPORT_PATH
    assert got["history_path"] == watchdog.HISTORY_PATH


def test_main_invalid_loop_interval_exits_with_error(monkeypatch):
    watchdog = _load_watchdog()
    rc, out, err = _run_main(monkeypatch, ["operator-health-watchdog", "run", "--loop", "--interval", "0", "--json"], watchdog)
    assert rc == 1
    assert err == ""
    payload = json.loads(out.strip())
    assert payload["ok"] is False
    assert payload["degraded_reason"] == "--loop requires --interval > 0"
    assert payload["run_once"]["mode"] == "loop"


def test_main_dispatches_status_install_launchagent_routes(monkeypatch):
    watchdog = _load_watchdog()
    got: dict[str, Any] = {}

    def fake_status(*, json_output: bool = True, latest_path=watchdog.LATEST_REPORT_PATH):
        got["status"] = True
        got["json_output"] = json_output
        got["latest_path"] = latest_path
        return {"ok": False}

    def fake_install(*, dry_run: bool = False, apply: bool = False, run_dir=watchdog.RUN_DIR):
        got["install"] = True
        got["dry_run"] = dry_run
        got["apply"] = apply
        got["run_dir"] = run_dir
        return {"ok": False, "degraded_reason": "test"}

    monkeypatch.setattr(watchdog, "command_status", fake_status)
    rc_status, _, _ = _run_main(monkeypatch, ["operator-health-watchdog", "status", "--json"], watchdog)

    monkeypatch.setattr(watchdog, "command_install_launchagent", fake_install)
    rc_install, out_install, _ = _run_main(
        monkeypatch,
        ["operator-health-watchdog", "install-launchagent", "--json", "--dry-run"],
        watchdog,
    )

    assert rc_status == 2
    assert got.get("status") is True
    assert got.get("json_output") is True
    assert got.get("latest_path") == watchdog.LATEST_REPORT_PATH
    assert rc_install == 1
    assert got.get("install") is True
    assert got.get("dry_run") is True
    assert "degraded_reason" in json.loads(out_install)


def test_install_launchagent_dry_run_uses_daemon_script():
    watchdog = _load_watchdog()

    payload = watchdog.command_install_launchagent(dry_run=True)

    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["label"] == "com.solar.harness.operator-health-watchdog"
    assert payload["daemon_script"].endswith("operator-health-watchdog-daemon.sh")
    assert payload["out_log"].endswith("operator-health-watchdog.out.log")
    assert payload["err_log"].endswith("operator-health-watchdog.err.log")
