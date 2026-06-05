#!/usr/bin/env python3
"""Release privacy scanner for Solar repository content.

The default scan targets git-tracked files because those are what would be
published. Runtime folders are intentionally ignored; they should not be in git
in the first place.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


SKIP_PARTS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "venvs",
    "vendor",
    "dist",
    "build",
    "target",
}

RUNTIME_PARTS = {
    ".solar",
    ".pm",
    "run",
    "runs",
    "state",
    "logs",
    "cache",
    "sprints",
    "workspace",
    "workspaces",
    "search-index",
    "quarantine",
}

GENERIC_SSH_USERS = {"user", "source-user", "remote-user"}
GENERIC_SSH_HOSTS = {"host", "remote-host", "target-machine", "source-host"}

TEXT_SUFFIXES = {
    "",
    ".bash",
    ".cjs",
    ".conf",
    ".css",
    ".env",
    ".example",
    ".html",
    ".js",
    ".json",
    ".jsonl",
    ".md",
    ".mjs",
    ".plist",
    ".py",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

ALLOW_EMAIL_DOMAINS = {
    "example.com",
    "example.org",
    "example.local",
    "localhost",
    "users.noreply.github.com",
}

PATTERNS = [
    (
        "secret_token",
        "error",
        re.compile(
            r"(AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{20,}|gh_pat_[A-Za-z0-9_]+|"
            r"sk-[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]+|"
            r"Bearer [A-Za-z0-9._~+/=-]{20,})"
        ),
    ),
    (
        "private_key",
        "error",
        re.compile(r"BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY"),
    ),
    (
        "personal_path",
        "warn",
        re.compile(r"/Users/(lisihao|sihaoli)\b"),
    ),
    (
        "real_user_path",
        "warn",
        re.compile(r"/Users/(?!<you>|<user>|<old-user>|<new-user>|<remote-user>|USERNAME|src_user|dst_user|x|\.\.\.|\$\{)[A-Za-z0-9._-]+"),
    ),
    (
        "private_network_ip",
        "warn",
        re.compile(r"\b(?:100(?:\.[0-9]{1,3}){3}|192\.168(?:\.[0-9]{1,3}){2})\b"),
    ),
    (
        "runtime_excerpt",
        "warn",
        re.compile(r"(last_block_excerpt|You've hit your limit)"),
    ),
    (
        "credential_assignment",
        "warn",
        re.compile(
            r"(?i)\b(api[_-]?key|auth[_-]?token|access[_-]?token|refresh[_-]?token|"
            r"secret|password|passwd|credential|private[_-]?key|cookie|session[_-]?token)"
            r"\b\s*[:=]\s*['\"]?(?!\$\{|<|example|changeme|redacted|N/A|null|true|false|process\.env)"
            r"[A-Za-z0-9._~+/=-]{8,}"
        ),
    ),
    (
        "ssh_target",
        "warn",
        re.compile(r"\b(?!git@|noreply@|[^@\s]+@example\.com)[A-Za-z][A-Za-z0-9._-]*@[A-Za-z0-9._-]+\b"),
    ),
    (
        "email",
        "info",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ),
]


@dataclass
class Finding:
    severity: str
    kind: str
    path: str
    line: int
    evidence: str


def git_tracked_files(repo: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"],
        check=True,
        stdout=subprocess.PIPE,
    )
    names = result.stdout.decode("utf-8", errors="replace").split("\0")
    return [repo / name for name in names if name]


def all_files(repo: Path) -> Iterable[Path]:
    for root, dirs, files in os.walk(repo):
        path = Path(root)
        dirs[:] = [d for d in dirs if d not in SKIP_PARTS]
        for name in files:
            yield path / name


def should_skip(path: Path, repo: Path, include_runtime: bool) -> bool:
    try:
        rel = path.relative_to(repo)
    except ValueError:
        return True
    parts = set(rel.parts)
    if parts & SKIP_PARTS:
        return True
    if not include_runtime and parts & RUNTIME_PARTS:
        return True
    if path.suffix not in TEXT_SUFFIXES:
        return True
    return False


def redact(text: str) -> str:
    text = re.sub(r"/Users/[A-Za-z0-9._-]+", "/Users/<user>", text)
    text = re.sub(r"\b100(?:\.[0-9]{1,3}){3}\b", "100.x.x.x", text)
    text = re.sub(r"\b192\.168(?:\.[0-9]{1,3}){2}\b", "192.168.x.x", text)
    text = re.sub(r"Bearer [A-Za-z0-9._~+/=-]{8,}", "Bearer <redacted>", text)
    text = re.sub(r"sk-[A-Za-z0-9]{8,}", "sk-<redacted>", text)
    return text.strip()[:220]


def allowed_email(match: str) -> bool:
    domain = match.rsplit("@", 1)[-1].lower()
    return domain in ALLOW_EMAIL_DOMAINS or domain.endswith(".example.com") or domain == "acme.com"


def allowed_secret_token(match: str) -> bool:
    lowered = match.lower()
    return any(
        marker in lowered
        for marker in (
            "example",
            "supersecret",
            "my_secret",
            "your_",
            "secret",
            "1234567890",
            "abcdef",
            "redacted",
            "placeholder",
        )
    )


def allowed_ssh_target(match: str) -> bool:
    user, host = match.split("@", 1)
    if allowed_email(match):
        return True
    if re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", match):
        return True
    if user in GENERIC_SSH_USERS and (host in GENERIC_SSH_HOSTS or "host" in host):
        return True
    if host in {"openai-curated", "openai-bundled"}:
        return True
    if re.fullmatch(r"[A-Za-z0-9._-]+@[0-9]+(?:\.[0-9]+)*", match):
        return True
    if "@" in match and not re.search(r"[.-]", host):
        return True
    return False


def allowed_credential_assignment(line: str, rel: str) -> bool:
    lowered = line.lower()
    if "/tests/" in f"/{rel}" or rel.startswith("harness/test-"):
        return True
    return any(
        marker in lowered
        for marker in (
            "os.environ",
            "os.getenv",
            "process.env",
            "getenv",
            "keychain",
            "_api_key",
            "_key",
            "auth_token",
            "sk-test",
            "example",
            "secret://",
        )
    )


def scan_file(path: Path, repo: Path) -> list[Finding]:
    rel = str(path.relative_to(repo))
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")

    findings: list[Finding] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for kind, severity, pattern in PATTERNS:
            for match in pattern.finditer(line):
                value = match.group(0)
                if kind == "secret_token" and allowed_secret_token(value):
                    continue
                if kind == "secret_token" and ("/tests/" in f"/{rel}" or rel.startswith("harness/test-")):
                    continue
                if kind == "credential_assignment" and allowed_credential_assignment(line, rel):
                    continue
                if kind == "runtime_excerpt" and not rel.startswith("harness/config/"):
                    continue
                if kind == "email" and ("/tests/" in f"/{rel}" or rel.startswith("harness/test-")):
                    continue
                if kind in {"personal_path", "real_user_path"} and ("/tests/" in f"/{rel}" or rel.startswith("harness/test-")):
                    continue
                if kind == "email" and allowed_email(value):
                    continue
                if kind == "ssh_target" and (value.startswith("${") or allowed_ssh_target(value)):
                    continue
                findings.append(
                    Finding(
                        severity=severity,
                        kind=kind,
                        path=rel,
                        line=line_no,
                        evidence=redact(value),
                    )
                )
    return findings


def print_table(findings: list[Finding]) -> None:
    counts = {"error": 0, "warn": 0, "info": 0}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1

    print("┌──────────┬───────┐")
    print("│ severity │ count │")
    print("├──────────┼───────┤")
    for severity in ("error", "warn", "info"):
        print(f"│ {severity:<8} │ {counts.get(severity, 0):>5} │")
    print("└──────────┴───────┘")

    ordered = sorted(findings, key=lambda f: {"error": 0, "warn": 1, "info": 2}.get(f.severity, 3))
    for finding in ordered[:80]:
        print(
            f"{finding.severity:<5} {finding.kind:<22} "
            f"{finding.path}:{finding.line} {finding.evidence}"
        )
    if len(findings) > 80:
        print(f"... {len(findings) - 80} more findings omitted")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan Solar repo for publish-risk privacy leaks.")
    parser.add_argument("--repo", default=".", help="Repository root")
    parser.add_argument("--all", action="store_true", help="Scan all files instead of git-tracked files")
    parser.add_argument("--include-runtime", action="store_true", help="Include runtime/state folders")
    parser.add_argument("--strict", action="store_true", help="Fail on warn and error findings")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    files = all_files(repo) if args.all else git_tracked_files(repo)
    findings: list[Finding] = []
    for path in files:
        if path.exists() and path.is_file() and not should_skip(path, repo, args.include_runtime):
            findings.extend(scan_file(path, repo))
    findings = list({(f.severity, f.kind, f.path, f.line, f.evidence): f for f in findings}.values())

    payload = {
        "ok": not any(
            f.severity == "error" or (args.strict and f.severity == "warn")
            for f in findings
        ),
        "strict": args.strict,
        "finding_count": len(findings),
        "findings": [asdict(f) for f in findings],
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_table(findings)
        print(json.dumps({"ok": payload["ok"], "finding_count": len(findings)}, ensure_ascii=False))

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
