"""GitLab API client for repository discovery and access."""

import re
from typing import Iterator

import gitlab
from rich.console import Console

from .models import RepoInfo

console = Console()



class GitLabClient:
    """Client for interacting with GitLab API."""
    
    def __init__(
        self,
        url: str,
        token: str,
        namespaces: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ):
        self.url = url
        self.gl = gitlab.Gitlab(url, private_token=token)
        self.namespaces = namespaces or []
        self.exclude_patterns = [
            re.compile(p) for p in (exclude_patterns or [])
        ]
        
    def authenticate(self) -> bool:
        """Verify authentication and connection."""
        try:
            self.gl.auth()
            console.print(f"[green]✓[/green] Connected to {self.url}")
            console.print(f"  User: {self.gl.user.username}")
            return True
        except gitlab.exceptions.GitlabAuthenticationError as e:
            console.print(f"[red]✗[/red] Authentication failed: {e}")
            return False
    
    def _should_include(self, project_path: str) -> bool:
        """Check if project should be included based on filters."""
        # Check namespace filter
        if self.namespaces:
            if not any(project_path.startswith(ns) for ns in self.namespaces):
                return False
        
        # Check exclusion patterns
        for pattern in self.exclude_patterns:
            if pattern.search(project_path):
                return False
        
        return True
    
    def discover_projects(self) -> Iterator[RepoInfo]:
        """Discover all accessible projects."""
        console.print("[blue]Discovering projects...[/blue]")
        
        projects = self.gl.projects.list(
            iterator=True,
            membership=True,
            archived=False,
            order_by="last_activity_at",
            sort="desc",
        )
        
        for project in projects:
            if not self._should_include(project.path_with_namespace):
                continue
            
            # Get language breakdown
            try:
                languages = project.languages()
            except Exception:
                languages = {}
            
            yield RepoInfo(
                id=project.id,
                name=project.name,
                path=project.path,
                full_path=project.path_with_namespace,
                description=project.description,
                default_branch=project.default_branch or "main",
                http_url=project.http_url_to_repo,
                ssh_url=project.ssh_url_to_repo,
                languages=languages,
                topics=project.topics or [],
                last_activity=project.last_activity_at,
            )
    
    def get_project_files(
        self,
        project_id: int,
        branch: str = "main",
        path: str = "",
    ) -> Iterator[dict]:
        """Get file tree for a project without cloning."""
        project = self.gl.projects.get(project_id)
        
        try:
            items = project.repository_tree(
                path=path,
                ref=branch,
                recursive=True,
                iterator=True,
            )
            for item in items:
                yield item
        except gitlab.exceptions.GitlabGetError:
            console.print(f"[yellow]Warning: Could not access tree for project {project_id}[/yellow]")
    
    def get_file_content(
        self,
        project_id: int,
        file_path: str,
        branch: str = "main",
    ) -> str | None:
        """Get raw file content."""
        project = self.gl.projects.get(project_id)
        
        try:
            f = project.files.get(file_path=file_path, ref=branch)
            return f.decode().decode("utf-8")
        except Exception:
            return None
