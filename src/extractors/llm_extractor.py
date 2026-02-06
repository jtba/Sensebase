"""LLM-based code extraction using Claude."""

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..analyzers.base import (
    AnalysisResult,
    SchemaInfo,
    BusinessLogicInfo,
    APIInfo,
    DependencyInfo,
    DataFlowInfo,
)

console = Console()

# Extraction prompt template
EXTRACTION_PROMPT = """Analyze this source code file and extract structured knowledge.

File: {file_path}
Language: {language}
Repository: {repo_name}

```{language}
{content}
```

Extract the following (if present). Be thorough but only include what's actually in the code:

1. **Schemas/Models**: Data structures, entities, types, interfaces
   - Name, type (entity/model/interface/type), fields with types and constraints
   - Relationships to other schemas (foreign keys, references)

2. **Business Logic**: Services, handlers, controllers, managers
   - Name, type, description of what it does
   - Public methods with parameters and return types
   - Dependencies (other services/components it uses)
   - What data/entities it accesses

3. **API Endpoints**: REST/GraphQL endpoints
   - Path, HTTP method, handler function
   - Parameters (path, query, body)
   - Description of purpose

4. **Data Flows**: How data moves through the system
   - Source → Target relationships
   - Type: read, write, transform, publish, subscribe

5. **Inferences**: Things you can infer from patterns
   - Business domain (payments, auth, inventory, etc.)
   - Design patterns used
   - Potential concerns (security, performance)

Respond with valid JSON only:
```json
{
  "schemas": [
    {
      "name": "string",
      "type": "entity|model|interface|type|table",
      "description": "what this represents",
      "fields": [
        {"name": "string", "type": "string", "constraints": ["not_null", "unique", "primary_key"], "description": "optional"}
      ],
      "relationships": [
        {"type": "has_many|belongs_to|has_one|many_to_many", "target": "OtherSchema", "via": "field_name"}
      ]
    }
  ],
  "business_logic": [
    {
      "name": "string",
      "type": "service|handler|controller|manager|repository",
      "description": "what this component does",
      "methods": [
        {"name": "string", "description": "what it does", "params": [{"name": "string", "type": "string"}], "returns": "string"}
      ],
      "dependencies": ["OtherService", "Repository"],
      "data_accessed": ["Entity1", "Entity2"]
    }
  ],
  "apis": [
    {
      "path": "/api/v1/something",
      "method": "GET|POST|PUT|DELETE",
      "handler": "functionName",
      "description": "what this endpoint does",
      "params": [{"name": "string", "in": "path|query|body", "type": "string", "required": true}]
    }
  ],
  "data_flows": [
    {
      "source": "Component/Entity",
      "target": "Component/Entity",
      "type": "read|write|transform|publish|subscribe",
      "description": "what happens"
    }
  ],
  "inferences": {
    "domain": "payments|auth|inventory|etc",
    "patterns": ["repository pattern", "event sourcing", "etc"],
    "concerns": ["handles PII", "financial data", "etc"]
  }
}
```

If a section has nothing to extract, use an empty array. Only include what's actually present or clearly inferable."""


@dataclass
class ExtractionResult:
    """Result from LLM extraction."""
    file_path: str
    success: bool
    data: dict | None
    error: str | None = None
    tokens_used: int = 0
    cached: bool = False


class LLMExtractor:
    """Extract code knowledge using Claude."""
    
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        cache_dir: Path | str | None = "./output/cache/llm",
        max_file_size: int = 100_000,  # ~100KB max per file
        requests_per_minute: int = 50,
    ):
        self.api_key = api_key or self._get_api_key()
        self.model = model
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.max_file_size = max_file_size
        self.requests_per_minute = requests_per_minute
        self._last_request_time = 0
        
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.client = httpx.Client(
            base_url="https://api.anthropic.com",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=120.0,
        )
    
    def _get_api_key(self) -> str:
        """Get API key from environment."""
        import os
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError(
                "ANTHROPIC_API_KEY not set. "
                "Set it in environment or pass api_key parameter."
            )
        return key
    
    def _get_cache_key(self, content: str, file_path: str) -> str:
        """Generate cache key for content."""
        h = hashlib.sha256()
        h.update(content.encode())
        h.update(file_path.encode())
        h.update(self.model.encode())
        return h.hexdigest()[:16]
    
    def _get_cached(self, cache_key: str) -> dict | None:
        """Get cached extraction result."""
        if not self.cache_dir:
            return None
        
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text())
            except Exception:
                return None
        return None
    
    def _save_cache(self, cache_key: str, data: dict) -> None:
        """Save extraction result to cache."""
        if not self.cache_dir:
            return
        
        cache_file = self.cache_dir / f"{cache_key}.json"
        cache_file.write_text(json.dumps(data, indent=2))
    
    def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        min_interval = 60.0 / self.requests_per_minute
        elapsed = time.time() - self._last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()
    
    def _detect_language(self, file_path: Path) -> str:
        """Detect language from file extension."""
        ext_map = {
            ".py": "python",
            ".pyi": "python",
            ".java": "java",
            ".go": "go",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".rb": "ruby",
            ".rs": "rust",
            ".cs": "csharp",
            ".php": "php",
            ".sql": "sql",
            ".graphql": "graphql",
            ".gql": "graphql",
            ".proto": "protobuf",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".xml": "xml",
        }
        return ext_map.get(file_path.suffix.lower(), "unknown")
    
    def extract_file(
        self,
        file_path: Path,
        content: str,
        repo_name: str = "",
    ) -> ExtractionResult:
        """Extract knowledge from a single file using Claude."""
        str_path = str(file_path)
        
        # Check file size
        if len(content) > self.max_file_size:
            return ExtractionResult(
                file_path=str_path,
                success=False,
                data=None,
                error=f"File too large ({len(content)} bytes)",
            )
        
        # Check cache
        cache_key = self._get_cache_key(content, str_path)
        cached = self._get_cached(cache_key)
        if cached:
            return ExtractionResult(
                file_path=str_path,
                success=True,
                data=cached,
                cached=True,
            )
        
        language = self._detect_language(file_path)
        
        # Build prompt
        prompt = EXTRACTION_PROMPT.format(
            file_path=str_path,
            language=language,
            repo_name=repo_name,
            content=content,
        )
        
        # Rate limit
        self._rate_limit()
        
        # Call Claude
        try:
            response = self.client.post(
                "/v1/messages",
                json={
                    "model": self.model,
                    "max_tokens": 4096,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                },
            )
            response.raise_for_status()
            result = response.json()
            
            # Extract JSON from response
            text = result["content"][0]["text"]
            
            # Find JSON in response
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = text[json_start:json_end]
                data = json.loads(json_str)
                
                # Cache the result
                self._save_cache(cache_key, data)
                
                return ExtractionResult(
                    file_path=str_path,
                    success=True,
                    data=data,
                    tokens_used=result.get("usage", {}).get("input_tokens", 0) + 
                               result.get("usage", {}).get("output_tokens", 0),
                )
            else:
                return ExtractionResult(
                    file_path=str_path,
                    success=False,
                    data=None,
                    error="No JSON found in response",
                )
        
        except httpx.HTTPStatusError as e:
            return ExtractionResult(
                file_path=str_path,
                success=False,
                data=None,
                error=f"API error: {e.response.status_code}",
            )
        except json.JSONDecodeError as e:
            return ExtractionResult(
                file_path=str_path,
                success=False,
                data=None,
                error=f"JSON parse error: {e}",
            )
        except Exception as e:
            return ExtractionResult(
                file_path=str_path,
                success=False,
                data=None,
                error=str(e),
            )
    
    def extract_to_analysis_result(
        self,
        extraction: ExtractionResult,
        repo_path: str,
        repo_name: str,
    ) -> AnalysisResult:
        """Convert LLM extraction to AnalysisResult."""
        result = AnalysisResult(
            repo_path=repo_path,
            repo_name=repo_name,
        )
        
        if not extraction.success or not extraction.data:
            if extraction.error:
                result.errors.append(f"{extraction.file_path}: {extraction.error}")
            return result
        
        data = extraction.data
        
        # Convert schemas
        for schema in data.get("schemas", []):
            result.schemas.append(SchemaInfo(
                name=schema.get("name", "unknown"),
                type=schema.get("type", "unknown"),
                source_file=extraction.file_path,
                fields=schema.get("fields", []),
                relationships=schema.get("relationships", []),
                raw_definition=None,
            ))
        
        # Convert business logic
        for logic in data.get("business_logic", []):
            result.business_logic.append(BusinessLogicInfo(
                name=logic.get("name", "unknown"),
                type=logic.get("type", "unknown"),
                source_file=extraction.file_path,
                description=logic.get("description"),
                methods=logic.get("methods", []),
                dependencies=logic.get("dependencies", []),
                data_accessed=logic.get("data_accessed", []),
            ))
        
        # Convert APIs
        for api in data.get("apis", []):
            result.apis.append(APIInfo(
                path=api.get("path", ""),
                method=api.get("method", ""),
                source_file=extraction.file_path,
                handler=api.get("handler", ""),
                params=api.get("params", []),
                request_body=api.get("request_body"),
                response=api.get("response"),
                description=api.get("description"),
            ))
        
        # Convert data flows
        for flow in data.get("data_flows", []):
            result.data_flows.append(DataFlowInfo(
                source=flow.get("source", ""),
                target=flow.get("target", ""),
                type=flow.get("type", ""),
                description=flow.get("description"),
                source_file=extraction.file_path,
            ))
        
        result.analyzed_files.append(extraction.file_path)
        
        return result


class LLMAnalyzer:
    """Analyze repositories using LLM extraction."""
    
    def __init__(
        self,
        extractor: LLMExtractor | None = None,
        skip_dirs: list[str] | None = None,
        include_extensions: list[str] | None = None,
        max_file_size: int = 100_000,
    ):
        self.extractor = extractor or LLMExtractor()
        self.skip_dirs = set(skip_dirs or [
            "node_modules", "vendor", "venv", ".venv", "__pycache__",
            "target", "build", "dist", ".git", ".idea", ".vscode",
        ])
        self.include_extensions = set(include_extensions or [
            ".py", ".java", ".go", ".js", ".ts", ".jsx", ".tsx",
            ".rb", ".rs", ".cs", ".php",
            ".sql", ".graphql", ".gql", ".proto",
        ])
        self.max_file_size = max_file_size
    
    def find_files(self, repo_path: Path) -> Iterator[Path]:
        """Find relevant files in repository."""
        for file_path in repo_path.rglob("*"):
            # Skip directories in exclusion list
            if any(skip in file_path.parts for skip in self.skip_dirs):
                continue
            
            if not file_path.is_file():
                continue
            
            # Check extension
            if file_path.suffix.lower() not in self.include_extensions:
                continue
            
            # Check file size
            try:
                if file_path.stat().st_size > self.max_file_size:
                    continue
            except OSError:
                continue
            
            yield file_path
    
    def analyze_repository(self, repo_path: Path) -> AnalysisResult:
        """Analyze a repository using LLM extraction."""
        repo_name = repo_path.name
        
        result = AnalysisResult(
            repo_path=str(repo_path),
            repo_name=repo_name,
        )
        
        files = list(self.find_files(repo_path))
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Analyzing {repo_name}...", total=len(files))
            
            for file_path in files:
                progress.update(task, description=f"[{repo_name}] {file_path.name}")
                
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    
                    extraction = self.extractor.extract_file(
                        file_path=file_path,
                        content=content,
                        repo_name=repo_name,
                    )
                    
                    file_result = self.extractor.extract_to_analysis_result(
                        extraction=extraction,
                        repo_path=str(repo_path),
                        repo_name=repo_name,
                    )
                    
                    result.merge(file_result)
                    result.file_count += 1
                    
                    if extraction.cached:
                        progress.console.print(f"  [dim]✓ {file_path.name} (cached)[/dim]")
                    elif extraction.success:
                        progress.console.print(f"  [green]✓[/green] {file_path.name}")
                    else:
                        progress.console.print(f"  [yellow]![/yellow] {file_path.name}: {extraction.error}")
                
                except Exception as e:
                    result.errors.append(f"{file_path}: {e}")
                    progress.console.print(f"  [red]✗[/red] {file_path.name}: {e}")
                
                progress.advance(task)
        
        return result


def main():
    """CLI for LLM extraction."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract code knowledge using Claude")
    parser.add_argument("path", help="File or directory to analyze")
    parser.add_argument("--model", default="claude-sonnet-4-20250514", help="Claude model to use")
    parser.add_argument("--no-cache", action="store_true", help="Disable caching")
    parser.add_argument("--output", "-o", help="Output JSON file")
    
    args = parser.parse_args()
    
    path = Path(args.path)
    
    extractor = LLMExtractor(
        model=args.model,
        cache_dir=None if args.no_cache else "./output/cache/llm",
    )
    
    if path.is_file():
        # Single file extraction
        content = path.read_text()
        result = extractor.extract_file(path, content)
        
        if result.success:
            output = json.dumps(result.data, indent=2)
            if args.output:
                Path(args.output).write_text(output)
            else:
                print(output)
        else:
            console.print(f"[red]Error:[/red] {result.error}")
    else:
        # Directory analysis
        analyzer = LLMAnalyzer(extractor=extractor)
        result = analyzer.analyze_repository(path)
        
        console.print(f"\n[bold]Analysis Complete[/bold]")
        console.print(f"  Files analyzed: {result.file_count}")
        console.print(f"  Schemas: {len(result.schemas)}")
        console.print(f"  Services: {len(result.business_logic)}")
        console.print(f"  APIs: {len(result.apis)}")
        console.print(f"  Data flows: {len(result.data_flows)}")
        console.print(f"  Errors: {len(result.errors)}")
        
        if args.output:
            from dataclasses import asdict
            Path(args.output).write_text(json.dumps(asdict(result), indent=2, default=str))
            console.print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()
