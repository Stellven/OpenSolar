"""trending.py — TrendingAdapter: GitHub Trending page scraper.

Scrapes GitHub Trending daily/weekly/monthly pages and normalizes
results into DiscoveryCandidate objects.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from .base import DiscoveryCandidate

logger = logging.getLogger(__name__)


class TrendingAdapter:
    """Discover repos from GitHub Trending pages."""

    def __init__(
        self,
        *,
        ranges: tuple[str, ...] = ("daily", "weekly"),
        github_token: str | None = None,
    ) -> None:
        self._ranges = ranges
        self._github_token = github_token

    def run(self, since: str | None = None) -> list[DiscoveryCandidate]:
        """Scrape GitHub Trending pages for each range.

        Parameters
        ----------
        since : str, optional
            Not used for trending (pages are already time-filtered).

        Returns
        -------
        list[DiscoveryCandidate]
        """
        candidates: list[DiscoveryCandidate] = []

        for range_type in self._ranges:
            try:
                items = self._scrape_trending(range_type)
                candidates.extend(items)
            except Exception as e:
                logger.error("TrendingAdapter error for %s: %s", range_type, e)
                # Adapter failure → log + skip, do not block other adapters

        return candidates

    def _scrape_trending(self, range_type: str) -> list[DiscoveryCandidate]:
        """Scrape a single trending page.

        Attempts real fetch from GitHub trending URL.
        Falls back to empty list on failure (no crash).
        """
        try:
            import urllib.request
            import json as json_mod

            url = f"https://api.github.com/search/repositories?q=created:>{range_type}&sort=stars&order=desc&per_page=25"
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Solar-GitHub-Intelligence/1.0",
            }
            if self._github_token:
                headers["Authorization"] = f"token {self._github_token}"

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json_mod.loads(resp.read().decode())
                items = data.get("items", [])

            candidates: list[DiscoveryCandidate] = []
            for item in items:
                full_name = item.get("full_name", "")
                if not full_name:
                    continue
                candidates.append(
                    DiscoveryCandidate(
                        full_name=full_name,
                        source_type="trending",
                        metadata={
                            "range": range_type,
                            "stars": item.get("stargazers_count", 0),
                            "description": item.get("description", ""),
                            "language": item.get("language", ""),
                        },
                    )
                )
            return candidates

        except ImportError:
            return []
        except Exception as e:
            logger.warning("TrendingAdapter scrape failed for %s: %s", range_type, e)
            return []
