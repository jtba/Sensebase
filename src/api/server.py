"""FastAPI REST API server for SenseBase."""

import asyncio
import json
import logging
import os
from collections import Counter
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..query.search import SearchEngine
from ..store.knowledge_base import KnowledgeBase
from .crawl_manager import CrawlManager

logger = logging.getLogger(__name__)


# Request/Response Models
class SearchRequest(BaseModel):
    """Search request body."""
    query: str = Field(..., description="Search query")
    limit: int = Field(20, ge=1, le=100, description="Maximum results")
    type_filter: str | None = Field(None, description="Filter by type: schema, api, service, dependency")
    repo_filter: str | None = Field(None, description="Filter by repository name")


class SearchResult(BaseModel):
    """Individual search result."""
    type: str
    name: str
    score: float
    repo: str | None = None
    source_file: str | None = None
    data: dict = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Search response."""
    query: str
    count: int
    results: list[SearchResult]


class SemanticSearchRequest(BaseModel):
    """Semantic search request."""
    query: str = Field(..., description="Natural language query")
    limit: int = Field(10, ge=1, le=50, description="Maximum results")
    type_filter: str | None = None
    repo_filter: str | None = None


class SemanticResult(BaseModel):
    """Semantic search result."""
    id: str
    score: float
    text: str
    metadata: dict


class SemanticSearchResponse(BaseModel):
    """Semantic search response."""
    query: str
    count: int
    results: list[SemanticResult]


class AskRequest(BaseModel):
    """Question-answering request."""
    question: str = Field(..., description="Natural language question")
    limit: int = Field(5, ge=1, le=20, description="Number of context chunks")


class AskResponse(BaseModel):
    """Question-answering response with RAG context."""
    question: str
    context: str
    sources: list[dict]
    result_count: int


class SchemaDetail(BaseModel):
    """Detailed schema information."""
    name: str
    type: str
    source_file: str
    repo: str | None = None
    fields: list[dict] = Field(default_factory=list)
    relationships: list[dict] = Field(default_factory=list)
    description: str | None = None
    business_context: str | None = None
    query_recipes: list[dict] = Field(default_factory=list)


class ServiceDetail(BaseModel):
    """Detailed service information."""
    name: str
    type: str
    source_file: str
    repo: str | None = None
    description: str | None = None
    methods: list[dict] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)


class APIEndpoint(BaseModel):
    """API endpoint information."""
    path: str
    method: str
    source_file: str
    repo: str | None = None
    handler: str | None = None
    description: str | None = None
    params: list[dict] = Field(default_factory=list)


class StatsResponse(BaseModel):
    """Knowledge base statistics."""
    repositories_analyzed: int
    total_schemas: int
    total_apis: int
    total_services: int
    total_dependencies: int
    unique_schemas: int
    unique_dependencies: int
    total_contexts: int = 0
    total_semantic_layers: int = 0
    total_query_recipes: int = 0
    total_glossary_terms: int = 0
    # Short aliases used by the webapp dashboard
    repos: int = 0
    schemas: int = 0
    apis: int = 0
    services: int = 0
    dependencies: int = 0


# Global state (initialized on startup)
_search_engine: SearchEngine | None = None
_semantic_search = None
_kb_data: dict | None = None


def create_app(
    kb_path: str = "./output/json/knowledge_base.json",
    chroma_path: str = "./output/vectors/chroma",
    enable_semantic: bool = True,
    config_path: str = "config/config.yaml",
) -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="SenseBase API",
        description="Knowledge extraction and search API for GitLab repositories",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.on_event("startup")
    async def startup():
        """Initialize search engines on startup."""
        global _search_engine, _semantic_search, _kb_data
        
        # Load keyword search
        _search_engine = SearchEngine(kb_path)
        _kb_data = _search_engine.data
        
        # Load semantic search if enabled
        if enable_semantic:
            try:
                from ..query.embeddings import SemanticSearch
                _semantic_search = SemanticSearch(persist_dir=chroma_path)
                count = _semantic_search.collection.count()

                # Auto-index if ChromaDB is empty but chunks.json exists
                if count == 0:
                    chunks_path = Path(chroma_path).parent / "chunks.json"
                    if chunks_path.exists():
                        logger.info("ChromaDB empty, auto-indexing from %s...", chunks_path)
                        indexed = _semantic_search.index_chunks(chunks_path)
                        logger.info("Indexed %d chunks into ChromaDB", indexed)
            except Exception as e:
                logger.warning("Semantic search unavailable: %s", e)
                _semantic_search = None
    
    # Health check
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "keyword_search": _search_engine is not None,
            "semantic_search": _semantic_search is not None,
        }
    
    # Statistics
    @app.get("/stats", response_model=StatsResponse)
    async def get_stats():
        """Get knowledge base statistics."""
        if not _kb_data:
            raise HTTPException(status_code=503, detail="Knowledge base not loaded")

        summary = _kb_data.get("summary", {})
        return StatsResponse(
            **summary,
            repos=summary.get("repositories_analyzed", 0),
            schemas=summary.get("total_schemas", 0),
            apis=summary.get("total_apis", 0),
            services=summary.get("total_services", 0),
            dependencies=summary.get("total_dependencies", 0),
        )
    
    # Keyword Search
    @app.post("/search", response_model=SearchResponse)
    async def search(request: SearchRequest):
        """
        Keyword search across the knowledge base.
        Searches schemas, APIs, services, and dependencies.
        """
        if not _search_engine:
            raise HTTPException(status_code=503, detail="Search engine not loaded")
        
        results = _search_engine.search(request.query, limit=request.limit)
        
        # Apply filters
        if request.type_filter:
            results = [r for r in results if r.get("type") == request.type_filter]
        if request.repo_filter:
            results = [
                r for r in results 
                if request.repo_filter.lower() in r.get("data", {}).get("repo", "").lower()
            ]
        
        formatted = []
        for r in results:
            data = r.get("data", {})
            formatted.append(SearchResult(
                type=r.get("type", "unknown"),
                name=r.get("name", "unknown"),
                score=r.get("score", 0),
                repo=data.get("repo"),
                source_file=data.get("source_file"),
                data=data,
            ))
        
        return SearchResponse(
            query=request.query,
            count=len(formatted),
            results=formatted,
        )
    
    @app.get("/search")
    async def search_get(
        q: Annotated[str, Query(description="Search query")],
        limit: int = 20,
        type: str | None = None,
        repo: str | None = None,
    ):
        """Keyword search (GET method for convenience)."""
        return await search(SearchRequest(
            query=q,
            limit=limit,
            type_filter=type,
            repo_filter=repo,
        ))
    
    # Semantic Search
    @app.post("/semantic/search", response_model=SemanticSearchResponse)
    async def semantic_search(request: SemanticSearchRequest):
        """
        Semantic search using embeddings.
        Finds conceptually similar content using natural language.
        """
        if not _semantic_search:
            raise HTTPException(
                status_code=503, 
                detail="Semantic search not available. Run indexing first."
            )
        
        results = _semantic_search.search(
            request.query,
            limit=request.limit,
            type_filter=request.type_filter,
            repo_filter=request.repo_filter,
        )
        
        formatted = [SemanticResult(**r) for r in results]
        
        return SemanticSearchResponse(
            query=request.query,
            count=len(formatted),
            results=formatted,
        )
    
    @app.get("/semantic/search")
    async def semantic_search_get(
        q: Annotated[str, Query(description="Natural language query")],
        limit: int = 10,
        type: str | None = None,
        repo: str | None = None,
    ):
        """Semantic search (GET method)."""
        return await semantic_search(SemanticSearchRequest(
            query=q,
            limit=limit,
            type_filter=type,
            repo_filter=repo,
        ))
    
    # Question Answering (RAG context)
    @app.post("/ask", response_model=AskResponse)
    async def ask_question(request: AskRequest):
        """
        Question-answering endpoint.
        Returns relevant context for RAG pipelines.
        Prepends matching query recipes from the semantic business layer.
        """
        if not _semantic_search:
            raise HTTPException(
                status_code=503,
                detail="Semantic search not available"
            )

        result = _semantic_search.ask(request.question, limit=request.limit)

        # Search query recipes for matching questions
        if _kb_data:
            q_lower = request.question.lower()
            q_terms = q_lower.split()
            matching_recipes = []
            for sl in _kb_data.get("semantic_layers", []):
                for recipe in sl.get("query_recipes", []):
                    recipe_q = recipe.get("question", "").lower()
                    if any(term in recipe_q for term in q_terms if len(term) > 3):
                        matching_recipes.append(recipe)

            if matching_recipes:
                recipe_context = "QUERY RECIPES (step-by-step instructions to answer similar questions):\n"
                for r in matching_recipes[:3]:
                    recipe_context += f"\nQ: {r.get('question', '')}\n"
                    for step in r.get("steps", []):
                        recipe_context += f"  - {step.get('action', '')} ({step.get('purpose', '')})\n"
                    recipe_context += f"  Answer format: {r.get('answer_format', '')}\n"
                result["context"] = recipe_context + "\n---\n\n" + result.get("context", "")

        return AskResponse(**result)
    
    @app.get("/ask")
    async def ask_get(
        q: Annotated[str, Query(description="Question")],
        limit: int = 5,
    ):
        """Ask a question (GET method)."""
        return await ask_question(AskRequest(question=q, limit=limit))
    
    # Schema endpoints
    @app.get("/schemas", response_model=list[SchemaDetail])
    async def list_schemas(
        name: str | None = None,
        type: str | None = None,
        repo: str | None = None,
        limit: int = 100,
    ):
        """List all schemas with optional filters."""
        if not _kb_data:
            raise HTTPException(status_code=503, detail="Knowledge base not loaded")
        
        schemas = _kb_data.get("schemas", [])
        
        if name:
            schemas = [s for s in schemas if name.lower() in s.get("name", "").lower()]
        if type:
            schemas = [s for s in schemas if s.get("type") == type]
        if repo:
            schemas = [s for s in schemas if repo.lower() in s.get("repo", "").lower()]
        
        return [SchemaDetail(**s) for s in schemas[:limit]]
    
    @app.get("/schemas/{name}", response_model=list[SchemaDetail])
    async def get_schema(name: str):
        """Get schema by name (may return multiple if same name in different repos)."""
        if not _search_engine:
            raise HTTPException(status_code=503, detail="Search engine not loaded")
        
        results = _search_engine.find_schema(name)
        if not results:
            raise HTTPException(status_code=404, detail=f"Schema '{name}' not found")
        
        return [SchemaDetail(**s) for s in results]
    
    @app.get("/schemas/{name}/relationships")
    async def get_schema_relationships(name: str):
        """Get all relationships for a schema."""
        if not _search_engine:
            raise HTTPException(status_code=503, detail="Search engine not loaded")
        
        relationships = _search_engine.get_schema_relationships(name)
        if not relationships["references_to"] and not relationships["referenced_by"]:
            raise HTTPException(status_code=404, detail=f"Schema '{name}' not found")
        
        return relationships
    
    # Service endpoints
    @app.get("/services", response_model=list[ServiceDetail])
    async def list_services(
        name: str | None = None,
        repo: str | None = None,
        limit: int = 100,
    ):
        """List all services with optional filters."""
        if not _kb_data:
            raise HTTPException(status_code=503, detail="Knowledge base not loaded")
        
        services = _kb_data.get("services", [])
        
        if name:
            services = [s for s in services if name.lower() in s.get("name", "").lower()]
        if repo:
            services = [s for s in services if repo.lower() in s.get("repo", "").lower()]
        
        return [ServiceDetail(**s) for s in services[:limit]]
    
    @app.get("/services/{name}", response_model=list[ServiceDetail])
    async def get_service(name: str):
        """Get service by name."""
        if not _search_engine:
            raise HTTPException(status_code=503, detail="Search engine not loaded")
        
        results = _search_engine.find_service(name)
        if not results:
            raise HTTPException(status_code=404, detail=f"Service '{name}' not found")
        
        return [ServiceDetail(**s) for s in results]
    
    @app.get("/services/{name}/dependencies")
    async def get_service_dependencies(name: str):
        """Get dependency graph for a service."""
        if not _search_engine:
            raise HTTPException(status_code=503, detail="Search engine not loaded")
        
        graph = _search_engine.get_service_dependencies(name)
        if not graph["depends_on"] and not graph["depended_by"]:
            raise HTTPException(status_code=404, detail=f"Service '{name}' not found")
        
        return graph
    
    # API endpoints
    @app.get("/apis", response_model=list[APIEndpoint])
    async def list_apis(
        path: str | None = None,
        method: str | None = None,
        repo: str | None = None,
        limit: int = 100,
    ):
        """List all API endpoints with optional filters."""
        if not _kb_data:
            raise HTTPException(status_code=503, detail="Knowledge base not loaded")
        
        apis = _kb_data.get("apis", [])
        
        if path:
            apis = [a for a in apis if path.lower() in a.get("path", "").lower()]
        if method:
            apis = [a for a in apis if a.get("method", "").upper() == method.upper()]
        if repo:
            apis = [a for a in apis if repo.lower() in a.get("repo", "").lower()]
        
        return [APIEndpoint(**a) for a in apis[:limit]]
    
    # Dependencies endpoints
    @app.get("/dependencies")
    async def list_dependencies(
        name: str | None = None,
        ecosystem: str | None = None,
        limit: int = 100,
    ):
        """List all dependencies with optional filters."""
        if not _kb_data:
            raise HTTPException(status_code=503, detail="Knowledge base not loaded")
        
        deps = _kb_data.get("dependencies", [])
        
        if name:
            deps = [d for d in deps if name.lower() in d.get("name", "").lower()]
        if ecosystem:
            deps = [d for d in deps if d.get("ecosystem") == ecosystem]
        
        # Deduplicate by name
        seen = set()
        unique_deps = []
        for d in deps:
            key = d.get("name", "")
            if key not in seen:
                seen.add(key)
                unique_deps.append(d)
        
        return unique_deps[:limit]
    
    @app.get("/dependencies/{name}/usage")
    async def get_dependency_usage(name: str):
        """Find where a dependency is used across repos."""
        if not _search_engine:
            raise HTTPException(status_code=503, detail="Search engine not loaded")
        
        results = _search_engine.find_dependency_usage(name)
        if not results:
            raise HTTPException(status_code=404, detail=f"Dependency '{name}' not found")
        
        return {
            "name": name,
            "usage_count": len(results),
            "usages": results,
        }
    
    # Semantic index management
    @app.post("/semantic/index")
    async def index_chunks(chunks_path: str = "./output/vectors/chunks.json"):
        """Index chunks for semantic search."""
        if not _semantic_search:
            raise HTTPException(
                status_code=503,
                detail="Semantic search not configured"
            )
        
        count = _semantic_search.index_chunks(chunks_path)
        return {"indexed": count}
    
    @app.get("/semantic/stats")
    async def get_semantic_stats():
        """Get semantic search index statistics."""
        if not _semantic_search:
            raise HTTPException(
                status_code=503,
                detail="Semantic search not available"
            )
        
        return _semantic_search.get_stats()

    # Knowledge Graph
    @app.get("/graph/data")
    async def get_graph_data() -> dict[str, Any]:
        """
        Returns nodes and edges for the knowledge graph visualization.
        Builds a graph from schemas, services, APIs, dependencies, and data flows.
        """
        if not _kb_data:
            raise HTTPException(status_code=503, detail="Knowledge base not loaded")

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        node_ids: set[str] = set()

        # Helper to add a node only once
        def add_node(
            node_id: str,
            label: str,
            node_type: str,
            repo: str | None = None,
            metadata: dict[str, Any] | None = None,
        ) -> None:
            if node_id not in node_ids:
                node_ids.add(node_id)
                node: dict[str, Any] = {
                    "id": node_id,
                    "label": label,
                    "type": node_type,
                }
                if repo is not None:
                    node["repo"] = repo
                node["metadata"] = metadata or {}
                nodes.append(node)

        # --- Schema nodes ---
        for schema in _kb_data.get("schemas", []):
            name = schema.get("name", "unknown")
            repo = schema.get("repo", "")
            node_id = f"schema:{name}"
            add_node(
                node_id,
                label=name,
                node_type="schema",
                repo=repo,
                metadata={
                    "type": schema.get("type", ""),
                    "source_file": schema.get("source_file", ""),
                    "fields": schema.get("fields", []),
                },
            )

        # --- Service nodes ---
        for service in _kb_data.get("services", []):
            name = service.get("name", "unknown")
            repo = service.get("repo", "")
            node_id = f"service:{name}"
            add_node(
                node_id,
                label=name,
                node_type="service",
                repo=repo,
                metadata={
                    "type": service.get("type", ""),
                    "source_file": service.get("source_file", ""),
                    "description": service.get("description", ""),
                    "methods": service.get("methods", []),
                },
            )

        # --- API nodes ---
        for api in _kb_data.get("apis", []):
            method = api.get("method", "")
            path = api.get("path", "")
            repo = api.get("repo", "")
            label = f"{method} {path}" if method else path
            node_id = f"api:{label}"
            add_node(
                node_id,
                label=label,
                node_type="api",
                repo=repo,
                metadata={
                    "handler": api.get("handler", ""),
                    "source_file": api.get("source_file", ""),
                    "description": api.get("description", ""),
                    "params": api.get("params", []),
                },
            )

        # --- Dependency nodes (top 50 most used) ---
        dep_counter: Counter[str] = Counter()
        dep_records: dict[str, dict[str, Any]] = {}
        for dep in _kb_data.get("dependencies", []):
            name = dep.get("name", "")
            if name:
                dep_counter[name] += 1
                if name not in dep_records:
                    dep_records[name] = dep

        top_deps = dep_counter.most_common(50)
        for dep_name, count in top_deps:
            dep = dep_records[dep_name]
            node_id = f"dep:{dep_name}"
            add_node(
                node_id,
                label=dep_name,
                node_type="dependency",
                metadata={
                    "ecosystem": dep.get("ecosystem", ""),
                    "version": dep.get("version", ""),
                    "usage_count": count,
                },
            )

        # --- Build service name lookup for matching ---
        service_names: set[str] = set()
        for service in _kb_data.get("services", []):
            service_names.add(service.get("name", ""))

        # --- Edges: service -> dependency service (depends_on) ---
        for service in _kb_data.get("services", []):
            src_name = service.get("name", "")
            src_id = f"service:{src_name}"
            for dep_name in service.get("dependencies", []):
                # Check if the dependency matches a known service
                target_id = f"service:{dep_name}"
                if f"service:{dep_name}" in node_ids:
                    edges.append({
                        "source": src_id,
                        "target": target_id,
                        "type": "depends_on",
                        "label": "depends on",
                    })

        # --- Edges: service -> schema (data_access) ---
        for service in _kb_data.get("services", []):
            src_name = service.get("name", "")
            src_id = f"service:{src_name}"
            for accessed in service.get("data_accessed", []):
                accessed_name = accessed if isinstance(accessed, str) else accessed.get("name", "")
                target_id = f"schema:{accessed_name}"
                if target_id in node_ids:
                    edges.append({
                        "source": src_id,
                        "target": target_id,
                        "type": "data_access",
                        "label": "reads",
                    })

        # --- Edges: schema -> schema (relationship) ---
        for schema in _kb_data.get("schemas", []):
            src_name = schema.get("name", "")
            src_id = f"schema:{src_name}"
            for rel in schema.get("relationships", []):
                target_name = rel.get("target", "") if isinstance(rel, dict) else str(rel)
                target_id = f"schema:{target_name}"
                rel_label = rel.get("type", "related") if isinstance(rel, dict) else "related"
                if target_id in node_ids:
                    edges.append({
                        "source": src_id,
                        "target": target_id,
                        "type": "relationship",
                        "label": rel_label,
                    })

        # --- Edges: API -> service (handler) ---
        for api in _kb_data.get("apis", []):
            handler = api.get("handler", "")
            if not handler:
                continue
            method = api.get("method", "")
            path = api.get("path", "")
            label = f"{method} {path}" if method else path
            src_id = f"api:{label}"

            # Try to match handler to a service name
            matched_service: str | None = None
            for svc_name in service_names:
                if svc_name and (
                    svc_name.lower() in handler.lower()
                    or handler.lower() in svc_name.lower()
                ):
                    matched_service = svc_name
                    break

            if matched_service:
                edges.append({
                    "source": src_id,
                    "target": f"service:{matched_service}",
                    "type": "handler",
                    "label": "handled by",
                })

        # --- Edges: data flows ---
        for flow in _kb_data.get("data_flows", []):
            source_name = flow.get("source", "")
            target_name = flow.get("target", "")
            if source_name and target_name:
                # Try to resolve to existing node ids
                source_id = (
                    f"service:{source_name}"
                    if f"service:{source_name}" in node_ids
                    else source_name
                )
                target_id = (
                    f"service:{target_name}"
                    if f"service:{target_name}" in node_ids
                    else target_name
                )
                edges.append({
                    "source": source_id,
                    "target": target_id,
                    "type": "data_flow",
                    "label": flow.get("description", "data flow"),
                })

        # --- Stats ---
        node_type_counts: dict[str, int] = {}
        for node in nodes:
            t = node["type"]
            node_type_counts[t] = node_type_counts.get(t, 0) + 1

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "node_types": node_type_counts,
            },
        }

    # Data Flows
    @app.get("/data-flows")
    async def get_data_flows() -> dict[str, Any]:
        """Returns all data flow information from the knowledge base."""
        if not _kb_data:
            raise HTTPException(status_code=503, detail="Knowledge base not loaded")

        flows: list[dict[str, Any]] = []

        # Primary source: top-level data_flows key
        for flow in _kb_data.get("data_flows", []):
            flows.append({
                "source": flow.get("source", ""),
                "target": flow.get("target", ""),
                "type": flow.get("type", ""),
                "description": flow.get("description", ""),
                "source_file": flow.get("source_file", ""),
                "repo": flow.get("repo", ""),
            })

        # Secondary: scan services for data flow patterns if no top-level flows
        if not flows:
            for service in _kb_data.get("services", []):
                svc_name = service.get("name", "")
                repo = service.get("repo", "")
                source_file = service.get("source_file", "")
                for dep_name in service.get("dependencies", []):
                    flows.append({
                        "source": svc_name,
                        "target": dep_name,
                        "type": "dependency",
                        "description": f"{svc_name} depends on {dep_name}",
                        "source_file": source_file,
                        "repo": repo,
                    })

        return {
            "flows": flows,
            "count": len(flows),
        }

    # Repositories
    @app.get("/repos")
    async def list_repos() -> dict[str, Any]:
        """Returns list of repositories with per-repo stats."""
        if not _kb_data:
            raise HTTPException(status_code=503, detail="Knowledge base not loaded")

        repo_stats: dict[str, dict[str, Any]] = {}

        def ensure_repo(name: str) -> dict[str, Any]:
            if name not in repo_stats:
                repo_stats[name] = {
                    "name": name,
                    "schemas": 0,
                    "apis": 0,
                    "services": 0,
                    "dependencies": 0,
                    "languages": {},
                    "has_context": False,
                    "purpose": "",
                }
            return repo_stats[name]

        # Count schemas per repo
        for schema in _kb_data.get("schemas", []):
            repo = schema.get("repo", "unknown")
            ensure_repo(repo)["schemas"] += 1

        # Count APIs per repo
        for api in _kb_data.get("apis", []):
            repo = api.get("repo", "unknown")
            ensure_repo(repo)["apis"] += 1

        # Count services per repo
        for service in _kb_data.get("services", []):
            repo = service.get("repo", "unknown")
            ensure_repo(repo)["services"] += 1

        # Count dependencies per repo and track languages
        for dep in _kb_data.get("dependencies", []):
            repo = dep.get("repo", "unknown")
            stats = ensure_repo(repo)
            stats["dependencies"] += 1
            ecosystem = dep.get("ecosystem", "")
            if ecosystem:
                stats["languages"][ecosystem] = stats["languages"].get(ecosystem, 0) + 1

        # Also gather language info from the summary or per-repo metadata if available
        for repo_info in _kb_data.get("repositories", []):
            name = repo_info.get("name", "")
            if name:
                stats = ensure_repo(name)
                languages = repo_info.get("languages", {})
                if languages:
                    stats["languages"] = languages

        # Add context info to repos
        for ctx in _kb_data.get("contexts", []):
            repo_name = ctx.get("repo_name", "")
            if repo_name:
                stats = ensure_repo(repo_name)
                stats["has_context"] = True
                stats["purpose"] = ctx.get("purpose", "")

        repos_list = sorted(repo_stats.values(), key=lambda r: r["name"])

        return {
            "repos": repos_list,
            "count": len(repos_list),
        }

    # Context endpoints
    @app.get("/contexts")
    async def list_contexts():
        """List all repo contexts with purpose/domain summaries."""
        if not _kb_data:
            raise HTTPException(status_code=503, detail="Knowledge base not loaded")

        contexts = _kb_data.get("contexts", [])
        return {
            "contexts": [
                {
                    "repo_name": c.get("repo_name", ""),
                    "purpose": c.get("purpose", ""),
                    "domain": c.get("domain", ""),
                    "when_to_use": c.get("when_to_use", []),
                    "file_count": c.get("file_count", 0),
                    "generated_at": c.get("generated_at", ""),
                }
                for c in contexts
            ],
            "count": len(contexts),
        }

    @app.get("/repos/{name}/context")
    async def get_repo_context(name: str):
        """Get full context data for a specific repo."""
        if not _kb_data:
            raise HTTPException(status_code=503, detail="Knowledge base not loaded")

        contexts = _kb_data.get("contexts", [])
        for ctx in contexts:
            if ctx.get("repo_name", "").lower() == name.lower():
                return ctx

        raise HTTPException(status_code=404, detail=f"Context for repo '{name}' not found")

    @app.get("/relationships")
    async def get_relationships():
        """Get cross-repo relationship map."""
        if not _kb_data:
            raise HTTPException(status_code=503, detail="Knowledge base not loaded")

        return _kb_data.get("relationships", {})

    # ---- Semantic Business Layer Endpoints ----

    @app.get("/semantic/glossary")
    async def get_business_glossary():
        """Business glossary: all entity definitions across repos."""
        if not _kb_data:
            raise HTTPException(status_code=503, detail="Knowledge base not loaded")
        combined = []
        for sl in _kb_data.get("semantic_layers", []):
            for entry in sl.get("business_glossary", []):
                entry_copy = dict(entry)
                entry_copy["repo"] = sl.get("repo_name", "")
                combined.append(entry_copy)
        return {"glossary": combined, "count": len(combined)}

    @app.get("/semantic/recipes")
    async def get_query_recipes(
        q: str | None = None,
        repo: str | None = None,
        limit: int = 50,
    ):
        """Query recipes: how to answer business questions using the system."""
        if not _kb_data:
            raise HTTPException(status_code=503, detail="Knowledge base not loaded")
        recipes = []
        for sl in _kb_data.get("semantic_layers", []):
            for recipe in sl.get("query_recipes", []):
                recipe_copy = dict(recipe)
                recipe_copy["repo"] = sl.get("repo_name", "")
                recipes.append(recipe_copy)
        if repo:
            recipes = [r for r in recipes if repo.lower() in r.get("repo", "").lower()]
        if q:
            q_lower = q.lower()
            recipes = [r for r in recipes if q_lower in r.get("question", "").lower()]
        return {"recipes": recipes[:limit], "count": len(recipes)}

    @app.get("/repos/{name}/semantic")
    async def get_repo_semantic(name: str):
        """Get semantic business layer for a specific repo."""
        if not _kb_data:
            raise HTTPException(status_code=503, detail="Knowledge base not loaded")
        for sl in _kb_data.get("semantic_layers", []):
            if sl.get("repo_name", "").lower() == name.lower():
                return sl
        raise HTTPException(status_code=404, detail=f"Semantic layer for '{name}' not found")

    # ---- Config Helpers ----

    def _read_config() -> dict:
        """Read the current config from disk."""
        import yaml
        config_file = Path(config_path)
        if not config_file.exists():
            return {}
        return yaml.safe_load(config_file.read_text()) or {}

    def _write_config(config: dict) -> None:
        """Write the config back to disk."""
        import yaml
        config_file = Path(config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))

    # ---- Sources Config Endpoints ----

    class SourceItem(BaseModel):
        type: str = Field(..., description="Source type: github, gitlab, or local")
        # GitHub fields
        token: str | None = Field(None, description="API token")
        orgs: list[str] | None = Field(None, description="GitHub orgs to crawl")
        # GitLab fields
        url: str | None = Field(None, description="GitLab instance URL")
        namespaces: list[str] | None = Field(None, description="GitLab namespaces to crawl")
        # Local fields
        dirs: list[str] | None = Field(None, description="Local directory paths")
        # Shared
        exclude_patterns: list[str] | None = Field(None, description="Regex patterns to exclude")

    class SourcesResponse(BaseModel):
        sources: list[SourceItem] = Field(default_factory=list)

    class AddSourceRequest(BaseModel):
        source: SourceItem

    class RemoveSourceRequest(BaseModel):
        type: str = Field(..., description="Source type to remove: github, gitlab, or local")

    def _source_from_config(cfg: dict, source_type: str) -> SourceItem | None:
        """Extract a SourceItem from a config dict for a given type."""
        if source_type == "github" and "github" in cfg:
            gh = cfg["github"]
            orgs = gh.get("orgs") or []
            if isinstance(orgs, str):
                orgs = [orgs] if orgs else []
            return SourceItem(
                type="github",
                token=gh.get("token", ""),
                orgs=[o for o in orgs if o] or None,
                exclude_patterns=gh.get("exclude_patterns"),
            )
        elif source_type == "gitlab" and "gitlab" in cfg:
            gl = cfg["gitlab"]
            ns = gl.get("namespaces") or []
            if isinstance(ns, str):
                ns = [ns] if ns else []
            return SourceItem(
                type="gitlab",
                url=gl.get("url", ""),
                token=gl.get("token", ""),
                namespaces=[n for n in ns if n] or None,
                exclude_patterns=gl.get("exclude_patterns"),
            )
        elif source_type == "local" and "local" in cfg:
            lc = cfg["local"]
            raw = lc.get("repos_path", [])
            if isinstance(raw, str):
                dirs = [raw] if raw and raw != "/path/to/your/repos" else []
            else:
                dirs = [d for d in (raw or []) if d and d != "/path/to/your/repos"]
            if not dirs:
                return None
            return SourceItem(
                type="local",
                dirs=dirs,
                exclude_patterns=lc.get("exclude_patterns"),
            )
        return None

    @app.get("/config/sources", response_model=SourcesResponse)
    async def get_sources():
        """Get all configured repository sources."""
        cfg = _read_config()
        sources = []
        for t in ("github", "gitlab", "local"):
            src = _source_from_config(cfg, t)
            if src:
                sources.append(src)
        return SourcesResponse(sources=sources)

    @app.post("/config/sources", response_model=SourcesResponse)
    async def add_source(request: AddSourceRequest):
        """Add or update a repository source."""
        cfg = _read_config()
        src = request.source

        if src.type == "github":
            gh = cfg.get("github", {})
            if src.token:
                gh["token"] = src.token
            if src.orgs is not None:
                gh["orgs"] = src.orgs if src.orgs else None
            gh.setdefault("exclude_patterns", ["^archived-.*", ".*-deprecated$", ".*-fork$"])
            gh.setdefault("clone", {"base_path": "./repos", "depth": 1, "concurrency": 5})
            cfg["github"] = gh

        elif src.type == "gitlab":
            gl = cfg.get("gitlab", {})
            if src.url:
                gl["url"] = src.url
            if src.token:
                gl["token"] = src.token
            if src.namespaces is not None:
                gl["namespaces"] = src.namespaces if src.namespaces else None
            gl.setdefault("exclude_patterns", ["^archived-.*", ".*-deprecated$"])
            gl.setdefault("clone", {"base_path": "./repos", "depth": 1, "concurrency": 5})
            cfg["gitlab"] = gl

        elif src.type == "local":
            lc = cfg.get("local", {})
            if src.dirs is not None:
                lc["repos_path"] = [d.strip() for d in src.dirs if d.strip()]
            lc.setdefault("exclude_patterns", ["^\\."])
            cfg["local"] = lc

        else:
            raise HTTPException(status_code=400, detail=f"Unknown source type: {src.type}")

        if src.exclude_patterns is not None:
            cfg[src.type]["exclude_patterns"] = src.exclude_patterns

        _write_config(cfg)

        # Return full list
        sources = []
        for t in ("github", "gitlab", "local"):
            s = _source_from_config(cfg, t)
            if s:
                sources.append(s)
        return SourcesResponse(sources=sources)

    @app.delete("/config/sources/{source_type}", response_model=SourcesResponse)
    async def remove_source(source_type: str):
        """Remove a repository source by type."""
        cfg = _read_config()
        if source_type not in ("github", "gitlab", "local"):
            raise HTTPException(status_code=400, detail=f"Unknown source type: {source_type}")
        if source_type not in cfg:
            raise HTTPException(status_code=404, detail=f"Source '{source_type}' not configured")

        del cfg[source_type]
        _write_config(cfg)

        sources = []
        for t in ("github", "gitlab", "local"):
            s = _source_from_config(cfg, t)
            if s:
                sources.append(s)
        return SourcesResponse(sources=sources)

    # ---- LLM Config Endpoints ----

    class LLMConfigResponse(BaseModel):
        provider: str | None = None
        model: str | None = None
        api_key_set: bool = False
        api_key_source: str | None = None

    class LLMConfigUpdate(BaseModel):
        provider: str = Field(..., description="anthropic or openai")
        api_key: str | None = Field(None, description="API key (omit to keep existing)")
        model: str | None = Field(None, description="Model name override")

    def _build_llm_config_response(cfg: dict) -> LLMConfigResponse:
        """Build LLM config response from config dict + env vars."""
        llm = cfg.get("llm", {})
        provider = llm.get("provider")
        model = llm.get("model")

        # Determine API key status and source
        api_key_set = False
        api_key_source = None

        if llm.get("api_key"):
            api_key_set = True
            api_key_source = "config"
        elif os.environ.get("ANTHROPIC_API_KEY"):
            api_key_set = True
            api_key_source = "env"
        elif os.environ.get("OPENAI_API_KEY"):
            api_key_set = True
            api_key_source = "env"
        elif os.environ.get("AWS_ACCESS_KEY_ID"):
            api_key_set = True
            api_key_source = "env"

        return LLMConfigResponse(
            provider=provider,
            model=model,
            api_key_set=api_key_set,
            api_key_source=api_key_source,
        )

    @app.get("/config/llm", response_model=LLMConfigResponse)
    async def get_llm_config():
        """Get current LLM provider configuration."""
        cfg = _read_config()
        return _build_llm_config_response(cfg)

    @app.put("/config/llm", response_model=LLMConfigResponse)
    async def update_llm_config(request: LLMConfigUpdate):
        """Update LLM provider settings."""
        cfg = _read_config()

        if "llm" not in cfg:
            cfg["llm"] = {}

        cfg["llm"]["provider"] = request.provider

        # Only overwrite key if a non-empty value is provided
        if request.api_key:
            cfg["llm"]["api_key"] = request.api_key

        if request.model:
            cfg["llm"]["model"] = request.model

        _write_config(cfg)
        return _build_llm_config_response(cfg)

    # ---- Backward-compat: local-dirs endpoints ----

    class LocalDirsResponse(BaseModel):
        dirs: list[str] = Field(default_factory=list)
        platform: str = Field("", description="Primary platform configured (github, gitlab, or local)")

    class LocalDirsUpdate(BaseModel):
        dirs: list[str] = Field(..., description="List of local directory paths to scan for repos")

    @app.get("/config/local-dirs", response_model=LocalDirsResponse)
    async def get_local_dirs():
        """Get the currently configured local repository directories."""
        cfg = _read_config()
        local_cfg = cfg.get("local", {})
        raw = local_cfg.get("repos_path", [])
        if isinstance(raw, str):
            dirs = [raw] if raw and raw != "/path/to/your/repos" else []
        else:
            dirs = [d for d in (raw or []) if d and d != "/path/to/your/repos"]

        platform = "local" if "local" in cfg else "github" if "github" in cfg else "gitlab" if "gitlab" in cfg else ""
        return LocalDirsResponse(dirs=dirs, platform=platform)

    @app.put("/config/local-dirs", response_model=LocalDirsResponse)
    async def update_local_dirs(request: LocalDirsUpdate):
        """Update the list of local repository directories in the config."""
        cfg = _read_config()

        if "local" not in cfg:
            cfg["local"] = {}

        dirs = [d.strip() for d in request.dirs if d.strip()]
        cfg["local"]["repos_path"] = dirs

        if "exclude_patterns" not in cfg["local"]:
            cfg["local"]["exclude_patterns"] = ["^\\."]

        _write_config(cfg)

        platform = "local" if "local" in cfg else "github" if "github" in cfg else "gitlab" if "gitlab" in cfg else ""
        return LocalDirsResponse(dirs=dirs, platform=platform)

    # ---- Crawl Pipeline Endpoints ----

    _crawl_manager = CrawlManager(config_path=config_path)

    def _reload_kb():
        """Reload knowledge base from disk after crawl completes."""
        global _search_engine, _semantic_search, _kb_data
        _search_engine = SearchEngine(kb_path)
        _kb_data = _search_engine.data
        if enable_semantic:
            try:
                from ..query.embeddings import SemanticSearch
                _semantic_search = SemanticSearch(persist_dir=chroma_path)
                count = _semantic_search.collection.count()

                # Auto-index if ChromaDB is empty but chunks.json exists
                if count == 0:
                    chunks_path = Path(chroma_path).parent / "chunks.json"
                    if chunks_path.exists():
                        logger.info("ChromaDB empty, auto-indexing from %s...", chunks_path)
                        indexed = _semantic_search.index_chunks(chunks_path)
                        logger.info("Indexed %d chunks into ChromaDB", indexed)
            except Exception as e:
                logger.warning("Semantic search reload failed: %s", e)
                _semantic_search = None

    _crawl_manager.set_on_complete(_reload_kb)

    class CrawlStartRequest(BaseModel):
        use_llm: bool = Field(False, description="Use LLM extraction instead of pattern matching")

    @app.post("/crawl/start")
    async def start_crawl(request: CrawlStartRequest):
        """Start a new crawl pipeline run."""
        result = _crawl_manager.start(use_llm=request.use_llm)
        if result.get("error"):
            raise HTTPException(status_code=409, detail=result["error"])
        return result

    @app.get("/crawl/status")
    async def crawl_status():
        """Get current crawl job status."""
        return _crawl_manager.get_status()

    @app.get("/crawl/stream")
    async def crawl_stream():
        """SSE stream of crawl progress updates."""
        async def event_generator():
            while True:
                status = _crawl_manager.get_status()
                yield f"data: {json.dumps(status)}\n\n"
                if status["status"] in ("completed", "failed", "idle"):
                    break
                await asyncio.sleep(1)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Webapp static files
    webapp_dir = Path(__file__).parent.parent / "webapp"
    if webapp_dir.exists():
        app.mount("/static", StaticFiles(directory=str(webapp_dir / "static")), name="static")

        @app.get("/app/{rest_of_path:path}")
        @app.get("/app")
        async def serve_webapp(rest_of_path: str = "") -> FileResponse:
            return FileResponse(str(webapp_dir / "index.html"))

        @app.get("/")
        async def root_redirect():
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/app")
    else:
        @app.get("/")
        async def root_redirect():
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/docs")

    return app


def main():
    """Run the API server."""
    import argparse
    import uvicorn
    
    parser = argparse.ArgumentParser(description="SenseBase REST API server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Port to bind")
    parser.add_argument("--kb", default="./output/json/knowledge_base.json", help="Knowledge base path")
    parser.add_argument("--chroma", default="./output/vectors/chroma", help="ChromaDB path")
    parser.add_argument("--no-semantic", action="store_true", help="Disable semantic search")
    parser.add_argument("--config", default="config/config.yaml", help="Config file path")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    args = parser.parse_args()

    app = create_app(
        kb_path=args.kb,
        chroma_path=args.chroma,
        enable_semantic=not args.no_semantic,
        config_path=args.config,
    )
    
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
