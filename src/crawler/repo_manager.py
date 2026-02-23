"""Repository cloning and management."""

import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from .models import RepoInfo

console = Console()


@dataclass
class ClonedRepo:
    """Information about a cloned repository."""
    info: RepoInfo
    local_path: Path
    success: bool
    error: str | None = None


class RepoManager:
    """Manages local repository clones."""
    
    def __init__(
        self,
        base_path: Path | str,
        depth: int = 1,
        concurrency: int = 5,
    ):
        self.base_path = Path(base_path)
        self.depth = depth
        self.concurrency = concurrency
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def get_repo_path(self, repo: RepoInfo) -> Path:
        """Get local path for a repository."""
        return self.base_path / repo.full_path
    
    def clone_repo(self, repo: RepoInfo) -> ClonedRepo:
        """Clone a single repository."""
        local_path = self.get_repo_path(repo)
        
        # Skip if already exists
        if local_path.exists() and (local_path / ".git").exists():
            return ClonedRepo(
                info=repo,
                local_path=local_path,
                success=True,
            )
        
        # Create parent directories
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Build clone command
        cmd = ["git", "clone"]
        if self.depth > 0:
            cmd.extend(["--depth", str(self.depth)])
        cmd.extend(["--branch", repo.default_branch])
        cmd.extend([repo.http_url, str(local_path)])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            
            if result.returncode != 0:
                return ClonedRepo(
                    info=repo,
                    local_path=local_path,
                    success=False,
                    error=result.stderr,
                )
            
            return ClonedRepo(
                info=repo,
                local_path=local_path,
                success=True,
            )
            
        except subprocess.TimeoutExpired:
            return ClonedRepo(
                info=repo,
                local_path=local_path,
                success=False,
                error="Clone timed out",
            )
        except Exception as e:
            return ClonedRepo(
                info=repo,
                local_path=local_path,
                success=False,
                error=str(e),
            )
    
    def clone_repos(self, repos: list[RepoInfo]) -> list[ClonedRepo]:
        """Clone multiple repositories concurrently."""
        results = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            console=console,
        ) as progress:
            task = progress.add_task("Cloning repos...", total=len(repos))
            
            with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
                futures = {
                    executor.submit(self.clone_repo, repo): repo
                    for repo in repos
                }
                
                for future in as_completed(futures):
                    result = future.result()
                    results.append(result)
                    
                    if result.success:
                        progress.console.print(
                            f"  [green]✓[/green] {result.info.full_path}"
                        )
                    else:
                        progress.console.print(
                            f"  [red]✗[/red] {result.info.full_path}: {result.error}"
                        )
                    
                    progress.advance(task)
        
        success_count = sum(1 for r in results if r.success)
        console.print(
            f"\n[bold]Cloned {success_count}/{len(repos)} repositories[/bold]"
        )
        
        return results
    
    def update_repo(self, repo: RepoInfo) -> bool:
        """Pull latest changes for a cloned repo."""
        local_path = self.get_repo_path(repo)
        
        if not local_path.exists():
            return False
        
        try:
            subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=local_path,
                capture_output=True,
                timeout=60,
            )
            return True
        except Exception:
            return False
    
    def cleanup_repo(self, repo: RepoInfo) -> bool:
        """Remove a cloned repository."""
        local_path = self.get_repo_path(repo)
        
        if local_path.exists():
            shutil.rmtree(local_path)
            return True
        return False
