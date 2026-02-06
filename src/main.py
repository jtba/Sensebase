"""Main entry point for ContextPedia."""

import argparse
import os
from pathlib import Path

import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .crawler.gitlab_client import GitLabClient, RepoInfo
from .crawler.repo_manager import RepoManager
from .analyzers.registry import create_default_registry
from .store.knowledge_base import KnowledgeBase
from .store.output import OutputGenerator

console = Console()


def load_config(config_path: Path) -> dict:
    """Load configuration from YAML file."""
    if not config_path.exists():
        console.print(f"[red]Error:[/red] Config file not found: {config_path}")
        console.print("Copy config/gitlab.example.yaml to config/gitlab.yaml and configure it.")
        raise SystemExit(1)
    
    return yaml.safe_load(config_path.read_text())


def run_crawl(config: dict) -> list[RepoInfo]:
    """Discover and list all repositories."""
    gitlab_config = config.get("gitlab", {})
    
    client = GitLabClient(
        url=gitlab_config.get("url", ""),
        token=gitlab_config.get("token", ""),
        namespaces=gitlab_config.get("namespaces"),
        exclude_patterns=gitlab_config.get("exclude_patterns"),
    )
    
    if not client.authenticate():
        raise SystemExit(1)
    
    repos = list(client.discover_projects())
    console.print(f"[bold]Found {len(repos)} repositories[/bold]")
    
    return repos


def run_clone(config: dict, repos: list[RepoInfo]) -> list[Path]:
    """Clone repositories locally."""
    clone_config = config.get("gitlab", {}).get("clone", {})
    
    manager = RepoManager(
        base_path=clone_config.get("base_path", "./repos"),
        depth=clone_config.get("depth", 1),
        concurrency=clone_config.get("concurrency", 5),
    )
    
    results = manager.clone_repos(repos)
    
    return [r.local_path for r in results if r.success]


def run_analyze(config: dict, repo_paths: list[Path], use_llm: bool = False) -> KnowledgeBase:
    """Analyze repositories and build knowledge base."""
    analysis_config = config.get("analysis", {})
    output_config = config.get("output", {})
    
    kb = KnowledgeBase(output_dir=output_config.get("base_path", "./output"))
    
    if use_llm:
        # Use LLM-based extraction
        console.print("[blue]Using LLM extraction (Claude)[/blue]")
        
        from .extractors.llm_extractor import LLMExtractor, LLMAnalyzer
        
        llm_config = config.get("llm", {})
        extractor = LLMExtractor(
            api_key=llm_config.get("api_key") or os.environ.get("ANTHROPIC_API_KEY"),
            model=llm_config.get("model", "claude-sonnet-4-20250514"),
            cache_dir=llm_config.get("cache_dir", "./output/cache/llm"),
            max_file_size=analysis_config.get("max_file_size", 100_000),
            requests_per_minute=llm_config.get("requests_per_minute", 50),
        )
        
        analyzer = LLMAnalyzer(
            extractor=extractor,
            skip_dirs=analysis_config.get("skip_dirs"),
            include_extensions=analysis_config.get("include_extensions"),
            max_file_size=analysis_config.get("max_file_size", 100_000),
        )
        
        for repo_path in repo_paths:
            console.print(f"\n[bold]Analyzing {repo_path.name}...[/bold]")
            result = analyzer.analyze_repository(repo_path)
            kb.add_result(result)
    else:
        # Use regex/AST-based extraction
        console.print("[blue]Using pattern-based extraction[/blue]")
        
        registry = create_default_registry()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing repositories...", total=len(repo_paths))
            
            for repo_path in repo_paths:
                progress.update(task, description=f"Analyzing {repo_path.name}...")
                
                result = registry.analyze_repository(
                    repo_path,
                    skip_dirs=analysis_config.get("skip_dirs"),
                    include_extensions=analysis_config.get("include_extensions"),
                    max_file_size=analysis_config.get("max_file_size", 1_048_576),
                )
                
                kb.add_result(result)
                progress.advance(task)
    
    summary = kb.get_summary()
    console.print(f"\n[bold]Analysis Complete[/bold]")
    console.print(f"  Repositories: {summary['repositories_analyzed']}")
    console.print(f"  Schemas: {summary['total_schemas']}")
    console.print(f"  APIs: {summary['total_apis']}")
    console.print(f"  Services: {summary['total_services']}")
    console.print(f"  Dependencies: {summary['total_dependencies']}")
    
    return kb


def run_generate(config: dict, kb: KnowledgeBase) -> None:
    """Generate output in all formats."""
    output_config = config.get("output", {})
    formats = output_config.get("formats", {})
    
    generator = OutputGenerator(
        kb=kb,
        output_dir=output_config.get("base_path", "./output"),
    )
    
    if formats.get("json", True):
        generator.generate_json()
    
    if formats.get("markdown", True):
        generator.generate_markdown()
    
    if formats.get("vectors", True):
        generator.generate_vector_chunks()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="ContextPedia - Extract knowledge from GitLab repositories"
    )
    parser.add_argument(
        "--config", "-c",
        default="config/gitlab.yaml",
        help="Path to configuration file",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Only discover repositories (don't clone or analyze)",
    )
    parser.add_argument(
        "--clone",
        action="store_true",
        help="Clone repositories (skip if already cloned)",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Analyze cloned repositories",
    )
    parser.add_argument(
        "--output-all",
        action="store_true",
        help="Generate all output formats",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full pipeline: discover → clone → analyze → generate",
    )
    parser.add_argument(
        "--repos-dir",
        help="Directory containing already-cloned repos (skip clone step)",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Use LLM (Claude) for extraction instead of pattern matching",
    )
    parser.add_argument(
        "--llm-model",
        default="claude-sonnet-4-20250514",
        help="Claude model for LLM extraction (default: claude-sonnet-4-20250514)",
    )
    
    args = parser.parse_args()
    
    config = load_config(Path(args.config))
    
    # Override LLM model from CLI
    if args.llm_model:
        if "llm" not in config:
            config["llm"] = {}
        config["llm"]["model"] = args.llm_model
    
    # Determine what to run
    if args.full:
        args.discover = True
        args.clone = True
        args.analyze = True
        args.output_all = True
    
    if not any([args.discover, args.clone, args.analyze, args.output_all]):
        parser.print_help()
        return
    
    repos: list[RepoInfo] = []
    repo_paths: list[Path] = []
    kb: KnowledgeBase | None = None
    
    # Discovery
    if args.discover or args.clone:
        repos = run_crawl(config)
        
        if args.discover and not args.clone:
            console.print("\n[bold]Repositories:[/bold]")
            for repo in repos[:50]:
                lang_str = ", ".join(f"{k}: {v:.0f}%" for k, v in list(repo.languages.items())[:3])
                console.print(f"  {repo.full_path} ({lang_str})")
            if len(repos) > 50:
                console.print(f"  ... and {len(repos) - 50} more")
            return
    
    # Clone
    if args.clone:
        repo_paths = run_clone(config, repos)
    elif args.repos_dir:
        # Use existing repos directory
        repos_dir = Path(args.repos_dir)
        repo_paths = [p for p in repos_dir.rglob("*") if (p / ".git").exists()]
        console.print(f"Found {len(repo_paths)} repositories in {repos_dir}")
    
    # Analyze
    if args.analyze and repo_paths:
        kb = run_analyze(config, repo_paths, use_llm=args.llm)
    
    # Generate output
    if args.output_all and kb:
        run_generate(config, kb)
        console.print(f"\n[green]✓[/green] Output generated in {config.get('output', {}).get('base_path', './output')}")


if __name__ == "__main__":
    main()
