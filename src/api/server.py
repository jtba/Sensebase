"""FastAPI REST API server for ContextPedia."""

import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..query.search import SearchEngine
from ..store.knowledge_base import KnowledgeBase


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


# Global state (initialized on startup)
_search_engine: SearchEngine | None = None
_semantic_search = None
_kb_data: dict | None = None


def create_app(
    kb_path: str = "./output/json/knowledge_base.json",
    chroma_path: str = "./output/vectors/chroma",
    enable_semantic: bool = True,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="ContextPedia API",
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
                # Touch collection to verify it exists
                _ = _semantic_search.collection.count()
            except Exception as e:
                print(f"Warning: Semantic search unavailable: {e}")
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
        return StatsResponse(**summary)
    
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
        """
        if not _semantic_search:
            raise HTTPException(
                status_code=503,
                detail="Semantic search not available"
            )
        
        result = _semantic_search.ask(request.question, limit=request.limit)
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
    
    return app


def main():
    """Run the API server."""
    import argparse
    import uvicorn
    
    parser = argparse.ArgumentParser(description="ContextPedia REST API server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Port to bind")
    parser.add_argument("--kb", default="./output/json/knowledge_base.json", help="Knowledge base path")
    parser.add_argument("--chroma", default="./output/vectors/chroma", help="ChromaDB path")
    parser.add_argument("--no-semantic", action="store_true", help="Disable semantic search")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser.parse_args()
    
    app = create_app(
        kb_path=args.kb,
        chroma_path=args.chroma,
        enable_semantic=not args.no_semantic,
    )
    
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
