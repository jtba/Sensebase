"""Central knowledge base that aggregates analysis results."""

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..analyzers.base import AnalysisResult


class KnowledgeBase:
    """Aggregates and indexes extracted knowledge."""
    
    def __init__(self, output_dir: Path | str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.results: list[AnalysisResult] = []

        # Indexes for quick lookup
        self._schema_index: dict[str, list[dict]] = {}  # name -> [schemas]
        self._api_index: dict[str, list[dict]] = {}  # path -> [endpoints]
        self._dependency_index: dict[str, list[dict]] = {}  # name -> [deps]
        self._service_index: dict[str, list[dict]] = {}  # name -> [services]
        self._context_index: dict[str, dict] = {}  # repo_name -> context data
        self._semantic_index: dict[str, dict] = {}  # repo_name -> semantic layer
        self._relationships: dict = {}  # cross-repo relationships
    
    def add_result(self, result: AnalysisResult) -> None:
        """Add analysis result and update indexes."""
        self.results.append(result)
        
        # Index schemas
        for schema in result.schemas:
            key = schema.name.lower()
            if key not in self._schema_index:
                self._schema_index[key] = []
            self._schema_index[key].append({
                "repo": result.repo_name,
                "path": result.repo_path,
                **asdict(schema),
            })
        
        # Index APIs
        for api in result.apis:
            key = api.path
            if key not in self._api_index:
                self._api_index[key] = []
            self._api_index[key].append({
                "repo": result.repo_name,
                "path": result.repo_path,
                **asdict(api),
            })
        
        # Index dependencies
        for dep in result.dependencies:
            key = dep.name.lower()
            if key not in self._dependency_index:
                self._dependency_index[key] = []
            self._dependency_index[key].append({
                "repo": result.repo_name,
                "path": result.repo_path,
                **asdict(dep),
            })
        
        # Index services
        for service in result.business_logic:
            key = service.name.lower()
            if key not in self._service_index:
                self._service_index[key] = []
            self._service_index[key].append({
                "repo": result.repo_name,
                "path": result.repo_path,
                **asdict(service),
            })

        # Index context
        if result.context:
            self._context_index[result.repo_name] = {
                "repo_name": result.context.repo_name,
                "repo_path": result.context.repo_path,
                "context_markdown": result.context.context_markdown,
                "purpose": result.context.purpose,
                "domain": result.context.domain,
                "when_to_use": result.context.when_to_use,
                "data_ownership": result.context.data_ownership,
                "service_dependencies": result.context.service_dependencies,
                "generated_at": result.context.generated_at,
                "model": result.context.model,
                "file_count": result.context.file_count,
            }

        # Index semantic layer
        if result.semantic_layer:
            self._semantic_index[result.repo_name] = {
                "repo_name": result.semantic_layer.repo_name,
                "business_glossary": result.semantic_layer.business_glossary,
                "entity_descriptions": result.semantic_layer.entity_descriptions,
                "field_descriptions": result.semantic_layer.field_descriptions,
                "query_recipes": result.semantic_layer.query_recipes,
                "generated_at": result.semantic_layer.generated_at,
                "model": result.semantic_layer.model,
            }

    def _reindex_repo(self, result) -> None:
        """Re-index a single repo's data after enrichment."""
        repo_name = result.repo_name

        # Remove old schema entries for this repo and re-add
        for key in list(self._schema_index.keys()):
            self._schema_index[key] = [s for s in self._schema_index[key] if s.get("repo") != repo_name]
            if not self._schema_index[key]:
                del self._schema_index[key]

        for schema in result.schemas:
            key = schema.name.lower()
            if key not in self._schema_index:
                self._schema_index[key] = []
            self._schema_index[key].append({
                "repo": repo_name,
                "path": result.repo_path,
                **asdict(schema),
            })

        # Remove old API entries for this repo and re-add
        for key in list(self._api_index.keys()):
            self._api_index[key] = [a for a in self._api_index[key] if a.get("repo") != repo_name]
            if not self._api_index[key]:
                del self._api_index[key]

        for api in result.apis:
            key = api.path
            if key not in self._api_index:
                self._api_index[key] = []
            self._api_index[key].append({
                "repo": repo_name,
                "path": result.repo_path,
                **asdict(api),
            })

        # Re-index semantic layer
        if result.semantic_layer:
            self._semantic_index[repo_name] = {
                "repo_name": result.semantic_layer.repo_name,
                "business_glossary": result.semantic_layer.business_glossary,
                "entity_descriptions": result.semantic_layer.entity_descriptions,
                "field_descriptions": result.semantic_layer.field_descriptions,
                "query_recipes": result.semantic_layer.query_recipes,
                "generated_at": result.semantic_layer.generated_at,
                "model": result.semantic_layer.model,
            }

    def set_relationships(self, relationships: dict) -> None:
        """Set cross-repo relationship data."""
        self._relationships = relationships

    def build_relationships_from_contexts(self) -> None:
        """Build relationship data directly from repo contexts.

        This synthesises the ``service_map``, ``data_routing``, and
        ``service_chains`` structures that the webapp Relationships page
        expects, using the per-repo context data (purpose, domain,
        data_ownership, service_dependencies) that was already generated by
        the LLM extraction pass — no additional LLM call needed.
        """
        from datetime import datetime

        contexts = self.get_all_contexts()
        if not contexts:
            return

        service_map: list[dict] = []
        data_routing: list[dict] = []
        # Build a lookup of repo_name -> context for cross-referencing
        ctx_by_name: dict[str, dict] = {c["repo_name"]: c for c in contexts}

        for ctx in contexts:
            repo = ctx.get("repo_name", "")
            purpose = ctx.get("purpose", "")
            domain = ctx.get("domain", "")
            data_owned = []
            for entity in ctx.get("data_ownership", []):
                name = entity.get("entity", "")
                if name:
                    data_owned.append(name)

            use_when = ctx.get("when_to_use", []) or []

            # Build "instead_of" from service_dependencies context
            instead_of: list[dict] = []
            deps = ctx.get("service_dependencies", []) or []

            service_map.append({
                "service": repo,
                "purpose": purpose,
                "domain": domain,
                "data_owned": data_owned,
                "use_when": use_when,
                "instead_of": instead_of,
            })

            # Build data_routing entries from data_ownership
            for entity in ctx.get("data_ownership", []):
                name = entity.get("entity", "")
                is_sot = entity.get("is_source_of_truth", False)
                if name and is_sot:
                    # Find other services that mention this entity
                    also_in: list[dict] = []
                    for other_ctx in contexts:
                        if other_ctx["repo_name"] == repo:
                            continue
                        for other_entity in other_ctx.get("data_ownership", []):
                            if other_entity.get("entity", "") == name and not other_entity.get("is_source_of_truth"):
                                also_in.append({
                                    "service": other_ctx["repo_name"],
                                    "freshness": "eventual",
                                    "notes": other_entity.get("description", ""),
                                })
                    data_routing.append({
                        "entity": name,
                        "source_of_truth": repo,
                        "also_available_in": also_in,
                        "query_this_when": entity.get("description", ""),
                    })

        # Build service chains from dependency relationships.
        # Walk service_dependencies to find chains of services that call
        # each other.
        service_chains: list[dict] = []
        all_repo_names = set(ctx_by_name.keys())

        # Build adjacency: repo -> list of repos it depends on
        dep_graph: dict[str, list[str]] = {}
        for ctx in contexts:
            repo = ctx["repo_name"]
            dep_repos: list[str] = []
            for dep in ctx.get("service_dependencies", []) or []:
                dep_svc = dep.get("service", "")
                # Match dependency name to a known repo
                for rn in all_repo_names:
                    if rn != repo and (rn.lower() in dep_svc.lower() or dep_svc.lower() in rn.lower()):
                        dep_repos.append(rn)
                        break
            if dep_repos:
                dep_graph[repo] = dep_repos

        # Find chains: start from services that are depended upon by others
        # but have no inbound dependencies themselves (roots)
        depended_on = set()
        for deps in dep_graph.values():
            depended_on.update(deps)
        roots = depended_on - set(dep_graph.keys())
        # Also add services that depend on others but aren't depended on
        if not roots:
            roots = set(dep_graph.keys())

        seen_chains: set[str] = set()
        for root in sorted(roots):
            # Walk forward: find services that depend on this root
            chain_steps: list[dict] = []
            root_ctx = ctx_by_name.get(root, {})
            chain_steps.append({
                "service": root,
                "action": (root_ctx.get("purpose", "") or "Provides data/services")[:120],
                "data_passed": "",
            })
            # Find all services that list root as a dependency
            for repo, deps in dep_graph.items():
                if root in deps:
                    repo_ctx = ctx_by_name.get(repo, {})
                    chain_steps.append({
                        "service": repo,
                        "action": (repo_ctx.get("purpose", "") or "Processes data")[:120],
                        "data_passed": root,
                    })

            if len(chain_steps) >= 2:
                chain_key = "|".join(sorted(s["service"] for s in chain_steps))
                if chain_key not in seen_chains:
                    seen_chains.add(chain_key)
                    service_chains.append({
                        "name": f"{root} Dependency Chain",
                        "description": f"Services that depend on {root}",
                        "steps": chain_steps,
                    })

        self._relationships = {
            "service_map": service_map,
            "data_routing": data_routing,
            "service_chains": service_chains,
            "generated_at": datetime.utcnow().isoformat(),
            "model": "context-derived",
            "repo_count": len(contexts),
        }

    def get_context(self, repo_name: str) -> dict | None:
        """Get context for a specific repo."""
        return self._context_index.get(repo_name)

    def get_all_contexts(self) -> list[dict]:
        """Get all repo contexts."""
        return list(self._context_index.values())

    def get_relationships(self) -> dict:
        """Get cross-repo relationships."""
        return self._relationships

    def get_semantic_layer(self, repo_name: str) -> dict | None:
        """Get semantic layer for a specific repo."""
        return self._semantic_index.get(repo_name)

    def get_all_semantic_layers(self) -> list[dict]:
        """Get all semantic layers."""
        return list(self._semantic_index.values())

    def get_all_query_recipes(self) -> list[dict]:
        """Get all query recipes across all repos."""
        recipes = []
        for sl in self._semantic_index.values():
            for recipe in sl.get("query_recipes", []):
                recipe_copy = dict(recipe)
                recipe_copy["repo"] = sl.get("repo_name", "")
                recipes.append(recipe_copy)
        return recipes

    def get_business_glossary(self) -> list[dict]:
        """Get combined business glossary across all repos."""
        glossary = []
        for sl in self._semantic_index.values():
            for entry in sl.get("business_glossary", []):
                entry_copy = dict(entry)
                entry_copy["repo"] = sl.get("repo_name", "")
                glossary.append(entry_copy)
        return glossary

    def find_schema(self, name: str) -> list[dict]:
        """Find schemas by name (case-insensitive)."""
        return self._schema_index.get(name.lower(), [])
    
    def find_api(self, path: str) -> list[dict]:
        """Find API endpoints by path."""
        results = []
        for api_path, endpoints in self._api_index.items():
            if path in api_path or api_path in path:
                results.extend(endpoints)
        return results
    
    def find_dependency(self, name: str) -> list[dict]:
        """Find where a dependency is used."""
        return self._dependency_index.get(name.lower(), [])
    
    def find_service(self, name: str) -> list[dict]:
        """Find services by name."""
        results = []
        name_lower = name.lower()
        for service_name, services in self._service_index.items():
            if name_lower in service_name:
                results.extend(services)
        return results
    
    def get_all_schemas(self) -> list[dict]:
        """Get all discovered schemas."""
        return [
            schema
            for schemas in self._schema_index.values()
            for schema in schemas
        ]
    
    def get_all_apis(self) -> list[dict]:
        """Get all discovered API endpoints."""
        return [
            api
            for apis in self._api_index.values()
            for api in apis
        ]
    
    def get_all_dependencies(self) -> list[dict]:
        """Get all discovered dependencies."""
        return [
            dep
            for deps in self._dependency_index.values()
            for dep in deps
        ]
    
    def get_all_services(self) -> list[dict]:
        """Get all discovered services."""
        return [
            service
            for services in self._service_index.values()
            for service in services
        ]
    
    def get_summary(self) -> dict:
        """Get a summary of the knowledge base."""
        return {
            "repositories_analyzed": len(self.results),
            "total_schemas": sum(len(s) for s in self._schema_index.values()),
            "total_apis": sum(len(a) for a in self._api_index.values()),
            "total_dependencies": sum(len(d) for d in self._dependency_index.values()),
            "total_services": sum(len(s) for s in self._service_index.values()),
            "unique_schemas": len(self._schema_index),
            "unique_dependencies": len(self._dependency_index),
            "total_contexts": len(self._context_index),
            "total_semantic_layers": len(self._semantic_index),
            "total_query_recipes": sum(len(sl.get("query_recipes", [])) for sl in self._semantic_index.values()),
            "total_glossary_terms": sum(len(sl.get("business_glossary", [])) for sl in self._semantic_index.values()),
            "generated_at": datetime.utcnow().isoformat(),
        }
    
    def save(self, path: Path | str | None = None) -> None:
        """Save knowledge base to disk."""
        path = Path(path) if path else self.output_dir / "knowledge_base.json"
        
        data = {
            "summary": self.get_summary(),
            "schemas": self.get_all_schemas(),
            "apis": self.get_all_apis(),
            "dependencies": self.get_all_dependencies(),
            "services": self.get_all_services(),
            "contexts": self.get_all_contexts(),
            "relationships": self._relationships,
            "semantic_layers": self.get_all_semantic_layers(),
        }
        
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str))
    
    @classmethod
    def load(cls, path: Path | str) -> "KnowledgeBase":
        """Load knowledge base from disk."""
        path = Path(path)
        data = json.loads(path.read_text())
        
        kb = cls(output_dir=path.parent)
        kb._schema_index = {
            schema["name"].lower(): [schema]
            for schema in data.get("schemas", [])
        }
        kb._api_index = {
            api["path"]: [api]
            for api in data.get("apis", [])
        }
        kb._dependency_index = {
            dep["name"].lower(): [dep]
            for dep in data.get("dependencies", [])
        }
        kb._service_index = {
            service["name"].lower(): [service]
            for service in data.get("services", [])
        }

        for ctx in data.get("contexts", []):
            repo_name = ctx.get("repo_name", "")
            if repo_name:
                kb._context_index[repo_name] = ctx

        kb._relationships = data.get("relationships", {})

        for sl in data.get("semantic_layers", []):
            repo_name = sl.get("repo_name", "")
            if repo_name:
                kb._semantic_index[repo_name] = sl

        return kb
