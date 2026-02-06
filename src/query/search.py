"""Search engine for querying the knowledge base."""

import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()


class SearchEngine:
    """Search and query the knowledge base."""
    
    def __init__(self, kb_path: Path | str = "./output/json/knowledge_base.json"):
        self.kb_path = Path(kb_path)
        self.data: dict = {}
        self._load()
    
    def _load(self) -> None:
        """Load knowledge base from disk."""
        if self.kb_path.exists():
            self.data = json.loads(self.kb_path.read_text())
        else:
            console.print(f"[yellow]Warning:[/yellow] Knowledge base not found at {self.kb_path}")
    
    def search(self, query: str, limit: int = 20) -> list[dict]:
        """
        Search across all knowledge types.
        Returns results ranked by relevance.
        """
        query_lower = query.lower()
        results = []
        
        # Search schemas
        for schema in self.data.get("schemas", []):
            score = self._score_match(query_lower, [
                schema.get("name", ""),
                *[f.get("name", "") for f in schema.get("fields", [])],
                *[f.get("type", "") for f in schema.get("fields", [])],
            ])
            if score > 0:
                results.append({
                    "type": "schema",
                    "name": schema.get("name"),
                    "score": score,
                    "data": schema,
                })
        
        # Search APIs
        for api in self.data.get("apis", []):
            score = self._score_match(query_lower, [
                api.get("path", ""),
                api.get("method", ""),
                api.get("handler", ""),
                api.get("description", "") or "",
            ])
            if score > 0:
                results.append({
                    "type": "api",
                    "name": f"{api.get('method', '?')} {api.get('path', '?')}",
                    "score": score,
                    "data": api,
                })
        
        # Search services
        for service in self.data.get("services", []):
            score = self._score_match(query_lower, [
                service.get("name", ""),
                service.get("description", "") or "",
                *[m.get("name", "") for m in service.get("methods", [])],
            ])
            if score > 0:
                results.append({
                    "type": "service",
                    "name": service.get("name"),
                    "score": score,
                    "data": service,
                })
        
        # Search dependencies
        for dep in self.data.get("dependencies", []):
            score = self._score_match(query_lower, [
                dep.get("name", ""),
                dep.get("ecosystem", ""),
            ])
            if score > 0:
                results.append({
                    "type": "dependency",
                    "name": dep.get("name"),
                    "score": score,
                    "data": dep,
                })
        
        # Sort by score and limit
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
    
    def _score_match(self, query: str, texts: list[str]) -> float:
        """Score how well texts match the query."""
        score = 0.0
        query_terms = query.split()
        
        for text in texts:
            text_lower = text.lower()
            
            # Exact match
            if query == text_lower:
                score += 10.0
            
            # Contains full query
            elif query in text_lower:
                score += 5.0
            
            # Contains query terms
            else:
                for term in query_terms:
                    if term in text_lower:
                        score += 1.0
        
        return score
    
    def find_schema(self, name: str) -> list[dict]:
        """Find schemas by name."""
        name_lower = name.lower()
        return [
            s for s in self.data.get("schemas", [])
            if name_lower in s.get("name", "").lower()
        ]
    
    def find_api(self, path: str = "", method: str = "") -> list[dict]:
        """Find API endpoints."""
        results = []
        for api in self.data.get("apis", []):
            if path and path.lower() not in api.get("path", "").lower():
                continue
            if method and method.upper() != api.get("method", "").upper():
                continue
            results.append(api)
        return results
    
    def find_service(self, name: str) -> list[dict]:
        """Find services by name."""
        name_lower = name.lower()
        return [
            s for s in self.data.get("services", [])
            if name_lower in s.get("name", "").lower()
        ]
    
    def find_dependency_usage(self, name: str) -> list[dict]:
        """Find where a dependency is used."""
        name_lower = name.lower()
        return [
            d for d in self.data.get("dependencies", [])
            if name_lower in d.get("name", "").lower()
        ]
    
    def get_schema_relationships(self, schema_name: str) -> dict:
        """Get all relationships for a schema."""
        relationships = {
            "references_to": [],  # Schemas this one references
            "referenced_by": [],  # Schemas that reference this one
        }
        
        schemas = self.find_schema(schema_name)
        if not schemas:
            return relationships
        
        target_name = schemas[0].get("name", "").lower()
        
        # Find what this schema references
        for schema in schemas:
            for rel in schema.get("relationships", []):
                relationships["references_to"].append({
                    "target": rel.get("target"),
                    "type": rel.get("type"),
                    "via": rel.get("field"),
                })
        
        # Find schemas that reference this one
        for schema in self.data.get("schemas", []):
            for rel in schema.get("relationships", []):
                if rel.get("target", "").lower() == target_name:
                    relationships["referenced_by"].append({
                        "source": schema.get("name"),
                        "type": rel.get("type"),
                        "via": rel.get("field"),
                    })
        
        return relationships
    
    def get_service_dependencies(self, service_name: str) -> dict:
        """Get dependency graph for a service."""
        graph = {
            "depends_on": [],
            "depended_by": [],
        }
        
        services = self.find_service(service_name)
        if not services:
            return graph
        
        target_name = services[0].get("name", "").lower()
        
        # Get direct dependencies
        for service in services:
            graph["depends_on"] = service.get("dependencies", [])
        
        # Find services that depend on this one
        for service in self.data.get("services", []):
            deps = [d.lower() for d in service.get("dependencies", [])]
            if target_name in deps:
                graph["depended_by"].append(service.get("name"))
        
        return graph
    
    def print_results(self, results: list[dict]) -> None:
        """Pretty print search results."""
        if not results:
            console.print("[yellow]No results found[/yellow]")
            return
        
        table = Table(title="Search Results")
        table.add_column("Type", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Score", style="magenta")
        table.add_column("Source")
        
        for result in results:
            data = result.get("data", {})
            source = data.get("source_file", data.get("repo", "?"))
            if len(source) > 50:
                source = "..." + source[-47:]
            
            table.add_row(
                result.get("type", "?"),
                result.get("name", "?"),
                f"{result.get('score', 0):.1f}",
                source,
            )
        
        console.print(table)


def main():
    """CLI for searching the knowledge base."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Search the ContextPedia knowledge base")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--kb", default="./output/json/knowledge_base.json", help="Knowledge base path")
    parser.add_argument("--schema", help="Find schema by name")
    parser.add_argument("--api", help="Find API by path")
    parser.add_argument("--service", help="Find service by name")
    parser.add_argument("--deps", help="Find dependency usage")
    parser.add_argument("--limit", type=int, default=20, help="Max results")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    engine = SearchEngine(args.kb)
    
    if args.schema:
        results = engine.find_schema(args.schema)
    elif args.api:
        results = engine.find_api(path=args.api)
    elif args.service:
        results = engine.find_service(args.service)
    elif args.deps:
        results = engine.find_dependency_usage(args.deps)
    elif args.query:
        results = engine.search(args.query, limit=args.limit)
    else:
        parser.print_help()
        return
    
    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        if isinstance(results, list) and results and "data" not in results[0]:
            # Direct query results, wrap them
            results = [{"type": "result", "name": r.get("name", "?"), "score": 1, "data": r} for r in results]
        engine.print_results(results)


if __name__ == "__main__":
    main()
