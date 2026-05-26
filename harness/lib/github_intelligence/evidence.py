"""Evidence compression pipeline — clean, analyze, and compress repository metadata.

Provides:
- ``clean_readme()``: strips HTML comments, image embeds, scripts, styles.
- ``call_qwen_local()``: calls the local ThunderOMLX Qwen3.6 model.
- ``compress_readme()``: extracts readme claims and runs wrapper detection.
- ``compress_releases()``: extracts release features.
- ``compress_issues_prs()``: extracts issue and PR signals.
- ``extract_cross_source_mentions()``: compiles social/youtube mentions.
- ``generate_growth_facts()``: formats snapshot delta growth stats.
- ``run_preprocess_pipeline()``: runs the complete pipeline, tracking failures in the retry queue.

Spec: sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade
      design.md §A2 & §A3 + outcomes.md O2 & O3
Node: B6
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# Global Constants
GITHUB_REPO_RE = re.compile(r"\b([a-zA-Z0-9-_\.]+/[a-zA-Z0-9-_\.]+)\b")
DEFAULT_THUNDEROMLX_ENDPOINT = "http://127.0.0.1:8002"
DEFAULT_THUNDEROMLX_MODEL = "Qwen3.6-35b-a3b"


def clean_readme(text: str) -> str:
    """Clean markdown README by removing HTML comments, scripts, styles, images, and extra spacing."""
    if not text:
        return ""
    # Remove HTML comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    # Remove script and style tags
    text = re.sub(r"<script.*?>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style.*?>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Remove markdown image embeds: ![alt](url)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"!\[.*?\].*?\]", "", text)
    # Compress multiple blank lines to a single blank line
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text.strip()


def github_repo_atom_id(full_name: str, evidence_type: str, source_id: str) -> str:
    """Generate a reproducible primary key for repo evidence atoms."""
    raw = f"{full_name}\0{evidence_type}\0{source_id}"
    return "ghatom_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def github_extract_repo_entities(text: str) -> dict[str, list[str]]:
    """Extract technology, repository, model, and company entities from text."""
    tech_words = [
        "agent", "mcp", "rag", "retrieval", "memory", "context", "llm", "inference",
        "triton", "cuda", "mlx", "vllm", "transformer", "robotics", "vla", "workflow",
        "browser", "devtools", "compiler", "database", "benchmark", "eval",
    ]
    found = sorted({kw for kw in tech_words if kw in text.lower()})
    repos = sorted(set(GITHUB_REPO_RE.findall(text)))
    return {
        "technologies": found[:12],
        "repos": repos[:10],
        "models": sorted(set(re.findall(r"\b(GPT-\d+(?:\.\d+)?|Claude|Gemini|Qwen\d*|DeepSeek|Llama)\b", text, re.I)))[:10],
        "companies": sorted(set(re.findall(r"\b(OpenAI|Anthropic|Google|DeepMind|NVIDIA|Meta|Microsoft|DeepSeek)\b", text, re.I)))[:10],
    }


def get_thunderomlx_config(endpoint: str | None = None, api_key: str | None = None) -> tuple[str, str, str]:
    """Retrieve ThunderOMLX endpoint, API key, and model name dynamically."""
    ep = endpoint or os.environ.get("THUNDEROMLX_BASE_URL")
    if not ep:
        ep = DEFAULT_THUNDEROMLX_ENDPOINT
    
    key = api_key or os.environ.get("THUNDEROMLX_AUTH_TOKEN")
    if not key:
        settings_path = Path.home() / ".omlx" / "settings.json"
        if settings_path.exists():
            try:
                data = json.loads(settings_path.read_text(encoding="utf-8"))
                key = data.get("auth", {}).get("api_key")
            except Exception:
                pass
    if not key:
        key = "local-thunderomlx"
        
    model = os.environ.get("THUNDEROMLX_KNOWLEDGE_MODEL") or DEFAULT_THUNDEROMLX_MODEL
    return ep, key, model


def parse_chat_response(data: dict[str, Any]) -> str:
    """Parse output text from completions/messages response formats."""
    if "choices" in data:
        for choice in data.get("choices") or []:
            msg = choice.get("message") or {}
            content = msg.get("content")
            if content:
                return str(content)
    elif "content" in data:
        text_parts = []
        for item in data.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(str(item.get("text") or ""))
            elif isinstance(item, dict) and "text" in item:
                text_parts.append(str(item.get("text") or ""))
        return "\n".join(text_parts)
    return ""


def extract_json_text(text: str) -> str:
    """Clean model reasoning steps and codeblock wrapping around JSON output."""
    text = re.sub(r"(?is)<think>.*?</think>\s*", "", text).strip()
    text = re.sub(r"(?is)^```(?:json)?\s*", "", text)
    text = re.sub(r"(?is)\s*```\s*$", "", text).strip()
    if "{" in text and "}" in text:
        return text[text.index("{") : text.rindex("}") + 1]
    return text


def call_qwen_local(
    prompt: str,
    system_prompt: str | None = None,
    endpoint: str | None = None,
    api_key: str | None = None,
    timeout_sec: float = 20.0,
) -> str:
    """Call the local ThunderOMLX endpoint with automatic backend fallback."""
    ep, key, model = get_thunderomlx_config(endpoint, api_key)
    base = ep.rstrip("/")
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    headers = {"Content-Type": "application/json", "x-api-key": key}
    if key:
        headers["authorization"] = f"Bearer {key}"
        
    payload = {"model": model, "messages": messages, "temperature": 0.1, "max_tokens": 1500}
    
    # Try /v1/chat/completions first
    url = f"{base}/v1/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            res_data = json.loads(resp.read().decode("utf-8", errors="replace"))
            return parse_chat_response(res_data)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            # Fallback to /v1/messages
            url_msg = f"{base}/v1/messages"
            user_msgs = [m for m in messages if m["role"] != "system"]
            msg_payload = {"model": model, "messages": user_msgs, "max_tokens": 1500, "temperature": 0.1}
            system_contents = [m["content"] for m in messages if m["role"] == "system"]
            if system_contents:
                msg_payload["system"] = "\n\n".join(system_contents)
                
            req_msg = urllib.request.Request(
                url_msg,
                data=json.dumps(msg_payload, ensure_ascii=False).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req_msg, timeout=timeout_sec) as resp_msg:
                res_data = json.loads(resp_msg.read().decode("utf-8", errors="replace"))
                return parse_chat_response(res_data)
        else:
            raise


def compress_readme(
    conn: sqlite3.Connection,
    full_name: str,
    readme_text: str | None = None,
    endpoint: str | None = None,
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    """Analyze and compress README content. Evaluates technical depth and identifies wrapper projects."""
    if readme_text is None:
        row = conn.execute("SELECT readme_text, html_url FROM github_repos WHERE full_name = ?", (full_name,)).fetchone()
        if not row:
            return []
        readme_text, html_url = row
    else:
        row = conn.execute("SELECT html_url FROM github_repos WHERE full_name = ?", (full_name,)).fetchone()
        html_url = row[0] if row else f"https://github.com/{full_name}"
        
    if not readme_text or not readme_text.strip():
        return []
        
    cleaned = clean_readme(readme_text)[:50000]
    
    system = """You are a software engineer analyzing a GitHub repository.
Analyze the README to extract key claims, and determine if the repository is a simple wrapper or has real technical depth.
Output a JSON object exactly matching this schema:
{
  "is_wrapper": true or false,
  "wrapper_type": "api_wrapper", "prompt_wrapper", "ui_wrapper", "glue_code", or null,
  "technical_depth_score": 0.0 to 1.0 (float),
  "novelty_score": 0.0 to 1.0 (float),
  "confidence": 0.0 to 1.0 (float),
  "claims": [
    {
      "claim_summary": "one-sentence summary of the claim",
      "compressed_content": "compressed claim explanation under 500 characters",
      "importance_score": 0 to 100,
      "novelty_score": 0.0 to 1.0,
      "confidence": 0.0 to 1.0,
      "tags": ["tag1", "tag2"]
    }
  ]
}
Notes for scoring:
- If is_wrapper is true, technical_depth_score MUST be set low (e.g. 0.0 to 0.30).
- If it is a deep framework, library, custom CUDA/mlx code, or systems software, set technical_depth_score high (0.65 to 1.0).
Ensure the output is ONLY a valid JSON object.
"""
    prompt = f"Repository: {full_name}\n\nREADME:\n{cleaned}"
    
    try:
        raw_resp = call_qwen_local(prompt, system, endpoint, api_key)
        parsed = json.loads(extract_json_text(raw_resp))
    except Exception as e:
        raise RuntimeError(f"Failed to parse model response for README: {e}")
        
    is_wrapper = parsed.get("is_wrapper", False)
    tech_depth = parsed.get("technical_depth_score", 0.5)
    if is_wrapper:
        tech_depth = min(tech_depth, 0.3)
    else:
        tech_depth = max(tech_depth, 0.35)
        
    atoms = []
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    claims_list = parsed.get("claims") or []
    for i, claim in enumerate(claims_list):
        imp = claim.get("importance_score", 50)
        if imp < 20:
            continue
            
        claim_summary = claim.get("claim_summary", "")
        compressed = claim.get("compressed_content", claim_summary)
        if len(compressed) > 500:
            compressed = compressed[:497] + "..."
            
        atom_id = github_repo_atom_id(full_name, "readme_claim", f"readme_claim_{i}")
        
        atom = {
            "atom_id": atom_id,
            "repo_full_name": full_name,
            "evidence_type": "readme_claim",
            "compressed_content": compressed,
            "entities_json": json.dumps(claim.get("entities") or github_extract_repo_entities(compressed), ensure_ascii=False, sort_keys=True),
            "tags_json": json.dumps(claim.get("tags") or [], ensure_ascii=False),
            "confidence": float(claim.get("confidence", parsed.get("confidence", 0.75))),
            "technical_depth": float(tech_depth),
            "novelty_score": float(claim.get("novelty_score", parsed.get("novelty_score", 0.5))),
            "raw_source_type": "github_readme",
            "raw_source_id": f"readme_{created_at[:10]}",
            "model_used": os.environ.get("THUNDEROMLX_KNOWLEDGE_MODEL") or DEFAULT_THUNDEROMLX_MODEL,
            "created_at": created_at,
        }
        
        conn.execute(
            """INSERT OR REPLACE INTO repo_evidence_atoms
               (atom_id, repo_full_name, evidence_type, compressed_content, entities_json, tags_json,
                confidence, technical_depth, novelty_score, raw_source_type, raw_source_id, model_used, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                atom["atom_id"], atom["repo_full_name"], atom["evidence_type"], atom["compressed_content"],
                atom["entities_json"], atom["tags_json"], atom["confidence"], atom["technical_depth"],
                atom["novelty_score"], atom["raw_source_type"], atom["raw_source_id"], atom["model_used"], atom["created_at"]
            )
        )
        atoms.append(atom)
        
    return atoms


def compress_releases(
    conn: sqlite3.Connection,
    full_name: str,
    releases_data: list[dict[str, Any]] | None = None,
    endpoint: str | None = None,
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    """Compress release notes/tags. Summarizes detailed release logs, falling back to latest release tag info."""
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    model_name = os.environ.get("THUNDEROMLX_KNOWLEDGE_MODEL") or DEFAULT_THUNDEROMLX_MODEL
    
    if releases_data:
        items = []
        for r in releases_data[:5]:
            tag = r.get("tag_name") or r.get("tag") or "unknown"
            name = r.get("name") or ""
            body = r.get("body") or r.get("description") or ""
            items.append(f"Release {tag}: {name}\n{body}")
        
        raw_text = "\n\n".join(items)
        if raw_text.strip():
            system = """You are analyzing release notes of a repository. Extract the key new features and improvements.
Output a JSON object exactly matching this schema:
{
  "features": [
    {
      "compressed_content": "compressed feature explanation under 500 characters",
      "importance_score": 0 to 100,
      "novelty_score": 0.0 to 1.0,
      "confidence": 0.0 to 1.0,
      "tags": ["tag1", "tag2"]
    }
  ]
}
Ensure output is ONLY the JSON object.
"""
            prompt = f"Repository: {full_name}\n\nRelease Notes:\n{raw_text[:20000]}"
            try:
                raw_resp = call_qwen_local(prompt, system, endpoint, api_key)
                parsed = json.loads(extract_json_text(raw_resp))
                features = parsed.get("features") or []
                atoms = []
                for i, feat in enumerate(features):
                    imp = feat.get("importance_score", 50)
                    if imp < 20:
                        continue
                    compressed = feat.get("compressed_content", "")
                    if not compressed:
                        continue
                    if len(compressed) > 500:
                        compressed = compressed[:497] + "..."
                        
                    atom_id = github_repo_atom_id(full_name, "release_feature", f"release_feature_{i}")
                    atom = {
                        "atom_id": atom_id,
                        "repo_full_name": full_name,
                        "evidence_type": "release_feature",
                        "compressed_content": compressed,
                        "entities_json": json.dumps(github_extract_repo_entities(compressed), ensure_ascii=False, sort_keys=True),
                        "tags_json": json.dumps(feat.get("tags") or [], ensure_ascii=False),
                        "confidence": float(feat.get("confidence", 0.8)),
                        "technical_depth": 0.5,
                        "novelty_score": float(feat.get("novelty_score", 0.5)),
                        "raw_source_type": "github_release",
                        "raw_source_id": f"release_{created_at[:10]}",
                        "model_used": model_name,
                        "created_at": created_at,
                    }
                    conn.execute(
                        """INSERT OR REPLACE INTO repo_evidence_atoms
                           (atom_id, repo_full_name, evidence_type, compressed_content, entities_json, tags_json,
                            confidence, technical_depth, novelty_score, raw_source_type, raw_source_id, model_used, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            atom["atom_id"], atom["repo_full_name"], atom["evidence_type"], atom["compressed_content"],
                            atom["entities_json"], atom["tags_json"], atom["confidence"], atom["technical_depth"],
                            atom["novelty_score"], atom["raw_source_type"], atom["raw_source_id"], atom["model_used"], atom["created_at"]
                        )
                    )
                    atoms.append(atom)
                return atoms
            except Exception as e:
                print(f"Warning: Failed to summarize releases via LLM for {full_name}: {e}")
                
    # Fallback to DB latest_release_tag
    row = conn.execute("SELECT latest_release_tag, latest_release_at FROM github_repos WHERE full_name = ?", (full_name,)).fetchone()
    if row and row[0]:
        tag, release_at = row
        content = f"{full_name} latest release {tag} at {release_at or 'unknown time'}."
        atom_id = github_repo_atom_id(full_name, "release_feature", f"release_tag_{tag}")
        atom = {
            "atom_id": atom_id,
            "repo_full_name": full_name,
            "evidence_type": "release_feature",
            "compressed_content": content,
            "entities_json": json.dumps(github_extract_repo_entities(content), ensure_ascii=False, sort_keys=True),
            "tags_json": json.dumps(["release"], ensure_ascii=False),
            "confidence": 0.8,
            "technical_depth": 0.45,
            "novelty_score": 0.5,
            "raw_source_type": "github_release",
            "raw_source_id": f"release_{tag}",
            "model_used": "local_qwen3_6",
            "created_at": created_at,
        }
        conn.execute(
            """INSERT OR REPLACE INTO repo_evidence_atoms
               (atom_id, repo_full_name, evidence_type, compressed_content, entities_json, tags_json,
                confidence, technical_depth, novelty_score, raw_source_type, raw_source_id, model_used, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                atom["atom_id"], atom["repo_full_name"], atom["evidence_type"], atom["compressed_content"],
                atom["entities_json"], atom["tags_json"], atom["confidence"], atom["technical_depth"],
                atom["novelty_score"], atom["raw_source_type"], atom["raw_source_id"], atom["model_used"], atom["created_at"]
            )
        )
        return [atom]
        
    return []


def compress_issues_prs(
    conn: sqlite3.Connection,
    full_name: str,
    issues_data: list[dict[str, Any]] | None = None,
    prs_data: list[dict[str, Any]] | None = None,
    endpoint: str | None = None,
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    """Summarize issue & PR signals. Distills bug trends and pull requests into structured atoms."""
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    model_name = os.environ.get("THUNDEROMLX_KNOWLEDGE_MODEL") or DEFAULT_THUNDEROMLX_MODEL
    
    issues = issues_data or []
    prs = prs_data or []
    
    if not issues and not prs:
        return []
        
    items = []
    for issue in issues[:10]:
        title = issue.get("title") or ""
        body = issue.get("body") or ""
        items.append(f"Issue: {title}\n{body[:500]}")
    for pr in prs[:10]:
        title = pr.get("title") or ""
        body = pr.get("body") or ""
        items.append(f"PR: {title}\n{body[:500]}")
        
    raw_text = "\n\n".join(items)
    if not raw_text.strip():
        return []
        
    system = """You are analyzing active issues and pull requests for a repository.
Identify significant signals like critical bug trends, major feature discussions, or architectural updates.
Output a JSON object exactly matching this schema:
{
  "signals": [
    {
      "signal_type": "issue_signal" or "pr_signal",
      "compressed_content": "compressed signal text under 500 characters",
      "importance_score": 0 to 100,
      "novelty_score": 0.0 to 1.0,
      "confidence": 0.0 to 1.0,
      "tags": ["tag1", "tag2"]
    }
  ]
}
Ensure output is ONLY the JSON object.
"""
    prompt = f"Repository: {full_name}\n\nIssues & PRs:\n{raw_text[:20000]}"
    try:
        raw_resp = call_qwen_local(prompt, system, endpoint, api_key)
        parsed = json.loads(extract_json_text(raw_resp))
        signals = parsed.get("signals") or []
        atoms = []
        for i, sig in enumerate(signals):
            imp = sig.get("importance_score", 50)
            if imp < 20:
                continue
            compressed = sig.get("compressed_content", "")
            if not compressed:
                continue
            if len(compressed) > 500:
                compressed = compressed[:497] + "..."
                
            sig_type = sig.get("signal_type")
            if sig_type not in ("issue_signal", "pr_signal"):
                sig_type = "issue_signal"
                
            atom_id = github_repo_atom_id(full_name, sig_type, f"{sig_type}_{i}")
            atom = {
                "atom_id": atom_id,
                "repo_full_name": full_name,
                "evidence_type": sig_type,
                "compressed_content": compressed,
                "entities_json": json.dumps(github_extract_repo_entities(compressed), ensure_ascii=False, sort_keys=True),
                "tags_json": json.dumps(sig.get("tags") or [], ensure_ascii=False),
                "confidence": float(sig.get("confidence", 0.75)),
                "technical_depth": 0.45,
                "novelty_score": float(sig.get("novelty_score", 0.5)),
                "raw_source_type": "github_issues_prs",
                "raw_source_id": f"issues_prs_{created_at[:10]}",
                "model_used": model_name,
                "created_at": created_at,
            }
            conn.execute(
                """INSERT OR REPLACE INTO repo_evidence_atoms
                   (atom_id, repo_full_name, evidence_type, compressed_content, entities_json, tags_json,
                    confidence, technical_depth, novelty_score, raw_source_type, raw_source_id, model_used, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    atom["atom_id"], atom["repo_full_name"], atom["evidence_type"], atom["compressed_content"],
                    atom["entities_json"], atom["tags_json"], atom["confidence"], atom["technical_depth"],
                    atom["novelty_score"], atom["raw_source_type"], atom["raw_source_id"], atom["model_used"], atom["created_at"]
                )
            )
            atoms.append(atom)
        return atoms
    except Exception as e:
        raise RuntimeError(f"Failed to summarize issues/PRs: {e}")


def extract_cross_source_mentions(
    conn: sqlite3.Connection,
    full_name: str,
    social_data: list[dict[str, Any]] | None = None,
    youtube_data: list[dict[str, Any]] | None = None,
    endpoint: str | None = None,
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    """Extract and summarize cross-source mentions from social media streams and YouTube transcripts."""
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    model_name = os.environ.get("THUNDEROMLX_KNOWLEDGE_MODEL") or DEFAULT_THUNDEROMLX_MODEL
    
    if social_data is None:
        rows = conn.execute(
            "SELECT evidence_id, content FROM evidence_atoms WHERE source='social' AND content LIKE ?",
            (f"%github.com/{full_name}%",),
        ).fetchall()
        social_data = [{"id": r[0], "text": r[1]} for r in rows]
        
    if youtube_data is None:
        rows = conn.execute(
            "SELECT evidence_id, content FROM evidence_atoms WHERE source='youtube' AND content LIKE ?",
            (f"%github.com/{full_name}%",),
        ).fetchall()
        youtube_data = [{"id": r[0], "text": r[1]} for r in rows]
        
    if not social_data and not youtube_data:
        return []
        
    items = []
    for item in social_data[:5]:
        items.append(f"Social Post ({item.get('id')}): {item.get('text')}")
    for item in youtube_data[:5]:
        items.append(f"YouTube Mention ({item.get('id')}): {item.get('text')}")
        
    raw_text = "\n\n".join(items)
    system = """You are analyzing social posts and video transcript mentions for a GitHub repository.
Extract key mentions, identify the author's stance (e.g. positive, critical, curious), and summarize.
Output a JSON object exactly matching this schema:
{
  "mentions": [
    {
      "source_id": "mention source id",
      "source_type": "social_mention" or "youtube_mention",
      "compressed_content": "compressed mention summary under 500 characters including stance/claim",
      "importance_score": 0 to 100,
      "novelty_score": 0.0 to 1.0,
      "confidence": 0.0 to 1.0,
      "tags": ["tag1", "tag2"]
    }
  ]
}
Ensure output is ONLY the JSON object.
"""
    prompt = f"Repository: {full_name}\n\nMentions:\n{raw_text[:20000]}"
    try:
        raw_resp = call_qwen_local(prompt, system, endpoint, api_key)
        parsed = json.loads(extract_json_text(raw_resp))
        mentions_list = parsed.get("mentions") or []
        atoms = []
        for i, ment in enumerate(mentions_list):
            imp = ment.get("importance_score", 50)
            if imp < 20:
                continue
            compressed = ment.get("compressed_content", "")
            if not compressed:
                continue
            if len(compressed) > 500:
                compressed = compressed[:497] + "..."
                
            m_type = ment.get("source_type")
            if m_type not in ("social_mention", "youtube_mention"):
                m_type = "social_mention"
                
            src_id = ment.get("source_id") or f"mention_{i}"
            
            atom_id = github_repo_atom_id(full_name, m_type, src_id)
            atom = {
                "atom_id": atom_id,
                "repo_full_name": full_name,
                "evidence_type": m_type,
                "compressed_content": compressed,
                "entities_json": json.dumps(github_extract_repo_entities(compressed), ensure_ascii=False, sort_keys=True),
                "tags_json": json.dumps(ment.get("tags") or [], ensure_ascii=False),
                "confidence": float(ment.get("confidence", 0.75)),
                "technical_depth": 0.35,
                "novelty_score": float(ment.get("novelty_score", 0.5)),
                "raw_source_type": m_type,
                "raw_source_id": src_id,
                "model_used": model_name,
                "created_at": created_at,
            }
            conn.execute(
                """INSERT OR REPLACE INTO repo_evidence_atoms
                   (atom_id, repo_full_name, evidence_type, compressed_content, entities_json, tags_json,
                    confidence, technical_depth, novelty_score, raw_source_type, raw_source_id, model_used, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    atom["atom_id"], atom["repo_full_name"], atom["evidence_type"], atom["compressed_content"],
                    atom["entities_json"], atom["tags_json"], atom["confidence"], atom["technical_depth"],
                    atom["novelty_score"], atom["raw_source_type"], atom["raw_source_id"], atom["model_used"], atom["created_at"]
                )
            )
            atoms.append(atom)
        return atoms
    except Exception as e:
        raise RuntimeError(f"Failed to extract cross source mentions: {e}")


def generate_growth_facts(
    conn: sqlite3.Connection,
    full_name: str,
) -> list[dict[str, Any]]:
    """Format quantitative snapshot growth statistics into growth_fact evidence atoms."""
    row = conn.execute(
        """SELECT stars, forks, open_issues, watchers, stars_delta_24h, stars_delta_7d, stars_delta_30d, star_acceleration, snapshot_at
           FROM github_star_snapshots
           WHERE full_name = ?
           ORDER BY snapshot_at DESC LIMIT 1""",
        (full_name,),
    ).fetchone()
    
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    if row:
        stars, forks, open_issues, watchers, delta_24h, delta_7d, delta_30d, accel, snapshot_at = row
        accel = accel or 1.0
        if accel > 20:
            tier = "needs_attribution"
        elif accel > 8:
            tier = "sudden_hot"
        elif accel > 3:
            tier = "breakout"
        elif accel > 1.5:
            tier = "warming"
        else:
            tier = "normal"
            
        content = (
            f"{full_name} growth snapshot: stars={stars or 0}, forks={forks or 0}, "
            f"delta_1d={delta_24h}, delta_7d={delta_7d}, "
            f"delta_30d={delta_30d}, acceleration={accel} ({tier})."
        )
    else:
        repo_row = conn.execute(
            "SELECT stars, forks, open_issues, watchers FROM github_repos WHERE full_name = ?",
            (full_name,),
        ).fetchone()
        if not repo_row:
            return []
        stars, forks, open_issues, watchers = repo_row
        content = (
            f"{full_name} growth snapshot: stars={stars or 0}, forks={forks or 0}, "
            f"delta_1d=None, delta_7d=None, delta_30d=None, acceleration=1.0 (normal)."
        )
        tier = "normal"
        
    atom_id = github_repo_atom_id(full_name, "growth_fact", f"growth_{created_at[:10]}")
    topics_row = conn.execute("SELECT topics, description FROM github_repos WHERE full_name = ?", (full_name,)).fetchone()
    topics = topics_row[0] if topics_row else ""
    desc = topics_row[1] if topics_row else ""
    
    # Classify trend bucket (AC7 fallback)
    bucket = "agent_runtime"
    if topics or desc:
        topics_lower = (topics or "").lower() + " " + (desc or "").lower()
        if "skill" in topics_lower or "plugin" in topics_lower:
            bucket = "agent_skill"
        elif "coding" in topics_lower or "coder" in topics_lower:
            bucket = "coding_agent"
        elif "context" in topics_lower or "rag" in topics_lower or "memory" in topics_lower:
            bucket = "context_engineering"
        elif "cuda" in topics_lower or "triton" in topics_lower or "inference" in topics_lower or "mlx" in topics_lower:
            bucket = "inference_compute"
        elif "train" in topics_lower or "lora" in topics_lower:
            bucket = "training_framework"
        elif "robot" in topics_lower or "embodied" in topics_lower:
            bucket = "robotics_physical_ai"
        elif "database" in topics_lower or "compiler" in topics_lower:
            bucket = "infra_os"
        elif "security" in topics_lower:
            bucket = "security_ai"
            
    atom = {
        "atom_id": atom_id,
        "repo_full_name": full_name,
        "evidence_type": "growth_fact",
        "compressed_content": content,
        "entities_json": json.dumps(github_extract_repo_entities(content), ensure_ascii=False, sort_keys=True),
        "tags_json": json.dumps([bucket, "growth", tier], ensure_ascii=False),
        "confidence": 0.8,
        "technical_depth": 0.35,
        "novelty_score": 0.75 if tier != "normal" else 0.35,
        "raw_source_type": "github_snapshot",
        "raw_source_id": f"snapshot_{created_at[:10]}",
        "model_used": "local_qwen3_6",
        "created_at": created_at,
    }
    
    conn.execute(
        """INSERT OR REPLACE INTO repo_evidence_atoms
           (atom_id, repo_full_name, evidence_type, compressed_content, entities_json, tags_json,
            confidence, technical_depth, novelty_score, raw_source_type, raw_source_id, model_used, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            atom["atom_id"], atom["repo_full_name"], atom["evidence_type"], atom["compressed_content"],
            atom["entities_json"], atom["tags_json"], atom["confidence"], atom["technical_depth"],
            atom["novelty_score"], atom["raw_source_type"], atom["raw_source_id"], atom["model_used"], atom["created_at"]
        )
    )
    return [atom]


def run_preprocess_pipeline(
    conn: sqlite3.Connection,
    full_name: str,
    readme_text: str | None = None,
    releases_data: list[dict[str, Any]] | None = None,
    issues_data: list[dict[str, Any]] | None = None,
    prs_data: list[dict[str, Any]] | None = None,
    social_data: list[dict[str, Any]] | None = None,
    youtube_data: list[dict[str, Any]] | None = None,
    endpoint: str | None = None,
    api_key: str | None = None,
) -> bool:
    """Run the complete local preprocessing pipeline for a repository. Marks status in retry_queue on failure."""
    try:
        # Run README claim compression
        compress_readme(conn, full_name, readme_text, endpoint, api_key)
        
        # Run Release compression
        compress_releases(conn, full_name, releases_data, endpoint, api_key)
        
        # Run Issues & PRs summary
        compress_issues_prs(conn, full_name, issues_data, prs_data, endpoint, api_key)
        
        # Run Cross-source mentions extraction
        extract_cross_source_mentions(conn, full_name, social_data, youtube_data, endpoint, api_key)
        
        # Run Growth facts generation
        generate_growth_facts(conn, full_name)
        
        # Successful execution: clean any preprocess failures for this repo
        conn.execute(
            "DELETE FROM retry_queue WHERE source='github' AND source_id=? AND operation='preprocess'",
            (full_name,),
        )
        conn.commit()
        return True
    except Exception as e:
        now = datetime.now(timezone.utc)
        next_retry = now + timedelta(minutes=5)
        row = conn.execute(
            "SELECT rowid, attempt FROM retry_queue WHERE source='github' AND source_id=? AND operation='preprocess'",
            (full_name,),
        ).fetchone()
        
        err_msg = "preprocess_failed: " + str(e)[:450]
        if row:
            rowid, attempt = row
            conn.execute(
                "UPDATE retry_queue SET attempt=?, status='abandoned', last_error=?, next_retry_at=?, updated_at=? WHERE rowid=?",
                (attempt + 1, err_msg, next_retry.strftime("%Y-%m-%dT%H:%M:%SZ"), now.strftime("%Y-%m-%dT%H:%M:%SZ"), rowid),
            )
        else:
            conn.execute(
                """INSERT INTO retry_queue
                   (source, source_id, operation, attempt, max_attempts, last_error, next_retry_at, created_at, status, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "github",
                    full_name,
                    "preprocess",
                    1,
                    3,
                    err_msg,
                    next_retry.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "abandoned",
                    now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ),
            )
        conn.commit()
        raise
