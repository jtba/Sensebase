"""LLM-based code extraction using Claude."""

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import anthropic
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
{{
  "schemas": [
    {{
      "name": "string",
      "type": "entity|model|interface|type|table",
      "description": "what this represents",
      "fields": [
        {{"name": "string", "type": "string", "constraints": ["not_null", "unique", "primary_key"], "description": "optional"}}
      ],
      "relationships": [
        {{"type": "has_many|belongs_to|has_one|many_to_many", "target": "OtherSchema", "via": "field_name"}}
      ]
    }}
  ],
  "business_logic": [
    {{
      "name": "string",
      "type": "service|handler|controller|manager|repository",
      "description": "what this component does",
      "methods": [
        {{"name": "string", "description": "what it does", "params": [{{"name": "string", "type": "string"}}], "returns": "string"}}
      ],
      "dependencies": ["OtherService", "Repository"],
      "data_accessed": ["Entity1", "Entity2"]
    }}
  ],
  "apis": [
    {{
      "path": "/api/v1/something",
      "method": "GET|POST|PUT|DELETE",
      "handler": "functionName",
      "description": "what this endpoint does",
      "params": [{{"name": "string", "in": "path|query|body", "type": "string", "required": true}}]
    }}
  ],
  "data_flows": [
    {{
      "source": "Component/Entity",
      "target": "Component/Entity",
      "type": "read|write|transform|publish|subscribe",
      "description": "what happens"
    }}
  ],
  "inferences": {{
    "domain": "payments|auth|inventory|etc",
    "patterns": ["repository pattern", "event sourcing", "etc"],
    "concerns": ["handles PII", "financial data", "etc"]
  }}
}}
```

If a section has nothing to extract, use an empty array. Only include what's actually present or clearly inferable."""

CONTEXT_GENERATION_PROMPT = """You are analyzing a complete code repository to generate a holistic context document.
Your goal is to understand the PURPOSE and BUSINESS MEANING of this service — grounding ALL statements in the actual code.

Repository: {repo_name}

## File Structure
{file_tree}

## Key Files (Full Content)
{tier1_content}

## Code Structure (Signatures & Interfaces)
{tier2_content}

## Additional Files
{tier3_listing}

---

Generate a context document in the following Markdown format. Ground ALL statements in actual code you can see.
Do NOT speculate beyond what the code shows. If something is unclear, say so.

# {repo_name}

## Purpose
Write a clear paragraph about what this service/application does and what business domain it serves.

## When to Use This Service
List specific conditions when an AI agent or developer should route to this service.
Format as bullet points starting with "Use this service when..."

## Business Logic
For each major area of business logic, create a subsection:
### [Logic Area Name]
Describe what it does and WHY it exists (the business rationale, not just the code mechanics).
What rules does it enforce? What invariants does it maintain?

## Data Ownership
List each significant data entity this service manages:
- **[Entity Name]**: What it represents in business terms. Note if this service is the source of truth for this data.

## API Surface
List key endpoints/interfaces with their business purpose:
- **[METHOD path]**: Business-level description of when/why you'd call this.

## Dependencies
List other services/systems this service calls and why:
- **[Service/System]**: Why this dependency exists and what data flows through it.

## Key Schemas
For each important data model:
- **[Schema Name]**: Business meaning and when you'd query this data vs. getting it elsewhere.

---

After the Markdown above, on a new line output EXACTLY `---METADATA---` followed by a JSON block:
```json
{{{{
  "purpose_summary": "one sentence",
  "domain": "primary business domain",
  "when_to_use": ["condition 1", "condition 2"],
  "data_ownership": [
    {{{{"entity": "name", "description": "what it is", "is_source_of_truth": true}}}}
  ],
  "service_dependencies": [
    {{{{"service": "name", "reason": "why"}}}}
  ]
}}}}
```
"""


SEMANTIC_ENRICHMENT_PROMPT = """You have two inputs about a code repository:

1. A business context document (generated from full code analysis)
2. A list of structural metadata (schemas, APIs, services) extracted from the code

Your job: ENRICH the structural metadata with business meaning so that an AI agent can
understand what the data represents and how to query it to answer business questions.

## Repository: {repo_name}

## Business Context
{context_markdown}

## Extracted Schemas
{schemas_json}

## Extracted APIs
{apis_json}

## Extracted Services
{services_json}

---

Generate a JSON document that adds business semantics to each structural element.
Ground ALL descriptions in the business context and code patterns above.

```json
{{{{
  "entity_descriptions": {{{{
    "SchemaName": "One paragraph: what this entity represents in business terms, what real-world thing it models, and when you'd query it."
  }}}},
  "field_descriptions": {{{{
    "SchemaName": {{{{
      "field_name": "What this field means in business terms (not just its type)"
    }}}}
  }}}},
  "api_descriptions": {{{{
    "METHOD /path": "When and why an AI agent or developer should call this endpoint. What business question does it answer?"
  }}}},
  "query_recipes": [
    {{{{
      "question": "A natural language question a business user or AI agent might ask",
      "steps": [
        {{{{
          "action": "Call GET /api/endpoint?param=value",
          "service": "service-name",
          "purpose": "What this step retrieves"
        }}}}
      ],
      "answer_format": "How to interpret and aggregate the response to answer the question."
    }}}}
  ],
  "business_glossary": [
    {{{{
      "term": "BusinessTerm",
      "definition": "A clear definition of what this term means in this system's domain.",
      "related_schemas": ["Schema1", "Schema2"],
      "related_apis": ["GET /api/path"]
    }}}}
  ]
}}}}
```

Rules:
- Only include entities/fields/APIs that actually exist in the structural metadata above.
- For query_recipes, think about the 3-8 most common business questions this service can answer.
- For the business_glossary, define the key domain concepts that would help someone unfamiliar with the system.
- Keep descriptions concise but rich enough for an AI agent to reason over."""


@dataclass
class ExtractionResult:
    """Result from LLM extraction."""
    file_path: str
    success: bool
    data: dict | None
    error: str | None = None
    tokens_used: int = 0
    cached: bool = False


def _claude_cli_available() -> bool:
    """Check if the claude CLI is installed and authenticated."""
    import shutil
    return shutil.which("claude") is not None


class LLMExtractor:
    """Extract code knowledge using Claude.

    Supports two backends:
    - ``api``: Direct Anthropic API calls (requires ANTHROPIC_API_KEY).
    - ``cli``: Uses the local ``claude`` CLI with its OAuth session.
      Automatically selected when no API key is set and the CLI is found.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        cache_dir: Path | str | None = "./output/cache/llm",
        max_file_size: int = 100_000,
        requests_per_minute: int = 50,
    ):
        self.model = model
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.max_file_size = max_file_size
        self.requests_per_minute = requests_per_minute
        self._last_request_time = 0
        self.backend: str = "api"  # "api" or "cli"
        self.client = None

        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Resolve auth: try API key first, fall back to CLI
        import os
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

        # Skip OAuth tokens — they don't work with the Anthropic API
        if resolved_key and resolved_key.startswith("sk-ant-oat"):
            console.print("[dim]Skipping OAuth token (not supported by API); trying CLI...[/dim]")
            resolved_key = None

        if resolved_key:
            self.backend = "api"
            self.client = anthropic.Anthropic(api_key=resolved_key)
            console.print("[dim]Using Anthropic API key[/dim]")
        elif _claude_cli_available():
            self.backend = "cli"
            # Map full model IDs to CLI aliases
            self._cli_model = self._resolve_cli_model(model)
            console.print(f"[dim]Using Claude CLI (model: {self._cli_model})[/dim]")
        else:
            raise ValueError(
                "No API key found and 'claude' CLI not installed. "
                "Set ANTHROPIC_API_KEY or install Claude Code and run 'claude auth login'."
            )

    @staticmethod
    def _resolve_cli_model(model: str) -> str:
        """Map a full model ID to a claude CLI alias."""
        if "opus" in model:
            return "opus"
        if "haiku" in model:
            return "haiku"
        return "sonnet"  # default
    
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

        # Get response text from the appropriate backend
        try:
            text = self._call_claude(prompt)
        except Exception as e:
            return ExtractionResult(
                file_path=str_path, success=False, data=None,
                error=f"{type(e).__name__}: {e}",
            )

        if not text:
            return ExtractionResult(
                file_path=str_path, success=False, data=None,
                error="Empty response from Claude",
            )

        # Extract JSON from response — try multiple strategies
        data = self._extract_json(text)

        if data is not None:
            self._save_cache(cache_key, data)
            return ExtractionResult(
                file_path=str_path, success=True, data=data,
            )
        else:
            snippet = text[:200]
            return ExtractionResult(
                file_path=str_path, success=False, data=None,
                error=f"Could not parse JSON from response: {snippet}",
            )

    def _call_claude(self, prompt: str, timeout: int = 120) -> str:
        """Send prompt to Claude and return the response text."""
        if self.backend == "cli":
            return self._call_via_cli(prompt, timeout=timeout)
        return self._call_via_api(prompt)

    def _call_via_api(self, prompt: str) -> str:
        """Call Claude via the Anthropic SDK."""
        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        if not message.content:
            return ""
        return message.content[0].text

    def _call_via_cli(self, prompt: str, timeout: int = 120) -> str:
        """Call Claude via the local ``claude`` CLI.

        Uses ``claude -p --output-format json --model <alias>`` which
        leverages the CLI's own OAuth session — no API key needed.
        """
        import subprocess

        result = subprocess.run(
            [
                "claude", "-p",
                "--output-format", "json",
                "--model", self._cli_model,
                "--no-session-persistence",
            ],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            raise RuntimeError(f"claude CLI exited {result.returncode}: {result.stderr[:200]}")

        # --output-format json wraps the response in a JSON envelope
        try:
            envelope = json.loads(result.stdout)
            # The envelope has a "result" field with the text
            return envelope.get("result", result.stdout)
        except json.JSONDecodeError:
            # If not valid JSON envelope, the stdout IS the text
            return result.stdout

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        """Extract a JSON object from Claude's response text."""
        # Strategy 1: JSON inside ```json ... ``` code block
        code_block = re.search(r'```(?:json)?\s*(\{.*\})\s*```', text, re.DOTALL)
        if code_block:
            try:
                return json.loads(code_block.group(1))
            except json.JSONDecodeError:
                pass

        # Strategy 2: Find the outermost { ... } by brace matching
        depth = 0
        start = None
        for i, ch in enumerate(text):
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start is not None:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        pass
                    break

        # Strategy 3: Last resort — first { to last }
        json_start = text.find("{")
        json_end = text.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            try:
                return json.loads(text[json_start:json_end])
            except json.JSONDecodeError:
                pass

        return None

    def generate_repo_context(self, manifest) -> tuple[str, dict]:
        """Generate holistic context.md for a repository.

        Returns (context_markdown, structured_metadata).
        """
        from .repo_prep import RepoManifest

        # Build tier content strings
        tier1_content = ""
        for f in manifest.tier1_files:
            tier1_content += f"\n### {f['path']} ({f['language']})\n```{f['language']}\n{f['content']}\n```\n"

        tier2_content = ""
        for f in manifest.tier2_files:
            tier2_content += f"\n### {f['path']} ({f['language']})\n```{f['language']}\n{f['signatures']}\n```\n"

        tier3_listing = "\n".join(f"- {p}" for p in manifest.tier3_files) or "None"

        prompt = CONTEXT_GENERATION_PROMPT.format(
            repo_name=manifest.repo_name,
            file_tree=manifest.file_tree,
            tier1_content=tier1_content or "No key files found.",
            tier2_content=tier2_content or "No additional source files.",
            tier3_listing=tier3_listing,
        )

        # Check repo-level cache
        cache_key = self._get_repo_cache_key(manifest)
        cached = self._get_repo_cached(cache_key)
        if cached:
            return cached["context_markdown"], cached["metadata"]

        # Rate limit
        self._rate_limit()

        # Call LLM with extended timeout for repo-level analysis
        text = self._call_claude(prompt, timeout=300)

        # Parse response: split markdown from metadata
        context_md, metadata = self._parse_context_response(text, manifest.repo_name)

        # Cache
        self._save_repo_cache(cache_key, {
            "context_markdown": context_md,
            "metadata": metadata,
            "repo_name": manifest.repo_name,
        })

        return context_md, metadata

    def _get_repo_cache_key(self, manifest) -> str:
        """Generate cache key for repo-level context."""
        h = hashlib.sha256()
        h.update(manifest.file_tree.encode())
        for f in manifest.tier1_files:
            h.update(f["content"].encode())
        for f in manifest.tier2_files:
            h.update(f["signatures"].encode())
        h.update(self.model.encode())
        return h.hexdigest()[:20]

    def _get_repo_cached(self, cache_key: str) -> dict | None:
        if not self.cache_dir:
            return None
        cache_file = self.cache_dir / "repo" / f"{cache_key}.json"
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text())
            except Exception:
                return None
        return None

    def _save_repo_cache(self, cache_key: str, data: dict) -> None:
        if not self.cache_dir:
            return
        repo_cache_dir = self.cache_dir / "repo"
        repo_cache_dir.mkdir(parents=True, exist_ok=True)
        (repo_cache_dir / f"{cache_key}.json").write_text(json.dumps(data, indent=2))

    @staticmethod
    def _parse_context_response(text: str, repo_name: str) -> tuple[str, dict]:
        """Split LLM response into context markdown and structured metadata."""
        # Try to split on ---METADATA--- marker
        marker = "---METADATA---"
        if marker in text:
            parts = text.split(marker, 1)
            context_md = parts[0].strip()
            metadata_text = parts[1].strip()
        else:
            # Fallback: try to find the last JSON block
            context_md = text
            metadata_text = ""

        # Parse metadata JSON
        metadata = {"purpose_summary": "", "domain": "", "when_to_use": [], "data_ownership": [], "service_dependencies": []}
        if metadata_text:
            extracted = LLMExtractor._extract_json(metadata_text)
            if extracted:
                metadata = extracted

        # If no marker found but there's a JSON block at the end, try to extract it
        if not metadata_text:
            extracted = LLMExtractor._extract_json(text)
            if extracted and "purpose_summary" in extracted:
                metadata = extracted
                # Remove the JSON from the markdown
                json_start = text.rfind("{")
                if json_start > 0:
                    # Find the start of the JSON section (look for ```json before it)
                    pre = text[:json_start]
                    code_marker = pre.rfind("```")
                    if code_marker > 0:
                        context_md = text[:code_marker].strip()
                    else:
                        context_md = pre.strip()

        return context_md, metadata

    def generate_semantic_layer(
        self,
        context_markdown: str,
        schemas: list[dict],
        apis: list[dict],
        services: list[dict],
        repo_name: str,
    ) -> dict:
        """Generate semantic enrichment for a repository.

        Takes the already-generated context markdown and structural metadata,
        returns semantic annotations (entity descriptions, field descriptions,
        query recipes, business glossary).
        """
        # Build compact JSON of structural metadata
        schemas_json = json.dumps([{
            "name": s.get("name"),
            "type": s.get("type"),
            "fields": [f.get("name") for f in s.get("fields", [])],
            "relationships": s.get("relationships", []),
        } for s in schemas], indent=2)

        apis_json = json.dumps([{
            "method": a.get("method"),
            "path": a.get("path"),
            "handler": a.get("handler"),
            "params": a.get("params", []),
        } for a in apis], indent=2)

        services_json = json.dumps([{
            "name": s.get("name"),
            "type": s.get("type"),
            "methods": [m.get("name") for m in s.get("methods", [])],
            "data_accessed": s.get("data_accessed", []),
        } for s in services], indent=2)

        prompt = SEMANTIC_ENRICHMENT_PROMPT.format(
            repo_name=repo_name,
            context_markdown=context_markdown,
            schemas_json=schemas_json,
            apis_json=apis_json,
            services_json=services_json,
        )

        # Check cache
        cache_key = self._get_semantic_cache_key(context_markdown, schemas_json, apis_json)
        cached = self._get_semantic_cached(cache_key)
        if cached:
            return cached

        self._rate_limit()
        text = self._call_claude(prompt, timeout=300)
        data = self._extract_json(text)

        if data:
            self._save_semantic_cache(cache_key, data)

        return data or {}

    def _get_semantic_cache_key(self, context_md: str, schemas_json: str, apis_json: str) -> str:
        h = hashlib.sha256()
        h.update(context_md.encode())
        h.update(schemas_json.encode())
        h.update(apis_json.encode())
        h.update(self.model.encode())
        return h.hexdigest()[:20]

    def _get_semantic_cached(self, cache_key: str) -> dict | None:
        if not self.cache_dir:
            return None
        cache_file = self.cache_dir / "semantic" / f"{cache_key}.json"
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text())
            except Exception:
                return None
        return None

    def _save_semantic_cache(self, cache_key: str, data: dict) -> None:
        if not self.cache_dir:
            return
        semantic_cache_dir = self.cache_dir / "semantic"
        semantic_cache_dir.mkdir(parents=True, exist_ok=True)
        (semantic_cache_dir / f"{cache_key}.json").write_text(json.dumps(data, indent=2))

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
                description=schema.get("description"),
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
        """Analyze a repository using holistic LLM context generation."""
        from .repo_prep import RepoFilePreparator
        from ..analyzers.base import RepoContext
        from datetime import datetime

        repo_name = repo_path.name
        result = AnalysisResult(repo_path=str(repo_path), repo_name=repo_name)

        # Prepare repo manifest
        preparator = RepoFilePreparator(skip_dirs=self.skip_dirs)
        manifest = preparator.prepare(repo_path)
        result.file_count = manifest.total_files

        if manifest.total_files == 0:
            console.print(f"  [yellow]![/yellow] {repo_name}: no source files found")
            return result

        console.print(f"  Prepared {manifest.total_files} files ({len(manifest.tier1_files)} key, {len(manifest.tier2_files)} signatures, {len(manifest.tier3_files)} listed)")

        try:
            context_md, metadata = self.extractor.generate_repo_context(manifest)

            result.context = RepoContext(
                repo_name=repo_name,
                repo_path=str(repo_path),
                context_markdown=context_md,
                purpose=metadata.get("purpose_summary", ""),
                domain=metadata.get("domain", ""),
                when_to_use=metadata.get("when_to_use", []),
                data_ownership=metadata.get("data_ownership", []),
                service_dependencies=metadata.get("service_dependencies", []),
                generated_at=datetime.utcnow().isoformat(),
                model=self.extractor.model,
                file_count=manifest.total_files,
            )

            console.print(f"  [green]✓[/green] {repo_name}: context generated ({metadata.get('domain', 'unknown')} domain)")

        except Exception as e:
            result.errors.append(f"Context generation failed: {e}")
            console.print(f"  [red]✗[/red] {repo_name}: {e}")

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
        # Directory analysis — holistic context generation
        analyzer = LLMAnalyzer(extractor=extractor)
        result = analyzer.analyze_repository(path)

        console.print(f"\n[bold]Analysis Complete[/bold]")
        console.print(f"  Files analyzed: {result.file_count}")
        console.print(f"  Errors: {len(result.errors)}")

        if result.context:
            console.print(f"\n[bold]--- context.md ---[/bold]\n")
            print(result.context.context_markdown)
            console.print(f"\n[bold]--- Metadata ---[/bold]")
            console.print(f"  Purpose: {result.context.purpose}")
            console.print(f"  Domain: {result.context.domain}")
            console.print(f"  When to use: {result.context.when_to_use}")
            console.print(f"  Data ownership: {len(result.context.data_ownership)} entities")
            console.print(f"  Dependencies: {len(result.context.service_dependencies)} services")
        else:
            console.print(f"\n[yellow]No context generated.[/yellow]")

        if args.output:
            from dataclasses import asdict
            Path(args.output).write_text(json.dumps(asdict(result), indent=2, default=str))
            console.print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()
