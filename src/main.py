"""Main entry point for SenseBase."""

import argparse
import os
from datetime import datetime
from pathlib import Path

import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .crawler.models import RepoInfo
from .crawler.gitlab_client import GitLabClient
from .crawler.github_client import GitHubClient
from .crawler.repo_manager import RepoManager
from .analyzers.registry import create_default_registry
from .store.knowledge_base import KnowledgeBase
from .store.output import OutputGenerator

console = Console()


def load_config(config_path: Path) -> dict:
    """Load configuration from YAML file."""
    if not config_path.exists():
        console.print(f"[red]Error:[/red] Config file not found: {config_path}")
        console.print("Run ./setup.sh or copy a config template from config/ to config/config.yaml.")
        raise SystemExit(1)
    
    return yaml.safe_load(config_path.read_text())


def _get_platform(config: dict) -> str:
    """Detect which platform is configured."""
    if "local" in config:
        return "local"
    if "github" in config:
        return "github"
    return "gitlab"


def discover_local_repos(config: dict) -> list[Path]:
    """Scan local directories for code projects.

    ``config["local"]["repos_path"]`` may be a single path string or a list
    of path strings.  For each directory the logic is:

    1. If the directory itself is a git repo (``.git`` exists), treat it as a
       single project.
    2. Otherwise scan immediate subdirectories — any subdirectory that is a git
       repo **or** simply contains source files (i.e. not an empty folder) is
       included.  This covers monorepo layouts and plain code directories that
       were never ``git init``-ed.
    """
    import re

    local_config = config["local"]
    raw_paths = local_config["repos_path"]
    if isinstance(raw_paths, str):
        raw_paths = [raw_paths]

    exclude_patterns = local_config.get("exclude_patterns") or []
    compiled = [re.compile(p) for p in exclude_patterns]

    found: list[Path] = []

    for raw in raw_paths:
        repos_path = Path(raw).expanduser().resolve()
        if not repos_path.exists():
            console.print(f"[yellow]Warning:[/yellow] Local repos directory not found: {repos_path}")
            continue

        # If the path itself is a git repo, use it directly
        if (repos_path / ".git").exists():
            found.append(repos_path)
            continue

        # Scan subdirectories
        for entry in sorted(repos_path.iterdir()):
            if not entry.is_dir():
                continue
            if any(p.search(entry.name) for p in compiled):
                continue
            # Accept git repos or any non-empty directory (plain code folders)
            if (entry / ".git").exists():
                found.append(entry)
            elif any(entry.iterdir()):
                found.append(entry)

    console.print(f"[bold]Found {len(found)} repositories across {len(raw_paths)} local director{'y' if len(raw_paths) == 1 else 'ies'}[/bold]")
    return found


def _apply_semantic_enrichment(repo_result, semantic_data: dict) -> None:
    """Apply semantic enrichment from LLM back to structural dataclasses."""
    entity_descs = semantic_data.get("entity_descriptions", {})
    field_descs = semantic_data.get("field_descriptions", {})
    api_descs = semantic_data.get("api_descriptions", {})

    for schema in repo_result.schemas:
        if schema.name in entity_descs:
            schema.description = entity_descs[schema.name]

        if schema.name in field_descs:
            for field_dict in schema.fields:
                fname = field_dict.get("name", "")
                if fname in field_descs[schema.name]:
                    field_dict["description"] = field_descs[schema.name][fname]

    for api_info in repo_result.apis:
        key = f"{api_info.method} {api_info.path}"
        if key in api_descs:
            api_info.business_description = api_descs[key]


def run_crawl(config: dict) -> list[RepoInfo]:
    """Discover and list all repositories."""
    platform = _get_platform(config)

    if platform == "local":
        # Local platform doesn't use RepoInfo — handled separately
        return []

    if platform == "github":
        gh_config = config["github"]
        client = GitHubClient(
            token=gh_config.get("token", ""),
            orgs=gh_config.get("orgs"),
            exclude_patterns=gh_config.get("exclude_patterns"),
        )
    else:
        gl_config = config["gitlab"]
        client = GitLabClient(
            url=gl_config.get("url", ""),
            token=gl_config.get("token", ""),
            namespaces=gl_config.get("namespaces"),
            exclude_patterns=gl_config.get("exclude_patterns"),
        )

    if not client.authenticate():
        raise SystemExit(1)

    repos = list(client.discover_projects())
    console.print(f"[bold]Found {len(repos)} repositories[/bold]")

    return repos


def run_clone(config: dict, repos: list[RepoInfo]) -> list[Path]:
    """Clone repositories locally."""
    platform = _get_platform(config)
    clone_config = config.get(platform, {}).get("clone", {})
    
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

    # Always run pattern-based extraction first for schemas, APIs, services, deps
    console.print("[blue]Running pattern-based extraction[/blue]")

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

    # Layer LLM repo-level context on top when requested
    if use_llm:
        console.print("\n[blue]Generating LLM repo-level contexts (Claude)[/blue]")

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

        for repo_result in kb.results:
            repo_path = Path(repo_result.repo_path)
            if not repo_path.exists():
                continue
            console.print(f"\n[bold]Generating context for {repo_result.repo_name}...[/bold]")
            llm_result = analyzer.analyze_repository(repo_path)
            # Merge LLM context into existing result
            if llm_result.context:
                repo_result.context = llm_result.context
                # Re-index with context
                kb._context_index[repo_result.repo_name] = {
                    "repo_name": llm_result.context.repo_name,
                    "repo_path": llm_result.context.repo_path,
                    "context_markdown": llm_result.context.context_markdown,
                    "purpose": llm_result.context.purpose,
                    "domain": llm_result.context.domain,
                    "when_to_use": llm_result.context.when_to_use,
                    "data_ownership": llm_result.context.data_ownership,
                    "service_dependencies": llm_result.context.service_dependencies,
                    "generated_at": llm_result.context.generated_at,
                    "model": llm_result.context.model,
                    "file_count": llm_result.context.file_count,
                }

        # Semantic business layer enrichment
        console.print("\n[blue]Generating semantic business layer...[/blue]")
        from .analyzers.base import SemanticLayer
        from dataclasses import asdict as _asdict

        for repo_result in kb.results:
            if not repo_result.context:
                continue

            repo_schemas = [_asdict(s) for s in repo_result.schemas]
            repo_apis = [_asdict(a) for a in repo_result.apis]
            repo_services = [_asdict(s) for s in repo_result.business_logic]

            if not repo_schemas and not repo_apis and not repo_services:
                continue

            console.print(f"  Enriching {repo_result.repo_name}...")
            try:
                semantic_data = extractor.generate_semantic_layer(
                    context_markdown=repo_result.context.context_markdown,
                    schemas=repo_schemas,
                    apis=repo_apis,
                    services=repo_services,
                    repo_name=repo_result.repo_name,
                )

                _apply_semantic_enrichment(repo_result, semantic_data)

                repo_result.semantic_layer = SemanticLayer(
                    repo_name=repo_result.repo_name,
                    business_glossary=semantic_data.get("business_glossary", []),
                    entity_descriptions=semantic_data.get("entity_descriptions", {}),
                    field_descriptions=semantic_data.get("field_descriptions", {}),
                    query_recipes=semantic_data.get("query_recipes", []),
                    generated_at=datetime.utcnow().isoformat(),
                    model=extractor.model,
                )

                kb._reindex_repo(repo_result)

                n_ent = len(semantic_data.get("entity_descriptions", {}))
                n_rec = len(semantic_data.get("query_recipes", []))
                console.print(f"    [green]OK[/green] {n_ent} entities, {n_rec} recipes")
            except Exception as e:
                console.print(f"    [red]X[/red] {repo_result.repo_name}: {e}")

        # Cross-repo relationship extraction
        contexts = [r.context for r in kb.results if r.context]
        if contexts and len(contexts) > 1:
            console.print(f"\n[blue]Generating cross-repo relationships...[/blue]")
            from .extractors.relationship_extractor import RelationshipExtractor
            from dataclasses import asdict
            rel_extractor = RelationshipExtractor(extractor=extractor)
            rel_result = rel_extractor.generate_relationships(contexts)
            kb.set_relationships(asdict(rel_result))

    # Build relationships from context data if the LLM cross-repo call
    # produced empty results, was skipped, or wasn't requested
    rels = kb.get_relationships()
    if not rels.get("service_map") and kb.get_all_contexts():
        console.print("[blue]Building relationships from context data...[/blue]")
        kb.build_relationships_from_contexts()

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

        # Auto-index chunks into ChromaDB for semantic search
        chunks_path = Path(output_config.get("base_path", "./output")) / "vectors" / "chunks.json"
        if chunks_path.exists():
            try:
                from .query.embeddings import SemanticSearch
                chroma_path = Path(output_config.get("base_path", "./output")) / "vectors" / "chroma"
                ss = SemanticSearch(persist_dir=chroma_path)
                count = ss.index_chunks(chunks_path)
                console.print(f"[green]✓[/green] Indexed {count} chunks into ChromaDB")
            except ImportError:
                console.print("[yellow]Skipping vector indexing (install sentence-transformers & chromadb)[/yellow]")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SenseBase - Extract knowledge from GitLab, GitHub, or local repositories"
    )
    parser.add_argument(
        "--config", "-c",
        default="config/config.yaml",
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
    platform = _get_platform(config)

    # Local platform: skip discovery/clone, scan directory directly
    if platform == "local":
        if args.discover or args.clone or args.analyze:
            repo_paths = discover_local_repos(config)
            if args.discover and not args.analyze:
                console.print("\n[bold]Repositories:[/bold]")
                for p in repo_paths:
                    console.print(f"  {p.name}")
                return
    else:
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
