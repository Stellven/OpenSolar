"""topic.py — TopicAdapter: GitHub Search API per topic query.

Reads topic definitions from the config file, queries GitHub Search API
for each, and returns DiscoveryCandidate objects.

Handles rate limiting with exponential backoff.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import yaml

from .base import DiscoveryCandidate

logger = logging.getLogger(__name__)

# Default path for config
_DEFAULT_CONFIG_PATH = "/Users/lisihao/Solar/harness/config/github_intelligence_config.yaml"


class TopicAdapter:
    """Discover repos by querying GitHub Search API per topic."""

    def __init__(
        self,
        *,
        config_path: str = _DEFAULT_CONFIG_PATH,
        github_token: str | None = None,
        max_results_per_topic: int = 100,
    ) -> None:
        self._config_path = config_path
        self._github_token = github_token
        self._max_results = max_results_per_topic
        self._topics: list[dict[str, Any]] = []
        self._load_config()

    def _load_config(self) -> None:
        """Load topic definitions from config file."""
        try:
            with open(self._config_path) as f:
                config = yaml.safe_load(f)
            self._topics = config.get("discovery", {}).get("topics", [])
        except (OSError, yaml.YAMLError) as e:
            logger.warning("Failed to load config from %s: %s", self._config_path, e)
            self._topics = []

    def run(self, since: str | None = None) -> list[DiscoveryCandidate]:
        """Query GitHub Search API for each topic.

        Parameters
        ----------
        since : str, optional
            ISO timestamp filter.

        Returns
        -------
        list[DiscoveryCandidate]
        """
        candidates: list[DiscoveryCandidate] = []

        for topic_def in self._topics:
            try:
                topic_candidates = self._query_topic(topic_def, since)
                candidates.extend(topic_candidates)
            except Exception as e:
                logger.error(
                    "TopicAdapter error for topic %s: %s",
                    topic_def.get("name", "?"), e,
                )
                # Adapter failure → log + skip, do not block other adapters

        return candidates

    def _query_topic(
        self,
        topic_def: dict[str, Any],
        since: str | None,
    ) -> list[DiscoveryCandidate]:
        """Query a single topic definition.

        In production, this calls the GitHub Search API.
        Currently returns structured candidates from the config definition.
        """
        name = topic_def.get("name", "unknown")
        query = topic_def.get("query", "")
        star_range = topic_def.get("star_range", [0, 100000])
        recency = topic_def.get("recency", "30d")

        # Build GitHub Search API URL
        # GET https://api.github.com/search/repositories?q={query}+stars:{min}..{max}+pushed:>{since}
        search_query = query
        if star_range and len(star_range) == 2:
            search_query += f" stars:{star_range[0]}..{star_range[1]}"
        if since:
            search_query += f" pushed:>{since}"

        # Attempt real GitHub API call
        results = self._call_github_api(search_query)

        if results is None:
            # API unavailable — return empty (no crash)
            return []

        candidates: list[DiscoveryCandidate] = []
        for item in results:
            full_name = item.get("full_name", "")
            if not full_name:
                continue
            candidates.append(
                DiscoveryCandidate(
                    full_name=full_name,
                    source_type="topic",
                    metadata={
                        "topic_name": name,
                        "stars": item.get("stargazers_count", 0),
                        "description": item.get("description", ""),
                        "language": item.get("language", ""),
                    },
                )
            )

        return candidates[:self._max_results]

    def _call_github_api(self, query: str) -> list[dict[str, Any]] | None:
        """Call GitHub Search API with rate limit backoff.

        Returns None if API is unavailable (no crash).
        """
        try:
            import urllib.request
            import json as json_mod

            url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(query)}&sort=stars&order=desc&per_page={self._max_results}"
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Solar-GitHub-Intelligence/1.0",
            }
            if self._github_token:
                headers["Authorization"] = f"token {self._github_token}"

            max_retries = 3
            for attempt in range(max_retries):
                req = urllib.request.Request(url, headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        data = json_mod.loads(resp.read().decode())
                        return data.get("items", [])
                except urllib.error.HTTPError as e:
                    if e.code in (403, 429):
                        # Rate limit — exponential backoff
                        wait = 2 ** attempt * 5
                        logger.warning(
                            "GitHub API rate limit (attempt %d/%d), waiting %ds",
                            attempt + 1, max_retries, wait,
                        )
                        time.sleep(wait)
                        continue
                    raise
                except urllib.error.URLError:
                    return None

            logger.error("GitHub API rate limit exhausted after %d retries", max_retries)
            return None

        except ImportError:
            return None
        except Exception as e:
            logger.error("GitHub API call failed: %s", e)
            return None
