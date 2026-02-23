"""Semantic search with embeddings."""

import json
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()

# Lazy imports for optional dependencies
_sentence_transformer = None
_chromadb = None


def _get_sentence_transformer():
    """Lazy load sentence-transformers."""
    global _sentence_transformer
    if _sentence_transformer is None:
        try:
            from sentence_transformers import SentenceTransformer
            _sentence_transformer = SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )
    return _sentence_transformer


def _get_chromadb():
    """Lazy load chromadb."""
    global _chromadb
    if _chromadb is None:
        try:
            import chromadb
            _chromadb = chromadb
        except ImportError:
            raise ImportError(
                "chromadb not installed. "
                "Run: pip install chromadb"
            )
    return _chromadb


class SemanticSearch:
    """Semantic search engine using embeddings."""
    
    def __init__(
        self,
        persist_dir: Path | str = "./output/vectors/chroma",
        model_name: str = "all-MiniLM-L6-v2",
    ):
        self.persist_dir = Path(persist_dir)
        self.model_name = model_name
        self._model = None
        self._client = None
        self._collection = None
    
    @property
    def model(self):
        """Lazy load embedding model."""
        if self._model is None:
            SentenceTransformer = _get_sentence_transformer()
            console.print(f"[blue]Loading embedding model: {self.model_name}[/blue]")
            self._model = SentenceTransformer(self.model_name)
        return self._model
    
    @property
    def client(self):
        """Lazy load ChromaDB client."""
        if self._client is None:
            chromadb = _get_chromadb()
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        return self._client
    
    @property
    def collection(self):
        """Get or create the knowledge collection."""
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name="sensebase",
                metadata={"hnsw:space": "cosine"}
            )
        return self._collection
    
    def index_chunks(self, chunks_path: Path | str) -> int:
        """Index chunks from JSON file into vector store."""
        chunks_path = Path(chunks_path)
        
        if not chunks_path.exists():
            console.print(f"[red]Chunks file not found: {chunks_path}[/red]")
            return 0
        
        chunks = json.loads(chunks_path.read_text())
        
        if not chunks:
            console.print("[yellow]No chunks to index[/yellow]")
            return 0
        
        console.print(f"[blue]Indexing {len(chunks)} chunks...[/blue]")
        
        # Prepare data for ChromaDB (deduplicate by ID, last wins)
        seen = {}
        for chunk in chunks:
            chunk_id = chunk.get("id", "")
            text = chunk.get("text", "")
            if not chunk_id or not text:
                continue
            seen[chunk_id] = chunk

        ids = []
        documents = []
        metadatas = []
        for chunk_id, chunk in seen.items():
            ids.append(chunk_id)
            documents.append(chunk["text"])
            metadatas.append({
                "type": chunk.get("type", "unknown"),
                "name": chunk.get("name", ""),
                "repo": chunk.get("repo", ""),
                "path": chunk.get("path", ""),
                "method": chunk.get("method", ""),
            })
        
        # Generate embeddings
        console.print("[blue]Generating embeddings...[/blue]")
        embeddings = self.model.encode(documents, show_progress_bar=True).tolist()
        
        # Upsert to ChromaDB (handles duplicates)
        batch_size = 500
        for i in range(0, len(ids), batch_size):
            end = min(i + batch_size, len(ids))
            self.collection.upsert(
                ids=ids[i:end],
                embeddings=embeddings[i:end],
                documents=documents[i:end],
                metadatas=metadatas[i:end],
            )
        
        console.print(f"[green]✓[/green] Indexed {len(ids)} chunks")
        return len(ids)
    
    def search(
        self,
        query: str,
        limit: int = 10,
        type_filter: str | None = None,
        repo_filter: str | None = None,
    ) -> list[dict]:
        """
        Semantic search across the knowledge base.
        
        Args:
            query: Natural language query
            limit: Maximum results to return
            type_filter: Filter by type (schema, service, api)
            repo_filter: Filter by repository name
        
        Returns:
            List of results with scores and metadata
        """
        # Build where clause for filtering
        where = None
        where_conditions = []
        
        if type_filter:
            where_conditions.append({"type": type_filter})
        if repo_filter:
            where_conditions.append({"repo": {"$contains": repo_filter}})
        
        if len(where_conditions) == 1:
            where = where_conditions[0]
        elif len(where_conditions) > 1:
            where = {"$and": where_conditions}
        
        # Generate query embedding
        query_embedding = self.model.encode([query])[0].tolist()
        
        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        
        # Format results
        formatted = []
        
        if results and results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 0
                # Convert cosine distance to similarity score (0-1)
                similarity = 1 - distance
                
                formatted.append({
                    "id": doc_id,
                    "score": round(similarity, 4),
                    "text": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                })
        
        return formatted
    
    def search_similar(self, chunk_id: str, limit: int = 5) -> list[dict]:
        """Find chunks similar to a given chunk."""
        # Get the chunk's embedding
        result = self.collection.get(
            ids=[chunk_id],
            include=["embeddings"]
        )
        
        if not result["embeddings"]:
            return []
        
        embedding = result["embeddings"][0]
        
        # Search for similar (exclude self)
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=limit + 1,  # +1 to account for self
            include=["documents", "metadatas", "distances"],
        )
        
        # Format and exclude self
        formatted = []
        
        if results and results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                if doc_id == chunk_id:
                    continue
                
                distance = results["distances"][0][i] if results["distances"] else 0
                similarity = 1 - distance
                
                formatted.append({
                    "id": doc_id,
                    "score": round(similarity, 4),
                    "text": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                })
                
                if len(formatted) >= limit:
                    break
        
        return formatted
    
    def ask(self, question: str, limit: int = 5) -> dict:
        """
        Answer a question using the knowledge base.
        Returns relevant context for RAG.
        """
        results = self.search(question, limit=limit)
        
        # Build context from results
        context_parts = []
        sources = []
        
        for result in results:
            if result["score"] > 0.3:  # Relevance threshold
                context_parts.append(result["text"])
                sources.append({
                    "id": result["id"],
                    "score": result["score"],
                    "type": result["metadata"].get("type"),
                    "name": result["metadata"].get("name"),
                    "repo": result["metadata"].get("repo"),
                })
        
        return {
            "question": question,
            "context": "\n\n---\n\n".join(context_parts),
            "sources": sources,
            "result_count": len(results),
        }
    
    def get_stats(self) -> dict:
        """Get statistics about the index."""
        count = self.collection.count()
        
        # Sample to get type distribution
        sample = self.collection.get(
            limit=min(count, 1000),
            include=["metadatas"]
        )
        
        type_counts = {}
        repo_counts = {}
        
        for metadata in sample.get("metadatas", []):
            t = metadata.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
            
            r = metadata.get("repo", "unknown")
            repo_counts[r] = repo_counts.get(r, 0) + 1
        
        return {
            "total_chunks": count,
            "type_distribution": type_counts,
            "repos_sampled": len(repo_counts),
            "model": self.model_name,
            "persist_dir": str(self.persist_dir),
        }


def main():
    """CLI for semantic search."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Semantic search for SenseBase")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--index", help="Index chunks from JSON file")
    parser.add_argument("--model", default="all-MiniLM-L6-v2", help="Embedding model")
    parser.add_argument("--persist", default="./output/vectors/chroma", help="ChromaDB path")
    parser.add_argument("--limit", "-n", type=int, default=10, help="Max results")
    parser.add_argument("--type", help="Filter by type (schema, service, api)")
    parser.add_argument("--repo", help="Filter by repository")
    parser.add_argument("--ask", action="store_true", help="Question-answering mode")
    parser.add_argument("--stats", action="store_true", help="Show index statistics")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    search = SemanticSearch(
        persist_dir=args.persist,
        model_name=args.model,
    )
    
    if args.index:
        search.index_chunks(args.index)
        return
    
    if args.stats:
        stats = search.get_stats()
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            console.print(f"[bold]Index Statistics[/bold]")
            console.print(f"  Total chunks: {stats['total_chunks']}")
            console.print(f"  Model: {stats['model']}")
            console.print(f"  Types: {stats['type_distribution']}")
        return
    
    if not args.query:
        parser.print_help()
        return
    
    if args.ask:
        result = search.ask(args.query, limit=args.limit)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            console.print(f"\n[bold]Question:[/bold] {result['question']}\n")
            console.print(f"[bold]Relevant Context ({len(result['sources'])} sources):[/bold]\n")
            console.print(result['context'])
            console.print(f"\n[dim]Sources: {[s['name'] for s in result['sources']]}[/dim]")
    else:
        results = search.search(
            args.query,
            limit=args.limit,
            type_filter=args.type,
            repo_filter=args.repo,
        )
        
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            console.print(f"\n[bold]Results for:[/bold] {args.query}\n")
            for i, result in enumerate(results, 1):
                meta = result['metadata']
                console.print(f"[cyan]{i}.[/cyan] [{result['score']:.2f}] {meta.get('type', '?')}: {meta.get('name', '?')}")
                console.print(f"   [dim]{meta.get('repo', '?')}[/dim]")
                # Show snippet
                text = result['text'][:200].replace('\n', ' ')
                console.print(f"   {text}...")
                console.print()


if __name__ == "__main__":
    main()
