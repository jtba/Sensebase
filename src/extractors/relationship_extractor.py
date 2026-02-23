"""Cross-repo relationship extraction using LLM."""

import json
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console

from ..analyzers.base import RepoContext

console = Console()

RELATIONSHIP_PROMPT = """You are analyzing multiple code repositories that work together as a system.
Your goal is to understand how these services relate, when to use one vs another, and where data lives.

## Services

{service_summaries}

---

Based on the above, generate a JSON document describing the relationships between these services.
Be specific and ground everything in the actual service context provided.

```json
{{
  "service_map": [
    {{
      "service": "service name",
      "purpose": "one sentence purpose",
      "domain": "business domain",
      "data_owned": ["list of entities this service is source of truth for"],
      "use_when": ["specific condition when you should call this service"],
      "instead_of": [
        {{"service": "other service name", "reason": "why you'd use this one instead"}}
      ]
    }}
  ],
  "data_routing": [
    {{
      "entity": "data entity name",
      "source_of_truth": "service name that owns this data",
      "also_available_in": [
        {{"service": "service name", "freshness": "real-time|cached|eventual", "notes": "any caveats"}}
      ],
      "query_this_when": "condition for when to query this entity from the source"
    }}
  ],
  "service_chains": [
    {{
      "name": "descriptive name for this flow",
      "description": "what business process this represents",
      "steps": [
        {{"service": "service name", "action": "what happens here", "data_passed": "what data flows to next step"}}
      ]
    }}
  ]
}}
```

Only include relationships you can confidently identify from the service contexts provided.
If there are few services or limited information, it's okay to have shorter lists.
"""


@dataclass
class RelationshipResult:
    """Cross-repo relationship analysis result."""
    service_map: list[dict[str, Any]] = field(default_factory=list)
    data_routing: list[dict[str, Any]] = field(default_factory=list)
    service_chains: list[dict[str, Any]] = field(default_factory=list)
    generated_at: str = ""
    model: str = ""
    repo_count: int = 0


class RelationshipExtractor:
    """Generate cross-repo relationships using LLM."""

    def __init__(self, extractor=None):
        if extractor is None:
            from .llm_extractor import LLMExtractor
            extractor = LLMExtractor()
        self.extractor = extractor

    def generate_relationships(self, contexts: list[RepoContext]) -> RelationshipResult:
        """Generate cross-repo relationship map from all repo contexts."""
        from datetime import datetime

        if not contexts:
            console.print("[yellow]No repo contexts provided for relationship extraction[/yellow]")
            return RelationshipResult()

        if len(contexts) == 1:
            console.print("[yellow]Only one repo context — generating single-service relationships[/yellow]")

        # Build compact summaries for each service
        summaries = []
        for ctx in contexts:
            summary_parts = [
                f"### {ctx.repo_name}",
                f"**Purpose:** {ctx.purpose}" if ctx.purpose else "",
                f"**Domain:** {ctx.domain}" if ctx.domain else "",
            ]

            if ctx.when_to_use:
                summary_parts.append("**When to use:**")
                for condition in ctx.when_to_use:
                    summary_parts.append(f"- {condition}")

            if ctx.data_ownership:
                summary_parts.append("**Data ownership:**")
                for entity in ctx.data_ownership:
                    name = entity.get("entity", "unknown")
                    desc = entity.get("description", "")
                    sot = " (source of truth)" if entity.get("is_source_of_truth") else ""
                    summary_parts.append(f"- {name}: {desc}{sot}")

            if ctx.service_dependencies:
                summary_parts.append("**Dependencies:**")
                for dep in ctx.service_dependencies:
                    svc = dep.get("service", "unknown")
                    reason = dep.get("reason", "")
                    summary_parts.append(f"- {svc}: {reason}")

            summaries.append("\n".join(p for p in summary_parts if p))

        service_summaries = "\n\n".join(summaries)
        prompt = RELATIONSHIP_PROMPT.format(service_summaries=service_summaries)

        console.print(f"[blue]Generating cross-repo relationships for {len(contexts)} services...[/blue]")

        try:
            text = self.extractor._call_claude(prompt, timeout=300)
        except Exception as e:
            console.print(f"[red]Relationship extraction failed: {e}[/red]")
            return RelationshipResult()

        # Parse response JSON
        data = self.extractor._extract_json(text)
        if not data:
            console.print("[yellow]Could not parse relationship JSON from LLM response[/yellow]")
            return RelationshipResult()

        result = RelationshipResult(
            service_map=data.get("service_map", []),
            data_routing=data.get("data_routing", []),
            service_chains=data.get("service_chains", []),
            generated_at=datetime.utcnow().isoformat(),
            model=self.extractor.model,
            repo_count=len(contexts),
        )

        console.print(
            f"[green]\u2713[/green] Relationships: "
            f"{len(result.service_map)} services, "
            f"{len(result.data_routing)} data routes, "
            f"{len(result.service_chains)} chains"
        )

        return result
