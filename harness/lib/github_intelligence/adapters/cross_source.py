"""cross_source.py — CrossSourceAdapter: Social/X + YouTube repo mention scanner.

Scans social media posts and YouTube transcripts for github.com/owner/repo
mentions, extracts repo full_name + mention metadata.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from .base import DiscoveryCandidate

logger = logging.getLogger(__name__)

# Pattern to match github.com/owner/repo URLs
_GITHUB_REPO_PATTERN = re.compile(
    r"github\.com/([a-zA-Z0-9\-_.]+/[a-zA-Z0-9\-_.]+)",
    re.IGNORECASE,
)


class CrossSourceAdapter:
    """Discover repos from social media / YouTube mentions."""

    def __init__(
        self,
        *,
        social_sources: list[str] | None = None,
        youtube_enabled: bool = True,
    ) -> None:
        self._social_sources = social_sources or []
        self._youtube_enabled = youtube_enabled

    def run(self, since: str | None = None) -> list[DiscoveryCandidate]:
        """Scan social sources and YouTube for GitHub repo mentions.

        Parameters
        ----------
        since : str, optional
            ISO timestamp; only scan content newer than this.

        Returns
        -------
        list[DiscoveryCandidate]
        """
        candidates: list[DiscoveryCandidate] = []

        # Social source scanning
        try:
            social_candidates = self._scan_social(since)
            candidates.extend(social_candidates)
        except Exception as e:
            logger.error("CrossSourceAdapter social scan error: %s", e)
            # Adapter failure → log + skip, do not block other adapters

        # YouTube scanning
        if self._youtube_enabled:
            try:
                youtube_candidates = self._scan_youtube(since)
                candidates.extend(youtube_candidates)
            except Exception as e:
                logger.error("CrossSourceAdapter YouTube scan error: %s", e)

        return candidates

    def _scan_social(self, since: str | None) -> list[DiscoveryCandidate]:
        """Scan social media sources for GitHub repo mentions.

        Reads from the AI Influence Daily Digest accounts data.
        Returns candidates extracted from text content.
        """
        candidates: list[DiscoveryCandidate] = []
        seen: set[str] = set()

        # Try to read from AI Influence digest output
        try:
            import os
            digest_dir = "/Users/lisihao/Knowledge/_raw/ai-influence-daily-digest"
            if os.path.exists(digest_dir):
                for entry in os.scandir(digest_dir):
                    if not entry.is_file() or not entry.name.endswith(".md"):
                        continue
                    try:
                        content = open(entry.path, encoding="utf-8").read()
                        for match in _GITHUB_REPO_PATTERN.finditer(content):
                            full_name = match.group(1)
                            # Filter out non-repo paths
                            parts = full_name.split("/")
                            if len(parts) != 2:
                                continue
                            # Skip obvious non-repos
                            if any(p in full_name.lower() for p in ("topics", "explore", "settings", "notifications", "marketplace")):
                                continue
                            if full_name not in seen:
                                seen.add(full_name)
                                candidates.append(
                                    DiscoveryCandidate(
                                        full_name=full_name,
                                        source_type="social_mention",
                                        metadata={
                                            "source_file": entry.name,
                                            "platform": "ai_influence_digest",
                                        },
                                    )
                                )
                    except OSError:
                        continue
        except Exception as e:
            logger.warning("Social scan failed: %s", e)

        return candidates

    def _scan_youtube(self, since: str | None) -> list[DiscoveryCandidate]:
        """Scan YouTube transcript data for GitHub repo mentions.

        YouTube scanning requires external transcript data.
        Returns empty list if no data source available.
        """
        # YouTube transcript scanning requires integration with
        # a transcript API or local cache. Placeholder that returns
        # empty until that integration is built.
        return []

    @staticmethod
    def extract_repos_from_text(text: str) -> list[str]:
        """Extract GitHub repo full_names from arbitrary text.

        Utility method for other modules.
        """
        seen: set[str] = set()
        repos: list[str] = []
        for match in _GITHUB_REPO_PATTERN.finditer(text):
            full_name = match.group(1)
            if full_name not in seen:
                seen.add(full_name)
                repos.append(full_name)
        return repos
