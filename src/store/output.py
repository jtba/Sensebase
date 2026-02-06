"""Output generators for different formats."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from .knowledge_base import KnowledgeBase

console = Console()


class OutputGenerator:
    """Generate output in various formats from the knowledge base."""
    
    def __init__(self, kb: KnowledgeBase, output_dir: Path | str = "./output"):
        self.kb = kb
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_all(self) -> None:
        """Generate all output formats."""
        self.generate_json()
        self.generate_markdown()
        self.generate_vector_chunks()
    
    def generate_json(self) -> None:
        """Generate JSON output for AI agents."""
        json_dir = self.output_dir / "json"
        json_dir.mkdir(exist_ok=True)
        
        # Main knowledge base
        self.kb.save(json_dir / "knowledge_base.json")
        
        # Separate files for each category
        self._write_json(json_dir / "schemas.json", self.kb.get_all_schemas())
        self._write_json(json_dir / "apis.json", self.kb.get_all_apis())
        self._write_json(json_dir / "dependencies.json", self.kb.get_all_dependencies())
        self._write_json(json_dir / "services.json", self.kb.get_all_services())
        
        console.print(f"[green]✓[/green] Generated JSON output in {json_dir}")
    
    def _write_json(self, path: Path, data: Any) -> None:
        """Write data as JSON."""
        path.write_text(json.dumps(data, indent=2, default=str))
    
    def generate_markdown(self) -> None:
        """Generate Markdown documentation for humans and AI chat."""
        md_dir = self.output_dir / "markdown"
        md_dir.mkdir(exist_ok=True)
        
        # Generate index
        self._generate_index(md_dir)
        
        # Generate schema documentation
        self._generate_schema_docs(md_dir / "schemas")
        
        # Generate API documentation
        self._generate_api_docs(md_dir / "apis")
        
        # Generate service documentation
        self._generate_service_docs(md_dir / "services")
        
        # Generate dependency documentation
        self._generate_dependency_docs(md_dir / "dependencies")
        
        console.print(f"[green]✓[/green] Generated Markdown output in {md_dir}")
    
    def _generate_index(self, md_dir: Path) -> None:
        """Generate main index file."""
        summary = self.kb.get_summary()
        
        content = f"""# ContextPedia Knowledge Base

Generated: {summary['generated_at']}

## Summary

| Metric | Count |
|--------|-------|
| Repositories Analyzed | {summary['repositories_analyzed']} |
| Data Schemas | {summary['total_schemas']} ({summary['unique_schemas']} unique) |
| API Endpoints | {summary['total_apis']} |
| Services | {summary['total_services']} |
| Dependencies | {summary['total_dependencies']} ({summary['unique_dependencies']} unique) |

## Navigation

- [Schemas](./schemas/index.md) - Data models, entities, and types
- [APIs](./apis/index.md) - REST/GraphQL endpoints
- [Services](./services/index.md) - Business logic and handlers
- [Dependencies](./dependencies/index.md) - External packages and libraries

## Quick Reference

### Most Common Schemas
{self._list_top_items(self.kb.get_all_schemas(), 'name', 10)}

### Most Used Dependencies
{self._list_top_items(self.kb.get_all_dependencies(), 'name', 10)}
"""
        
        (md_dir / "index.md").write_text(content)
    
    def _list_top_items(self, items: list[dict], key: str, limit: int) -> str:
        """Create a bullet list of top items."""
        seen = set()
        lines = []
        for item in items:
            name = item.get(key, "unknown")
            if name not in seen:
                seen.add(name)
                lines.append(f"- {name}")
                if len(lines) >= limit:
                    break
        return "\n".join(lines) if lines else "- None found"
    
    def _generate_schema_docs(self, schema_dir: Path) -> None:
        """Generate schema documentation."""
        schema_dir.mkdir(exist_ok=True)
        
        schemas = self.kb.get_all_schemas()
        
        # Group by name
        by_name: dict[str, list[dict]] = {}
        for schema in schemas:
            name = schema.get("name", "unknown")
            if name not in by_name:
                by_name[name] = []
            by_name[name].append(schema)
        
        # Generate index
        index_content = "# Data Schemas\n\n"
        for name in sorted(by_name.keys()):
            index_content += f"- [{name}](./{self._safe_filename(name)}.md)\n"
        (schema_dir / "index.md").write_text(index_content)
        
        # Generate individual schema files
        for name, instances in by_name.items():
            content = self._render_schema(name, instances)
            (schema_dir / f"{self._safe_filename(name)}.md").write_text(content)
    
    def _render_schema(self, name: str, instances: list[dict]) -> str:
        """Render a schema to Markdown."""
        content = f"# {name}\n\n"
        
        for i, schema in enumerate(instances):
            if len(instances) > 1:
                content += f"## Instance {i + 1}\n\n"
            
            content += f"- **Type:** {schema.get('type', 'unknown')}\n"
            content += f"- **Source:** `{schema.get('source_file', 'unknown')}`\n"
            content += f"- **Repository:** {schema.get('repo', 'unknown')}\n\n"
            
            # Fields
            fields = schema.get("fields", [])
            if fields:
                content += "### Fields\n\n"
                content += "| Name | Type | Constraints |\n"
                content += "|------|------|-------------|\n"
                for field in fields:
                    constraints = ", ".join(field.get("constraints", [])) or "-"
                    content += f"| {field.get('name', '-')} | {field.get('type', '-')} | {constraints} |\n"
                content += "\n"
            
            # Relationships
            relationships = schema.get("relationships", [])
            if relationships:
                content += "### Relationships\n\n"
                for rel in relationships:
                    content += f"- **{rel.get('type', 'unknown')}** → {rel.get('target', 'unknown')} (via `{rel.get('field', '-')}`)\n"
                content += "\n"
            
            # Raw definition
            raw = schema.get("raw_definition")
            if raw:
                content += "### Definition\n\n```\n"
                content += raw[:2000]  # Truncate long definitions
                if len(raw) > 2000:
                    content += "\n... (truncated)"
                content += "\n```\n\n"
        
        return content
    
    def _generate_api_docs(self, api_dir: Path) -> None:
        """Generate API documentation."""
        api_dir.mkdir(exist_ok=True)
        
        apis = self.kb.get_all_apis()
        
        # Group by path prefix
        by_prefix: dict[str, list[dict]] = {}
        for api in apis:
            path = api.get("path", "/")
            prefix = path.split("/")[1] if "/" in path else "root"
            if prefix not in by_prefix:
                by_prefix[prefix] = []
            by_prefix[prefix].append(api)
        
        # Generate index
        index_content = "# API Endpoints\n\n"
        for prefix in sorted(by_prefix.keys()):
            index_content += f"## /{prefix}\n\n"
            for api in by_prefix[prefix]:
                method = api.get("method", "?")
                path = api.get("path", "?")
                index_content += f"- `{method}` [{path}](./{self._safe_filename(prefix)}.md)\n"
            index_content += "\n"
        (api_dir / "index.md").write_text(index_content)
        
        # Generate per-prefix files
        for prefix, endpoints in by_prefix.items():
            content = f"# /{prefix} Endpoints\n\n"
            for api in endpoints:
                content += f"## `{api.get('method', '?')}` {api.get('path', '?')}\n\n"
                content += f"- **Source:** `{api.get('source_file', 'unknown')}`\n"
                content += f"- **Handler:** `{api.get('handler', 'unknown')}`\n"
                if api.get("description"):
                    content += f"- **Description:** {api['description']}\n"
                content += "\n"
            (api_dir / f"{self._safe_filename(prefix)}.md").write_text(content)
    
    def _generate_service_docs(self, service_dir: Path) -> None:
        """Generate service documentation."""
        service_dir.mkdir(exist_ok=True)
        
        services = self.kb.get_all_services()
        
        # Generate index
        index_content = "# Services & Business Logic\n\n"
        for service in services:
            name = service.get("name", "unknown")
            index_content += f"- [{name}](./{self._safe_filename(name)}.md)\n"
        (service_dir / "index.md").write_text(index_content)
        
        # Generate individual files
        for service in services:
            name = service.get("name", "unknown")
            content = f"# {name}\n\n"
            content += f"- **Type:** {service.get('type', 'unknown')}\n"
            content += f"- **Source:** `{service.get('source_file', 'unknown')}`\n"
            if service.get("description"):
                content += f"\n{service['description']}\n"
            
            # Dependencies
            deps = service.get("dependencies", [])
            if deps:
                content += "\n## Dependencies\n\n"
                for dep in deps:
                    content += f"- {dep}\n"
            
            # Methods
            methods = service.get("methods", [])
            if methods:
                content += "\n## Methods\n\n"
                for method in methods:
                    content += f"### {method.get('name', 'unknown')}\n\n"
                    if method.get("docstring"):
                        content += f"{method['docstring']}\n\n"
                    params = method.get("params", [])
                    if params:
                        content += "**Parameters:**\n"
                        for param in params:
                            if isinstance(param, dict):
                                content += f"- `{param.get('name', '?')}`: {param.get('type', 'any')}\n"
                            else:
                                content += f"- {param}\n"
                    returns = method.get("returns") or method.get("return_type")
                    if returns:
                        content += f"\n**Returns:** `{returns}`\n"
                    content += "\n"
            
            (service_dir / f"{self._safe_filename(name)}.md").write_text(content)
    
    def _generate_dependency_docs(self, dep_dir: Path) -> None:
        """Generate dependency documentation."""
        dep_dir.mkdir(exist_ok=True)
        
        deps = self.kb.get_all_dependencies()
        
        # Group by ecosystem
        by_ecosystem: dict[str, list[dict]] = {}
        for dep in deps:
            eco = dep.get("ecosystem", "unknown")
            if eco not in by_ecosystem:
                by_ecosystem[eco] = []
            by_ecosystem[eco].append(dep)
        
        # Generate index
        index_content = "# Dependencies\n\n"
        for eco in sorted(by_ecosystem.keys()):
            index_content += f"## {eco.title()}\n\n"
            seen = set()
            for dep in by_ecosystem[eco]:
                name = dep.get("name", "unknown")
                if name not in seen:
                    seen.add(name)
                    version = dep.get("version", "")
                    index_content += f"- {name}"
                    if version:
                        index_content += f" `{version}`"
                    index_content += "\n"
            index_content += "\n"
        (dep_dir / "index.md").write_text(index_content)
    
    def generate_vector_chunks(self) -> None:
        """Generate chunks for vector embedding."""
        vector_dir = self.output_dir / "vectors"
        vector_dir.mkdir(exist_ok=True)
        
        chunks = []
        
        # Chunk schemas
        for schema in self.kb.get_all_schemas():
            text = self._schema_to_text(schema)
            chunks.append({
                "id": f"schema:{schema.get('name', 'unknown')}:{schema.get('source_file', '')}",
                "type": "schema",
                "name": schema.get("name"),
                "repo": schema.get("repo"),
                "text": text,
            })
        
        # Chunk services
        for service in self.kb.get_all_services():
            text = self._service_to_text(service)
            chunks.append({
                "id": f"service:{service.get('name', 'unknown')}:{service.get('source_file', '')}",
                "type": "service",
                "name": service.get("name"),
                "repo": service.get("repo"),
                "text": text,
            })
        
        # Chunk APIs
        for api in self.kb.get_all_apis():
            text = self._api_to_text(api)
            chunks.append({
                "id": f"api:{api.get('method', '')}:{api.get('path', '')}:{api.get('source_file', '')}",
                "type": "api",
                "path": api.get("path"),
                "method": api.get("method"),
                "repo": api.get("repo"),
                "text": text,
            })
        
        # Save chunks
        (vector_dir / "chunks.json").write_text(
            json.dumps(chunks, indent=2, default=str)
        )
        
        console.print(f"[green]✓[/green] Generated {len(chunks)} vector chunks in {vector_dir}")
    
    def _schema_to_text(self, schema: dict) -> str:
        """Convert schema to searchable text."""
        lines = [
            f"Schema: {schema.get('name', 'unknown')}",
            f"Type: {schema.get('type', 'unknown')}",
            f"Repository: {schema.get('repo', 'unknown')}",
            f"Source: {schema.get('source_file', 'unknown')}",
            "Fields:",
        ]
        for field in schema.get("fields", []):
            constraints = ", ".join(field.get("constraints", []))
            lines.append(f"  - {field.get('name', '?')}: {field.get('type', '?')} ({constraints})")
        
        for rel in schema.get("relationships", []):
            lines.append(f"Relationship: {rel.get('type', '?')} to {rel.get('target', '?')}")
        
        return "\n".join(lines)
    
    def _service_to_text(self, service: dict) -> str:
        """Convert service to searchable text."""
        lines = [
            f"Service: {service.get('name', 'unknown')}",
            f"Type: {service.get('type', 'unknown')}",
            f"Repository: {service.get('repo', 'unknown')}",
            f"Source: {service.get('source_file', 'unknown')}",
        ]
        if service.get("description"):
            lines.append(f"Description: {service['description']}")
        
        lines.append("Methods:")
        for method in service.get("methods", []):
            lines.append(f"  - {method.get('name', '?')}")
            if method.get("docstring"):
                lines.append(f"    {method['docstring'][:200]}")
        
        lines.append("Dependencies:")
        for dep in service.get("dependencies", []):
            lines.append(f"  - {dep}")
        
        return "\n".join(lines)
    
    def _api_to_text(self, api: dict) -> str:
        """Convert API to searchable text."""
        lines = [
            f"API Endpoint: {api.get('method', '?')} {api.get('path', '?')}",
            f"Handler: {api.get('handler', 'unknown')}",
            f"Repository: {api.get('repo', 'unknown')}",
            f"Source: {api.get('source_file', 'unknown')}",
        ]
        if api.get("description"):
            lines.append(f"Description: {api['description']}")
        
        return "\n".join(lines)
    
    def _safe_filename(self, name: str) -> str:
        """Convert name to safe filename."""
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in name).lower()
