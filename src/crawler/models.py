"""Shared data models for repository crawlers."""

from dataclasses import dataclass


@dataclass
class RepoInfo:
    """Repository metadata."""
    id: int
    name: str
    path: str
    full_path: str
    description: str | None
    default_branch: str
    http_url: str
    ssh_url: str
    languages: dict[str, float]
    topics: list[str]
    last_activity: str
