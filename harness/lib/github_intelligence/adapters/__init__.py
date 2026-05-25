"""adapters — 4 discovery adapters + dedup queue for GitHub Project Intelligence.

Adapters:
1. TopicAdapter — GitHub Search API per topic query
2. TrendingAdapter — GitHub Trending page scraper
3. TrackedAdapter — Config-driven tracked repo list
4. CrossSourceAdapter — Social/X + YouTube repo mention scanner

Each adapter implements the DiscoveryAdapter protocol and returns
list[DiscoveryCandidate] with dedup against the repo_master table.

Spec: design.md §A1 (Discovery Pipeline) + scoring-contract.md §1
Node: B3
"""
from __future__ import annotations

from .base import DiscoveryCandidate, DiscoveryAdapter, DedupQueue
from .topic import TopicAdapter
from .trending import TrendingAdapter
from .tracked import TrackedAdapter
from .cross_source import CrossSourceAdapter

__all__ = [
    "DiscoveryCandidate",
    "DiscoveryAdapter",
    "DedupQueue",
    "TopicAdapter",
    "TrendingAdapter",
    "TrackedAdapter",
    "CrossSourceAdapter",
]
