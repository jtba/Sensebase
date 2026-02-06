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
        
        return kb
