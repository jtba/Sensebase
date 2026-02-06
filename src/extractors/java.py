"""Java code analyzer."""

import re
from pathlib import Path

from ..analyzers.base import (
    Analyzer,
    AnalysisResult,
    SchemaInfo,
    BusinessLogicInfo,
    APIInfo,
    DependencyInfo,
)


class JavaAnalyzer(Analyzer):
    """Analyzer for Java source files."""
    
    extensions = [".java"]
    language = "java"
    
    # Patterns for entity/model detection
    ENTITY_PATTERN = re.compile(
        r'@(?:Entity|Table|Document|Embeddable)\s*(?:\([^)]*\))?\s*'
        r'(?:public\s+)?class\s+(\w+)',
        re.MULTILINE
    )
    
    # Field patterns with JPA annotations
    FIELD_PATTERN = re.compile(
        r'(?:@(\w+)(?:\([^)]*\))?\s*)*'
        r'(?:private|protected|public)\s+'
        r'(\w+(?:<[^>]+>)?)\s+'
        r'(\w+)\s*(?:=|;)',
        re.MULTILINE
    )
    
    # Spring annotations
    SERVICE_PATTERN = re.compile(
        r'@(?:Service|Component|Repository|Controller|RestController)\s*'
        r'(?:\([^)]*\))?\s*(?:public\s+)?class\s+(\w+)',
        re.MULTILINE
    )
    
    # REST endpoint patterns
    ENDPOINT_PATTERN = re.compile(
        r'@(?:Get|Post|Put|Delete|Patch|Request)Mapping\s*'
        r'\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']',
        re.MULTILINE
    )
    
    METHOD_PATTERN = re.compile(
        r'(?:@\w+(?:\([^)]*\))?\s*)*'
        r'(?:public|protected|private)\s+'
        r'(\w+(?:<[^>]+>)?)\s+'
        r'(\w+)\s*\(([^)]*)\)',
        re.MULTILINE
    )
    
    def analyze_file(self, file_path: Path, content: str) -> AnalysisResult:
        result = AnalysisResult(
            repo_path=str(file_path.parent),
            repo_name=file_path.parent.name,
        )
        
        rel_path = str(file_path)
        
        # Extract entities/models
        for match in self.ENTITY_PATTERN.finditer(content):
            class_name = match.group(1)
            fields = self._extract_fields(content, match.start())
            
            result.schemas.append(SchemaInfo(
                name=class_name,
                type="entity",
                source_file=rel_path,
                fields=fields,
                relationships=self._extract_relationships(content, match.start()),
                raw_definition=self._extract_class_body(content, match.start()),
            ))
        
        # Extract services
        for match in self.SERVICE_PATTERN.finditer(content):
            class_name = match.group(1)
            methods = self._extract_methods(content, match.start())
            
            result.business_logic.append(BusinessLogicInfo(
                name=class_name,
                type="service",
                source_file=rel_path,
                description=self._extract_javadoc(content, match.start()),
                methods=methods,
                dependencies=self._extract_injections(content),
                data_accessed=self._extract_repository_calls(content),
            ))
        
        # Extract REST endpoints
        result.apis.extend(self._extract_endpoints(content, rel_path))
        
        # Check for pom.xml style dependencies
        if file_path.name == "pom.xml":
            result.dependencies.extend(self._parse_pom(content, rel_path))
        
        return result
    
    def _extract_fields(self, content: str, class_start: int) -> list[dict]:
        """Extract field definitions from a class."""
        fields = []
        class_body = self._extract_class_body(content, class_start)
        
        for match in self.FIELD_PATTERN.finditer(class_body):
            annotations = match.group(1) or ""
            field_type = match.group(2)
            field_name = match.group(3)
            
            constraints = []
            if "@NotNull" in content[match.start()-50:match.start()]:
                constraints.append("not_null")
            if "@Id" in content[match.start()-30:match.start()]:
                constraints.append("primary_key")
            
            fields.append({
                "name": field_name,
                "type": field_type,
                "constraints": constraints,
                "annotations": annotations,
            })
        
        return fields
    
    def _extract_relationships(self, content: str, class_start: int) -> list[dict]:
        """Extract JPA relationships."""
        relationships = []
        class_body = self._extract_class_body(content, class_start)
        
        rel_patterns = [
            (r'@OneToMany.*?(\w+)\s+(\w+)', 'one_to_many'),
            (r'@ManyToOne.*?(\w+)\s+(\w+)', 'many_to_one'),
            (r'@OneToOne.*?(\w+)\s+(\w+)', 'one_to_one'),
            (r'@ManyToMany.*?(\w+)\s+(\w+)', 'many_to_many'),
        ]
        
        for pattern, rel_type in rel_patterns:
            for match in re.finditer(pattern, class_body, re.DOTALL):
                relationships.append({
                    "type": rel_type,
                    "target": match.group(1),
                    "field": match.group(2),
                })
        
        return relationships
    
    def _extract_class_body(self, content: str, start: int) -> str:
        """Extract the body of a class starting from a position."""
        brace_count = 0
        in_class = False
        end = start
        
        for i, char in enumerate(content[start:], start):
            if char == '{':
                brace_count += 1
                in_class = True
            elif char == '}':
                brace_count -= 1
                if in_class and brace_count == 0:
                    end = i + 1
                    break
        
        return content[start:end]
    
    def _extract_methods(self, content: str, class_start: int) -> list[dict]:
        """Extract method definitions from a class."""
        methods = []
        class_body = self._extract_class_body(content, class_start)
        
        for match in self.METHOD_PATTERN.finditer(class_body):
            return_type = match.group(1)
            method_name = match.group(2)
            params = match.group(3)
            
            methods.append({
                "name": method_name,
                "return_type": return_type,
                "params": self._parse_params(params),
                "docstring": None,  # Could extract Javadoc
            })
        
        return methods
    
    def _parse_params(self, params_str: str) -> list[dict]:
        """Parse method parameters."""
        if not params_str.strip():
            return []
        
        params = []
        for param in params_str.split(','):
            param = param.strip()
            if param:
                parts = param.split()
                if len(parts) >= 2:
                    params.append({
                        "type": parts[-2],
                        "name": parts[-1],
                    })
        return params
    
    def _extract_javadoc(self, content: str, class_start: int) -> str | None:
        """Extract Javadoc comment before a class."""
        # Look backwards for /**
        search_start = max(0, class_start - 500)
        segment = content[search_start:class_start]
        
        match = re.search(r'/\*\*(.*?)\*/', segment, re.DOTALL)
        if match:
            doc = match.group(1)
            # Clean up the javadoc
            doc = re.sub(r'^\s*\*\s?', '', doc, flags=re.MULTILINE)
            return doc.strip()
        return None
    
    def _extract_injections(self, content: str) -> list[str]:
        """Extract @Autowired or constructor injected dependencies."""
        deps = []
        
        # @Autowired fields
        for match in re.finditer(r'@Autowired\s+(?:private\s+)?(\w+)', content):
            deps.append(match.group(1))
        
        # Constructor injection
        for match in re.finditer(r'private\s+final\s+(\w+)\s+\w+;', content):
            deps.append(match.group(1))
        
        return list(set(deps))
    
    def _extract_repository_calls(self, content: str) -> list[str]:
        """Extract repository method calls to infer data access."""
        entities = []
        
        for match in re.finditer(r'(\w+)Repository\.', content):
            entities.append(match.group(1))
        
        return list(set(entities))
    
    def _extract_endpoints(self, content: str, file_path: str) -> list[APIInfo]:
        """Extract REST API endpoints."""
        endpoints = []
        
        # Get class-level RequestMapping
        class_path = ""
        class_match = re.search(r'@RequestMapping\s*\(["\']([^"\']+)["\']', content)
        if class_match:
            class_path = class_match.group(1)
        
        method_map = {
            'GetMapping': 'GET',
            'PostMapping': 'POST',
            'PutMapping': 'PUT',
            'DeleteMapping': 'DELETE',
            'PatchMapping': 'PATCH',
        }
        
        for annotation, http_method in method_map.items():
            for match in re.finditer(
                rf'@{annotation}\s*\(\s*(?:value\s*=\s*)?["\']([^"\']*)["\']',
                content
            ):
                path = class_path + match.group(1)
                
                endpoints.append(APIInfo(
                    path=path,
                    method=http_method,
                    source_file=file_path,
                    handler=self._find_handler_name(content, match.end()),
                    params=[],
                    request_body=None,
                    response=None,
                    description=None,
                ))
        
        return endpoints
    
    def _find_handler_name(self, content: str, annotation_end: int) -> str:
        """Find the method name after an annotation."""
        match = re.search(r'public\s+\w+\s+(\w+)\s*\(', content[annotation_end:annotation_end+200])
        return match.group(1) if match else "unknown"
    
    def _parse_pom(self, content: str, file_path: str) -> list[DependencyInfo]:
        """Parse Maven pom.xml for dependencies."""
        deps = []
        
        for match in re.finditer(
            r'<dependency>\s*'
            r'<groupId>([^<]+)</groupId>\s*'
            r'<artifactId>([^<]+)</artifactId>\s*'
            r'(?:<version>([^<]+)</version>)?',
            content,
            re.DOTALL
        ):
            deps.append(DependencyInfo(
                name=f"{match.group(1)}:{match.group(2)}",
                version=match.group(3),
                type="runtime",
                source_file=file_path,
                ecosystem="maven",
            ))
        
        return deps
