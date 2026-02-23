"""GitHub API client for repository discovery and access."""

import re
from typing import Iterator

from github import Auth, Github, GithubException
from rich.console import Console

from .models import RepoInfo

console = Console()


class GitHubClient:
    """Client for interacting with GitHub API."""

    def __init__(
        self,
        token: str,
        orgs: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ):
        self.gh = Github(auth=Auth.Token(token))
        self.orgs = orgs or []
        self.exclude_patterns = [
            re.compile(p) for p in (exclude_patterns or [])
        ]

    def authenticate(self) -> bool:
        """Verify authentication and connection."""
        try:
            user = self.gh.get_user()
            console.print(f"[green]\u2713[/green] Connected to GitHub")
            console.print(f"  User: {user.login}")
            return True
        except GithubException as e:
            console.print(f"[red]\u2717[/red] Authentication failed: {e}")
            return False

    def _should_include(self, repo_full_name: str) -> bool:
        """Check if repository should be included based on filters."""
        if self.orgs:
            owner = repo_full_name.split("/")[0]
            if not any(owner == org for org in self.orgs):
                return False

        for pattern in self.exclude_patterns:
            if pattern.search(repo_full_name):
                return False

        return True

    def discover_projects(self) -> Iterator[RepoInfo]:
        """Discover all accessible repositories."""
        console.print("[blue]Discovering repositories...[/blue]")

        if self.orgs:
            for org_name in self.orgs:
                try:
                    org = self.gh.get_organization(org_name)
                    repos = org.get_repos(type="all", sort="updated", direction="desc")
                except GithubException:
                    # Fall back to user repos filtered by org name
                    repos = (
                        r for r in self.gh.get_user().get_repos(
                            sort="updated", direction="desc"
                        )
                        if r.full_name.startswith(f"{org_name}/")
                    )

                for repo in repos:
                    if repo.archived:
                        continue
                    if not self._should_include(repo.full_name):
                        continue
                    yield self._repo_to_info(repo)
        else:
            user = self.gh.get_user()
            for repo in user.get_repos(sort="updated", direction="desc"):
                if repo.archived:
                    continue
                if not self._should_include(repo.full_name):
                    continue
                yield self._repo_to_info(repo)

    def _repo_to_info(self, repo) -> RepoInfo:
        """Convert a PyGithub repository object to RepoInfo."""
        try:
            languages = repo.get_languages()
            total = sum(languages.values()) or 1
            languages = {k: (v / total) * 100 for k, v in languages.items()}
        except GithubException:
            languages = {}

        return RepoInfo(
            id=repo.id,
            name=repo.name,
            path=repo.name,
            full_path=repo.full_name,
            description=repo.description,
            default_branch=repo.default_branch or "main",
            http_url=repo.clone_url,
            ssh_url=repo.ssh_url,
            languages=languages,
            topics=repo.get_topics(),
            last_activity=repo.updated_at.isoformat() if repo.updated_at else "",
        )

    def get_project_files(
        self,
        repo_full_name: str,
        branch: str = "main",
        path: str = "",
    ) -> Iterator[dict]:
        """Get file tree for a repository without cloning."""
        repo = self.gh.get_repo(repo_full_name)

        try:
            contents = repo.get_contents(path, ref=branch)
            while contents:
                item = contents.pop(0)
                yield {"name": item.name, "path": item.path, "type": item.type}
                if item.type == "dir":
                    contents.extend(repo.get_contents(item.path, ref=branch))
        except GithubException:
            console.print(
                f"[yellow]Warning: Could not access tree for {repo_full_name}[/yellow]"
            )

    def get_file_content(
        self,
        repo_full_name: str,
        file_path: str,
        branch: str = "main",
    ) -> str | None:
        """Get raw file content."""
        repo = self.gh.get_repo(repo_full_name)

        try:
            content = repo.get_contents(file_path, ref=branch)
            return content.decoded_content.decode("utf-8")
        except Exception:
            return None
