from __future__ import annotations

import datetime as dt
import fcntl
import json
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _request_affinity_key(request_lineage: str) -> str:
    text = str(request_lineage or "").strip()
    if not text:
        return ""
    pieces = [part for part in text.split(":") if part]
    if len(pieces) >= 3 and pieces[0] == "ai-influence-youtube-report":
        return ":".join((pieces[0], pieces[2]))
    return text


class BrowserAgentSessionPool:
    def __init__(self, root: Path, *, service: str = "chatgpt", pool_size: int = 2):
        self.root = Path(root)
        self.service = str(service or "chatgpt").strip() or "chatgpt"
        self.pool_size = max(1, int(pool_size))
        self.pool_dir = self.root / self.service
        self.pool_dir.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.pool_dir / ".lock"

    def _slot_path(self, slot_id: str) -> Path:
        return self.pool_dir / f"{slot_id}.json"

    def _default_slot(self, index: int) -> dict[str, Any]:
        slot_id = f"slot-{index:02d}"
        return {
            "slot_id": slot_id,
            "service": self.service,
            "state": "idle",
            "session_lineage": f"browser-agent-session:{self.service}:{slot_id}",
            "assigned_task_id": "",
            "assigned_request_lineage": "",
            "assigned_request_dir": "",
            "last_request_lineage": "",
            "leased_at": "",
            "last_used_at": "",
            "warm": False,
        }

    def ensure_slots(self) -> list[dict[str, Any]]:
        with open(self.lock_path, "a+", encoding="utf-8") as lock_fh:
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
            slots = self._ensure_slots_unlocked()
            fcntl.flock(lock_fh, fcntl.LOCK_UN)
        return slots

    def list_slots(self) -> list[dict[str, Any]]:
        slots = self.ensure_slots()
        return [self._read_slot(idx) or self._default_slot(idx) for idx in range(1, len(slots) + 1)]

    def acquire_slot(
        self,
        *,
        task_id: str,
        request_lineage: str = "",
        request_dir: str = "",
    ) -> dict[str, Any]:
        with open(self.lock_path, "a+", encoding="utf-8") as lock_fh:
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
            slots = self._ensure_slots_unlocked()
            idle_slots = [slot for slot in slots if str(slot.get("state") or "idle") == "idle"]
            affinity_key = _request_affinity_key(request_lineage)
            if not idle_slots:
                chosen = min(slots, key=lambda slot: str(slot.get("last_used_at") or ""))
            else:
                affinity_idle = []
                if affinity_key:
                    affinity_idle = [
                        slot
                        for slot in idle_slots
                        if _request_affinity_key(
                            str(slot.get("last_request_lineage") or slot.get("assigned_request_lineage") or "")
                        )
                        == affinity_key
                    ]
                if affinity_idle:
                    warm_affinity = [slot for slot in affinity_idle if bool(slot.get("warm"))]
                    candidates = warm_affinity or affinity_idle
                    chosen = max(candidates, key=lambda slot: str(slot.get("last_used_at") or ""))
                else:
                    cold_idle = [slot for slot in idle_slots if not bool(slot.get("warm"))]
                    chosen = cold_idle[0] if cold_idle else min(
                        idle_slots, key=lambda slot: str(slot.get("last_used_at") or "")
                    )
            chosen["state"] = "running"
            chosen["assigned_task_id"] = str(task_id or "")
            chosen["assigned_request_lineage"] = str(request_lineage or "")
            chosen["assigned_request_dir"] = str(request_dir or "")
            chosen["last_request_lineage"] = str(request_lineage or chosen.get("last_request_lineage") or "")
            chosen["leased_at"] = _now_iso()
            self._write_slot(chosen)
            fcntl.flock(lock_fh, fcntl.LOCK_UN)
            return dict(chosen)

    def release_slot(self, slot_id: str, *, keep_warm: bool = True) -> dict[str, Any]:
        with open(self.lock_path, "a+", encoding="utf-8") as lock_fh:
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
            slot = self._read_slot_by_id(slot_id)
            if slot is None:
                slot = self._default_slot(self._slot_index(slot_id))
            slot["last_request_lineage"] = str(slot.get("assigned_request_lineage") or slot.get("last_request_lineage") or "")
            slot["state"] = "idle"
            slot["assigned_task_id"] = ""
            slot["assigned_request_lineage"] = ""
            slot["assigned_request_dir"] = ""
            slot["leased_at"] = ""
            slot["last_used_at"] = _now_iso()
            slot["warm"] = bool(keep_warm)
            self._write_slot(slot)
            fcntl.flock(lock_fh, fcntl.LOCK_UN)
            return dict(slot)

    def _ensure_slots_unlocked(self) -> list[dict[str, Any]]:
        slots: list[dict[str, Any]] = []
        for idx in range(1, self.pool_size + 1):
            slot = self._read_slot(idx)
            if slot is None:
                slot = self._default_slot(idx)
                self._write_slot(slot)
            slots.append(slot)
        return slots

    def _slot_index(self, slot_id: str) -> int:
        try:
            return int(str(slot_id).split("-")[-1])
        except Exception:
            return 1

    def _read_slot_by_id(self, slot_id: str) -> dict[str, Any] | None:
        path = self._slot_path(str(slot_id))
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _read_slot(self, index: int) -> dict[str, Any] | None:
        return self._read_slot_by_id(f"slot-{index:02d}")

    def _write_slot(self, slot: dict[str, Any]) -> None:
        path = self._slot_path(str(slot["slot_id"]))
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(slot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
