"""Query interface for knowledge retrieval."""

from .search import SearchEngine

__all__ = ["SearchEngine"]

# Lazy import for semantic search (optional deps)
def get_semantic_search():
    from .embeddings import SemanticSearch
    return SemanticSearch
