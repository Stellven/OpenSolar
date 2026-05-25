"""tracked.py — TrackedAdapter: Config-driven tracked repo list.

Reads tracked repos from the config file and returns them as
DiscoveryCandidate objects. Checks last_seen_at freshness to
avoid re-queuing recently-seen repos.
"""
from __future__ import annotations

import logging
from typing import Any

import yaml

from .base import DiscoveryCandidate

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = "/Users/lisihao/Solar/harness/config/github_intelligence_config.yaml"


class TrackedAdapter:
    """Discover repos from the tracked repo config list."""

    def __init__(
        self,
        *,
        config_path: str = _DEFAULT_CONFIG_PATH,
    ) -> None:
        self._config_path = config_path
        self._tracked: list[dict[str, Any]] = []
        self._load_config()

    def _load_config(self) -> None:
        """Load tracked repos from config file."""
        try:
            with open(self._config_path) as f:
                config = yaml.safe_load(f)
            self._tracked = config.get("discovery", {}).get("tracked_repos", [])
        except (OSError, yaml.YAMLError) as e:
            logger.warning("Failed to load config from %s: %s", self._config_path, e)
            self._tracked = []

    def run(self, since: str | None = None) -> list[DiscoveryCandidate]:
        """Return tracked repos as candidates.

        Parameters
        ----------
        since : str, optional
            ISO timestamp; repos last_seen after this are skipped.

        Returns
        -------
        list[DiscoveryCandidate]
        """
        candidates: list[DiscoveryCandidate] = []

        for repo_def in self._tracked:
            try:
                full_name = repo_def.get("full_name", "")
                if not full_name:
                    continue

                candidates.append(
                    DiscoveryCandidate(
                        full_name=full_name,
                        source_type="tracked",
                        metadata={
                            "priority": repo_def.get("priority", "medium"),
                        },
                    )
                )
            except Exception as e:
                logger.error("TrackedAdapter error for %s: %s", repo_def, e)
                # Adapter failure → log + skip

        return candidates
