"""Central knowledge base that aggregates analysis results."""

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from ..analyzers.base import AnalysisResult
from ..analyzers.ontology import (
    InterfaceProperty,
    InterfaceType,
    LinkTypeInfo,
    make_entity_id,
)
from .graph import GraphEdge, GraphNode, OntologyGraph


class KnowledgeBase:
    """Aggregates and indexes extracted knowledge.

    Uses an ``OntologyGraph`` as the primary store for all entities and
    their relationships, replacing the previous flat dict-of-lists indexes.
    Context and semantic-layer data remain in dedicated dicts because they
    are keyed by repo rather than by entity identity.
    """

    def __init__(self, output_dir: Path | str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.results: list[AnalysisResult] = []

        # Primary graph store
        self.graph = OntologyGraph()

        # Context and semantic data (keyed by repo, not graph-structured)
        self._context_index: dict[str, dict] = {}
        self._semantic_index: dict[str, dict] = {}
        self._relationships: dict = {}

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def add_result(self, result: AnalysisResult) -> None:
        """Add analysis result and index all entities into the graph."""
        self.results.append(result)
        self._index_result(result)

    def _index_result(self, result: AnalysisResult) -> None:
        """Add all entities from *result* to the graph."""
        repo = result.repo_name
        repo_node_id = f"repo:{repo}"
        self.graph.add_node(GraphNode(
            id=repo_node_id, type="repo", repo=repo,
            data={"repo_name": repo, "repo_path": result.repo_path},
        ))

        # --- Schemas ---
        for schema in result.schemas:
            node_id = make_entity_id("schema", schema.name, repo, schema.source_file)
            schema.entity_id = node_id
            self.graph.add_node(GraphNode(
                id=node_id, type="schema", repo=repo,
                data={"repo": repo, "path": result.repo_path, **asdict(schema)},
            ))
            self.graph.add_edge(GraphEdge(
                source_id=repo_node_id, target_id=node_id, type="contains",
            ))

        # Schema relationship edges (links_to) — resolved against known schemas
        for schema in result.schemas:
            source_id = schema.entity_id
            for rel in schema.relationships:
                # Promote to first-class link type
                link = LinkTypeInfo.from_relationship_ref(
                    rel, schema.name, schema.source_file,
                )
                link.entity_id = make_entity_id(
                    "link_type", link.name, repo, schema.source_file,
                )
                result.link_types.append(link)

                self.graph.add_node(GraphNode(
                    id=link.entity_id, type="link_type", repo=repo,
                    data={"repo": repo, **asdict(link)},
                ))

                # source schema -> link_type
                self.graph.add_edge(GraphEdge(
                    source_id=source_id, target_id=link.entity_id,
                    type="links_via",
                ))

                # link_type -> target schema(s)
                for target_node in self.graph.find_by_name(rel.target, "schema"):
                    self.graph.add_edge(GraphEdge(
                        source_id=link.entity_id, target_id=target_node.id,
                        type="links_to",
                    ))
                    # Bidirectional reverse edge
                    if link.bidirectional:
                        self.graph.add_edge(GraphEdge(
                            source_id=target_node.id, target_id=source_id,
                            type="linked_from",
                            properties={"via": link.entity_id},
                        ))

        # --- APIs ---
        for api in result.apis:
            node_id = make_entity_id(
                "api", f"{api.method}_{api.path}", repo, api.source_file,
            )
            api.entity_id = node_id
            self.graph.add_node(GraphNode(
                id=node_id, type="api", repo=repo,
                data={"repo": repo, "path": result.repo_path, **asdict(api)},
            ))
            self.graph.add_edge(GraphEdge(
                source_id=repo_node_id, target_id=node_id, type="contains",
            ))

        # --- Services / business logic ---
        for service in result.business_logic:
            node_id = make_entity_id(
                "service", service.name, repo, service.source_file,
            )
            service.entity_id = node_id
            self.graph.add_node(GraphNode(
                id=node_id, type="service", repo=repo,
                data={"repo": repo, "path": result.repo_path, **asdict(service)},
            ))
            self.graph.add_edge(GraphEdge(
                source_id=repo_node_id, target_id=node_id, type="contains",
            ))

            # service -> schema (accesses)
            for accessed in service.data_accessed:
                for target in self.graph.find_by_name(accessed, "schema"):
                    self.graph.add_edge(GraphEdge(
                        source_id=node_id, target_id=target.id, type="accesses",
                    ))

            # service -> service (depends_on)
            for dep_name in service.dependencies:
                for dep_node in self.graph.find_by_name_substring(dep_name, "service"):
                    if dep_node.id != node_id:
                        self.graph.add_edge(GraphEdge(
                            source_id=node_id, target_id=dep_node.id,
                            type="depends_on",
                        ))

        # --- Dependencies ---
        for dep in result.dependencies:
            node_id = make_entity_id(
                "dependency", dep.name, repo, dep.source_file,
            )
            dep.entity_id = node_id
            self.graph.add_node(GraphNode(
                id=node_id, type="dependency", repo=repo,
                data={"repo": repo, "path": result.repo_path, **asdict(dep)},
            ))
            self.graph.add_edge(GraphEdge(
                source_id=repo_node_id, target_id=node_id, type="contains",
            ))

        # --- Interfaces ---
        for iface in result.interfaces:
            if not iface.entity_id:
                iface.entity_id = make_entity_id("interface", iface.name, repo, "")
            self.graph.add_node(GraphNode(
                id=iface.entity_id, type="interface", repo=repo,
                data={"repo": repo, **asdict(iface)},
            ))
            for impl_name in iface.implemented_by:
                for impl_node in self.graph.find_by_name(impl_name, "schema"):
                    self.graph.add_edge(GraphEdge(
                        source_id=impl_node.id, target_id=iface.entity_id,
                        type="implements",
                    ))

        # --- Context ---
        if result.context:
            self._context_index[repo] = {
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

        # --- Semantic layer ---
        if result.semantic_layer:
            self._semantic_index[repo] = {
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
        self.graph.remove_by_repo(result.repo_name)
        self._index_result(result)

    # ------------------------------------------------------------------
    # Interface inference
    # ------------------------------------------------------------------

    # Well-known field-set patterns for readable interface names
    _KNOWN_PATTERNS: dict[frozenset[str], str] = {
        frozenset({"id", "created_at", "updated_at"}): "Auditable",
        frozenset({"created_at", "updated_at"}): "Timestamped",
        frozenset({"name", "description"}): "Describable",
        frozenset({"latitude", "longitude"}): "Locatable",
        frozenset({"id", "name"}): "Identifiable",
        frozenset({"status", "updated_at"}): "Trackable",
    }

    def compute_interfaces(
        self,
        min_shared_fields: int = 3,
        min_implementors: int = 2,
    ) -> list[InterfaceType]:
        """Infer interfaces from common field patterns across schemas.

        Schemas from *different* repos that share >= ``min_shared_fields``
        fields (same name + type) are grouped under an auto-generated
        ``InterfaceType`` marked ``inferred=True``.
        """
        schemas = self.graph.get_nodes_by_type("schema")
        if len(schemas) < min_implementors:
            return []

        # field (name, type) -> list of (schema_name, repo)
        field_to_schemas: dict[tuple[str, str], list[tuple[str, str]]] = {}
        # schema key -> set of fields
        schema_fields: dict[str, set[tuple[str, str]]] = {}

        for node in schemas:
            sname = node.data.get("name", "")
            repo = node.repo
            sk = f"{repo}:{sname}"
            fields: set[tuple[str, str]] = set()
            for f in node.data.get("fields", []):
                fn = f.get("name", "")
                ft = f.get("type", "")
                if fn and ft:
                    key = (fn, ft)
                    fields.add(key)
                    field_to_schemas.setdefault(key, []).append((sname, repo))
            if fields:
                schema_fields[sk] = fields

        # Filter to fields present in schemas across >= 2 repos
        cross_repo_fields: dict[tuple[str, str], list[tuple[str, str]]] = {}
        for fkey, slist in field_to_schemas.items():
            repos = {r for _, r in slist}
            if len(repos) >= 2 and len(slist) >= min_implementors:
                cross_repo_fields[fkey] = slist

        if not cross_repo_fields:
            return []

        # Per-schema: which cross-repo fields does it have?
        schema_cross: dict[str, set[tuple[str, str]]] = {}
        for fkey, slist in cross_repo_fields.items():
            for sname, repo in slist:
                sk = f"{repo}:{sname}"
                schema_cross.setdefault(sk, set()).add(fkey)

        # Group schemas by their cross-repo field fingerprint
        fp_to_schemas: dict[frozenset[tuple[str, str]], list[str]] = {}
        for sk, fset in schema_cross.items():
            fp = frozenset(fset)
            fp_to_schemas.setdefault(fp, []).append(sk)

        interfaces: list[InterfaceType] = []
        seen: set[frozenset[tuple[str, str]]] = set()

        for fp, skeys in sorted(fp_to_schemas.items(), key=lambda x: -len(x[0])):
            if len(fp) < min_shared_fields:
                continue
            repos = {k.split(":")[0] for k in skeys}
            if len(repos) < 2:
                continue
            if len(skeys) < min_implementors:
                continue
            if any(fp.issubset(s) for s in seen):
                continue
            seen.add(fp)

            implementors = [k.split(":", 1)[1] for k in skeys]
            iname = self._generate_interface_name(fp, implementors)

            iface = InterfaceType(
                name=iname,
                description=f"Shared structure across {', '.join(sorted(set(implementors)))}",
                properties=[
                    InterfaceProperty(name=f[0], type=f[1])
                    for f in sorted(fp)
                ],
                implemented_by=sorted(set(implementors)),
                inferred=True,
                entity_id=make_entity_id("interface", iname, "", ""),
            )
            interfaces.append(iface)

            # Add to graph
            self.graph.add_node(GraphNode(
                id=iface.entity_id, type="interface", repo="",
                data=asdict(iface),
            ))
            for sk in skeys:
                repo, sname = sk.split(":", 1)
                for sn in self.graph.find_by_name(sname, "schema"):
                    if sn.repo == repo:
                        self.graph.add_edge(GraphEdge(
                            source_id=sn.id, target_id=iface.entity_id,
                            type="implements",
                        ))
                        impl_list = sn.data.setdefault("implements", [])
                        if iname not in impl_list:
                            impl_list.append(iname)

        return interfaces

    def _generate_interface_name(
        self,
        field_set: frozenset[tuple[str, str]],
        implementors: list[str],
    ) -> str:
        field_names = {f[0] for f in field_set}
        for pattern, name in self._KNOWN_PATTERNS.items():
            if pattern.issubset(field_names):
                return name
        sorted_fields = sorted(field_names)[:4]
        return "Has" + "".join(
            f.replace("_", " ").title().replace(" ", "") for f in sorted_fields
        )

    # ------------------------------------------------------------------
    # Graph traversal queries
    # ------------------------------------------------------------------

    def get_dependencies_of(
        self, entity_name: str, max_depth: int = 3,
    ) -> list[dict]:
        """What does *entity_name* depend on? (transitive)"""
        nodes = self.graph.find_by_name(entity_name)
        if not nodes:
            return []
        return [
            {"path": path, "node": node.data}
            for path, node in self.graph.traverse(
                nodes[0].id, max_depth=max_depth, direction="outgoing",
                edge_types={"depends_on", "accesses", "links_to", "links_via"},
            )
        ]

    def get_dependents_of(
        self, entity_name: str, max_depth: int = 3,
    ) -> list[dict]:
        """What depends on *entity_name*? (transitive)"""
        nodes = self.graph.find_by_name(entity_name)
        if not nodes:
            return []
        return [
            {"path": path, "node": node.data}
            for path, node in self.graph.traverse(
                nodes[0].id, max_depth=max_depth, direction="incoming",
                edge_types={"depends_on", "accesses", "links_to", "linked_from"},
            )
        ]

    def get_impact_analysis(
        self, entity_name: str, max_depth: int = 3,
    ) -> dict:
        """What would be affected if *entity_name* changes?"""
        dependents = self.get_dependents_of(entity_name, max_depth)
        return {
            "entity": entity_name,
            "affected_count": len(dependents),
            "affected": dependents,
        }

    # ------------------------------------------------------------------
    # Relationship data (cross-repo)
    # ------------------------------------------------------------------

    def set_relationships(self, relationships: dict) -> None:
        """Set cross-repo relationship data."""
        self._relationships = relationships

    def build_relationships_from_contexts(self) -> None:
        """Build relationship data directly from repo contexts.

        Synthesises ``service_map``, ``data_routing``, and
        ``service_chains`` for the webapp, using per-repo context data.
        """
        contexts = self.get_all_contexts()
        if not contexts:
            return

        service_map: list[dict] = []
        data_routing: list[dict] = []
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
            instead_of: list[dict] = []

            service_map.append({
                "service": repo,
                "purpose": purpose,
                "domain": domain,
                "data_owned": data_owned,
                "use_when": use_when,
                "instead_of": instead_of,
            })

            for entity in ctx.get("data_ownership", []):
                name = entity.get("entity", "")
                is_sot = entity.get("is_source_of_truth", False)
                if name and is_sot:
                    also_in: list[dict] = []
                    for other_ctx in contexts:
                        if other_ctx["repo_name"] == repo:
                            continue
                        for other_entity in other_ctx.get("data_ownership", []):
                            if (
                                other_entity.get("entity", "") == name
                                and not other_entity.get("is_source_of_truth")
                            ):
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

        # Service chains from dependency relationships
        service_chains: list[dict] = []
        all_repo_names = set(ctx_by_name.keys())

        dep_graph: dict[str, list[str]] = {}
        for ctx in contexts:
            r = ctx["repo_name"]
            dep_repos: list[str] = []
            for dep in ctx.get("service_dependencies", []) or []:
                dep_svc = dep.get("service", "")
                for rn in all_repo_names:
                    if rn != r and (
                        rn.lower() in dep_svc.lower()
                        or dep_svc.lower() in rn.lower()
                    ):
                        dep_repos.append(rn)
                        break
            if dep_repos:
                dep_graph[r] = dep_repos

        depended_on: set[str] = set()
        for deps in dep_graph.values():
            depended_on.update(deps)
        roots = depended_on - set(dep_graph.keys())
        if not roots:
            roots = set(dep_graph.keys())

        seen_chains: set[str] = set()
        for root in sorted(roots):
            chain_steps: list[dict] = []
            root_ctx = ctx_by_name.get(root, {})
            chain_steps.append({
                "service": root,
                "action": (root_ctx.get("purpose", "") or "Provides data/services")[:120],
                "data_passed": "",
            })
            for r2, deps in dep_graph.items():
                if root in deps:
                    r2_ctx = ctx_by_name.get(r2, {})
                    chain_steps.append({
                        "service": r2,
                        "action": (r2_ctx.get("purpose", "") or "Processes data")[:120],
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

    # ------------------------------------------------------------------
    # Backward-compatible query API (returns list[dict])
    # ------------------------------------------------------------------

    def find_schema(self, name: str) -> list[dict]:
        """Find schemas by name (case-insensitive)."""
        return [n.data for n in self.graph.find_by_name(name, "schema")]

    def find_api(self, path: str) -> list[dict]:
        """Find API endpoints by path (substring match)."""
        results: list[dict] = []
        for node in self.graph.get_nodes_by_type("api"):
            api_path = node.data.get("path", "")
            if path in api_path or api_path in path:
                results.append(node.data)
        return results

    def find_dependency(self, name: str) -> list[dict]:
        """Find where a dependency is used."""
        return [n.data for n in self.graph.find_by_name(name, "dependency")]

    def find_service(self, name: str) -> list[dict]:
        """Find services by name (substring match)."""
        return [n.data for n in self.graph.find_by_name_substring(name, "service")]

    def get_all_schemas(self) -> list[dict]:
        return [n.data for n in self.graph.get_nodes_by_type("schema")]

    def get_all_apis(self) -> list[dict]:
        return [n.data for n in self.graph.get_nodes_by_type("api")]

    def get_all_dependencies(self) -> list[dict]:
        return [n.data for n in self.graph.get_nodes_by_type("dependency")]

    def get_all_services(self) -> list[dict]:
        return [n.data for n in self.graph.get_nodes_by_type("service")]

    def get_all_link_types(self) -> list[dict]:
        return [n.data for n in self.graph.get_nodes_by_type("link_type")]

    def get_all_interfaces(self) -> list[dict]:
        return [n.data for n in self.graph.get_nodes_by_type("interface")]

    # ------------------------------------------------------------------
    # Context & semantic layer (unchanged API)
    # ------------------------------------------------------------------

    def get_context(self, repo_name: str) -> dict | None:
        return self._context_index.get(repo_name)

    def get_all_contexts(self) -> list[dict]:
        return list(self._context_index.values())

    def get_relationships(self) -> dict:
        return self._relationships

    def get_semantic_layer(self, repo_name: str) -> dict | None:
        return self._semantic_index.get(repo_name)

    def get_all_semantic_layers(self) -> list[dict]:
        return list(self._semantic_index.values())

    def get_all_query_recipes(self) -> list[dict]:
        recipes = []
        for sl in self._semantic_index.values():
            for recipe in sl.get("query_recipes", []):
                recipe_copy = dict(recipe)
                recipe_copy["repo"] = sl.get("repo_name", "")
                recipes.append(recipe_copy)
        return recipes

    def get_business_glossary(self) -> list[dict]:
        glossary = []
        for sl in self._semantic_index.values():
            for entry in sl.get("business_glossary", []):
                entry_copy = dict(entry)
                entry_copy["repo"] = sl.get("repo_name", "")
                glossary.append(entry_copy)
        return glossary

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def get_summary(self) -> dict:
        schema_nodes = self.graph.get_nodes_by_type("schema")
        unique_names = {n.data.get("name", "").lower() for n in schema_nodes}
        dep_nodes = self.graph.get_nodes_by_type("dependency")
        unique_deps = {n.data.get("name", "").lower() for n in dep_nodes}

        return {
            "repositories_analyzed": len(self.results) or len(
                self.graph.get_nodes_by_type("repo")
            ),
            "total_schemas": len(schema_nodes),
            "total_apis": len(self.graph.get_nodes_by_type("api")),
            "total_dependencies": len(dep_nodes),
            "total_services": len(self.graph.get_nodes_by_type("service")),
            "total_link_types": len(self.graph.get_nodes_by_type("link_type")),
            "total_interfaces": len(self.graph.get_nodes_by_type("interface")),
            "unique_schemas": len(unique_names),
            "unique_dependencies": len(unique_deps),
            "total_contexts": len(self._context_index),
            "total_semantic_layers": len(self._semantic_index),
            "total_query_recipes": sum(
                len(sl.get("query_recipes", []))
                for sl in self._semantic_index.values()
            ),
            "total_glossary_terms": sum(
                len(sl.get("business_glossary", []))
                for sl in self._semantic_index.values()
            ),
            "graph_nodes": self.graph.node_count,
            "graph_edges": self.graph.edge_count,
            "generated_at": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: Path | str | None = None) -> None:
        """Save knowledge base to disk."""
        path = Path(path) if path else self.output_dir / "knowledge_base.json"

        data = {
            "summary": self.get_summary(),
            "schemas": self.get_all_schemas(),
            "apis": self.get_all_apis(),
            "dependencies": self.get_all_dependencies(),
            "services": self.get_all_services(),
            "link_types": self.get_all_link_types(),
            "interfaces": self.get_all_interfaces(),
            "contexts": self.get_all_contexts(),
            "relationships": self._relationships,
            "semantic_layers": self.get_all_semantic_layers(),
            "graph": self.graph.to_dict(),
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str))

    @classmethod
    def load(cls, path: Path | str) -> "KnowledgeBase":
        """Load knowledge base from disk."""
        path = Path(path)
        data = json.loads(path.read_text())

        kb = cls(output_dir=path.parent)

        # Reconstruct graph
        if "graph" in data:
            kb.graph = OntologyGraph.from_dict(data["graph"])
        else:
            kb._rebuild_graph_from_data(data)

        # Contexts
        for ctx in data.get("contexts", []):
            repo_name = ctx.get("repo_name", "")
            if repo_name:
                kb._context_index[repo_name] = ctx

        kb._relationships = data.get("relationships", {})

        # Semantic layers
        for sl in data.get("semantic_layers", []):
            repo_name = sl.get("repo_name", "")
            if repo_name:
                kb._semantic_index[repo_name] = sl

        return kb

    def _rebuild_graph_from_data(self, data: dict) -> None:
        """Rebuild graph from flat entity lists (backward compat with v1 files)."""
        repos: set[str] = set()

        for entity_type, key in [
            ("schema", "schemas"),
            ("api", "apis"),
            ("dependency", "dependencies"),
            ("service", "services"),
            ("link_type", "link_types"),
            ("interface", "interfaces"),
        ]:
            for item in data.get(key, []):
                repo = item.get("repo", "")
                repos.add(repo)
                name = item.get("name", item.get("path", ""))
                source = item.get("source_file", "")
                node_id = item.get("entity_id") or make_entity_id(
                    entity_type, name, repo, source,
                )
                item["entity_id"] = node_id
                self.graph.add_node(GraphNode(
                    id=node_id, type=entity_type, repo=repo, data=item,
                ))

        # Repo nodes + contains edges
        for repo in repos:
            if not repo:
                continue
            repo_id = f"repo:{repo}"
            self.graph.add_node(GraphNode(
                id=repo_id, type="repo", repo=repo,
                data={"repo_name": repo},
            ))
            for node in self.graph.get_nodes_by_repo(repo):
                if node.type != "repo":
                    self.graph.add_edge(GraphEdge(
                        source_id=repo_id, target_id=node.id, type="contains",
                    ))

        # Relationship edges from schema data
        for node in self.graph.get_nodes_by_type("schema"):
            for rel in node.data.get("relationships", []):
                target_name = rel.get("target", "")
                for target in self.graph.find_by_name(target_name, "schema"):
                    self.graph.add_edge(GraphEdge(
                        source_id=node.id, target_id=target.id,
                        type="links_to", properties=rel,
                    ))
