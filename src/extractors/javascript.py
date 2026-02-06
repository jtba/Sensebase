"""JavaScript/TypeScript code analyzer."""

import json
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


class JavaScriptAnalyzer(Analyzer):
    """Analyzer for JavaScript and TypeScript files."""
    
    extensions = [".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"]
    language = "javascript"
    
    # TypeScript interface/type patterns
    INTERFACE_PATTERN = re.compile(
        r'(?:export\s+)?interface\s+(\w+)(?:<[^>]+>)?\s*(?:extends\s+[^{]+)?\s*\{([^}]+)\}',
        re.MULTILINE | re.DOTALL
    )
    
    TYPE_PATTERN = re.compile(
        r'(?:export\s+)?type\s+(\w+)(?:<[^>]+>)?\s*=\s*\{([^}]+)\}',
        re.MULTILINE | re.DOTALL
    )
    
    # Class patterns
    CLASS_PATTERN = re.compile(
        r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?\s*\{',
        re.MULTILINE
    )
    
    # Express/Fastify/Koa route patterns
    ROUTE_PATTERNS = [
        re.compile(r'app\.(get|post|put|delete|patch)\s*\(\s*[\'"`]([^\'"]+)[\'"`]', re.MULTILINE),
        re.compile(r'router\.(get|post|put|delete|patch)\s*\(\s*[\'"`]([^\'"]+)[\'"`]', re.MULTILINE),
    ]
    
    # Mongoose/Sequelize model patterns
    MONGOOSE_PATTERN = re.compile(
        r'(?:const|let|var)\s+(\w+)Schema\s*=\s*new\s+(?:mongoose\.)?Schema\s*\(\s*\{([^}]+)\}',
        re.MULTILINE | re.DOTALL
    )
    
    SEQUELIZE_PATTERN = re.compile(
        r'(?:class\s+(\w+)\s+extends\s+Model|(\w+)\.init\s*\(\s*\{([^}]+)\})',
        re.MULTILINE | re.DOTALL
    )
    
    # Prisma-like patterns
    PRISMA_PATTERN = re.compile(
        r'model\s+(\w+)\s*\{([^}]+)\}',
        re.MULTILINE | re.DOTALL
    )
    
    def analyze_file(self, file_path: Path, content: str) -> AnalysisResult:
        result = AnalysisResult(
            repo_path=str(file_path.parent),
            repo_name=file_path.parent.name,
        )
        
        rel_path = str(file_path)
        
        # Handle package.json
        if file_path.name == "package.json":
            result.dependencies.extend(self._parse_package_json(content, rel_path))
            return result
        
        # Handle Prisma schema
        if file_path.suffix == ".prisma":
            result.schemas.extend(self._parse_prisma_schema(content, rel_path))
            return result
        
        # Extract TypeScript interfaces
        for match in self.INTERFACE_PATTERN.finditer(content):
            name = match.group(1)
            body = match.group(2)
            
            fields = self._parse_ts_fields(body)
            
            result.schemas.append(SchemaInfo(
                name=name,
                type="interface",
                source_file=rel_path,
                fields=fields,
                relationships=[],
                raw_definition=match.group(0),
            ))
        
        # Extract TypeScript type aliases (object types)
        for match in self.TYPE_PATTERN.finditer(content):
            name = match.group(1)
            body = match.group(2)
            
            fields = self._parse_ts_fields(body)
            
            result.schemas.append(SchemaInfo(
                name=name,
                type="type",
                source_file=rel_path,
                fields=fields,
                relationships=[],
                raw_definition=match.group(0),
            ))
        
        # Extract Mongoose schemas
        for match in self.MONGOOSE_PATTERN.finditer(content):
            name = match.group(1)
            body = match.group(2)
            
            fields = self._parse_mongoose_fields(body)
            
            result.schemas.append(SchemaInfo(
                name=name,
                type="model",
                source_file=rel_path,
                fields=fields,
                relationships=[],
                raw_definition=match.group(0),
            ))
        
        # Extract routes
        for pattern in self.ROUTE_PATTERNS:
            for match in pattern.finditer(content):
                method = match.group(1).upper()
                path = match.group(2)
                
                result.apis.append(APIInfo(
                    path=path,
                    method=method,
                    source_file=rel_path,
                    handler="",
                    params=[],
                    request_body=None,
                    response=None,
                    description=None,
                ))
        
        # Extract service classes
        result.business_logic.extend(
            self._extract_services(content, rel_path)
        )
        
        return result
    
    def _parse_ts_fields(self, body: str) -> list[dict]:
        """Parse TypeScript interface/type fields."""
        fields = []
        
        # Match: fieldName?: Type; or fieldName: Type;
        field_pattern = re.compile(
            r'(\w+)(\?)?:\s*([^;,\n]+)',
            re.MULTILINE
        )
        
        for match in field_pattern.finditer(body):
            name = match.group(1)
            optional = match.group(2) is not None
            field_type = match.group(3).strip()
            
            constraints = []
            if not optional:
                constraints.append("required")
            
            fields.append({
                "name": name,
                "type": field_type,
                "constraints": constraints,
                "optional": optional,
            })
        
        return fields
    
    def _parse_mongoose_fields(self, body: str) -> list[dict]:
        """Parse Mongoose schema fields."""
        fields = []
        
        # Simple parsing - match field: { type: X, ... }
        field_pattern = re.compile(
            r'(\w+)\s*:\s*(?:\{\s*type\s*:\s*(\w+)|(\w+))',
            re.MULTILINE
        )
        
        for match in field_pattern.finditer(body):
            name = match.group(1)
            field_type = match.group(2) or match.group(3)
            
            constraints = []
            
            # Check for required in the field definition
            field_def_match = re.search(
                rf'{name}\s*:\s*\{{[^}}]*required\s*:\s*true',
                body
            )
            if field_def_match:
                constraints.append("required")
            
            unique_match = re.search(
                rf'{name}\s*:\s*\{{[^}}]*unique\s*:\s*true',
                body
            )
            if unique_match:
                constraints.append("unique")
            
            fields.append({
                "name": name,
                "type": field_type or "Mixed",
                "constraints": constraints,
            })
        
        return fields
    
    def _parse_prisma_schema(self, content: str, file_path: str) -> list[SchemaInfo]:
        """Parse Prisma schema file."""
        schemas = []
        
        for match in self.PRISMA_PATTERN.finditer(content):
            name = match.group(1)
            body = match.group(2)
            
            fields = []
            relationships = []
            
            for line in body.strip().splitlines():
                line = line.strip()
                if not line or line.startswith("//") or line.startswith("@@"):
                    continue
                
                # Parse field: name Type @attributes
                field_match = re.match(r'(\w+)\s+(\w+)(\[\])?\??(\s+.+)?', line)
                if field_match:
                    field_name = field_match.group(1)
                    field_type = field_match.group(2)
                    is_array = field_match.group(3) is not None
                    attrs = field_match.group(4) or ""
                    
                    constraints = []
                    if "@id" in attrs:
                        constraints.append("primary_key")
                    if "@unique" in attrs:
                        constraints.append("unique")
                    if "?" not in line:
                        constraints.append("required")
                    
                    # Check for relations
                    if "@relation" in attrs or field_type[0].isupper():
                        relationships.append({
                            "type": "has_many" if is_array else "belongs_to",
                            "target": field_type,
                            "field": field_name,
                        })
                    else:
                        fields.append({
                            "name": field_name,
                            "type": field_type,
                            "constraints": constraints,
                        })
            
            schemas.append(SchemaInfo(
                name=name,
                type="model",
                source_file=file_path,
                fields=fields,
                relationships=relationships,
                raw_definition=match.group(0),
            ))
        
        return schemas
    
    def _extract_services(self, content: str, file_path: str) -> list[BusinessLogicInfo]:
        """Extract service-like classes."""
        services = []
        
        for match in self.CLASS_PATTERN.finditer(content):
            class_name = match.group(1)
            
            # Check if it looks like a service
            if not any(
                suffix in class_name
                for suffix in ['Service', 'Handler', 'Controller', 'Manager', 'Repository']
            ):
                continue
            
            # Extract methods
            methods = self._extract_class_methods(content, match.start())
            
            # Extract constructor dependencies
            deps = self._extract_constructor_deps(content, match.start())
            
            if methods:
                services.append(BusinessLogicInfo(
                    name=class_name,
                    type="service",
                    source_file=file_path,
                    description=None,
                    methods=methods,
                    dependencies=deps,
                    data_accessed=[],
                ))
        
        return services
    
    def _extract_class_methods(self, content: str, class_start: int) -> list[dict]:
        """Extract methods from a class."""
        methods = []
        
        # Find class body
        brace_count = 0
        in_class = False
        end = class_start
        
        for i, char in enumerate(content[class_start:], class_start):
            if char == '{':
                brace_count += 1
                in_class = True
            elif char == '}':
                brace_count -= 1
                if in_class and brace_count == 0:
                    end = i + 1
                    break
        
        class_body = content[class_start:end]
        
        # Match methods: async? methodName(params): ReturnType
        method_pattern = re.compile(
            r'(?:async\s+)?(\w+)\s*\(([^)]*)\)(?:\s*:\s*([^{]+))?\s*\{',
            re.MULTILINE
        )
        
        for match in method_pattern.finditer(class_body):
            name = match.group(1)
            if name not in ('constructor', 'if', 'for', 'while', 'switch'):
                methods.append({
                    "name": name,
                    "params": match.group(2),
                    "returns": match.group(3).strip() if match.group(3) else None,
                })
        
        return methods
    
    def _extract_constructor_deps(self, content: str, class_start: int) -> list[str]:
        """Extract dependencies from constructor."""
        deps = []
        
        # Find constructor
        ctor_match = re.search(
            r'constructor\s*\(([^)]+)\)',
            content[class_start:class_start + 2000]
        )
        
        if ctor_match:
            params = ctor_match.group(1)
            
            # Match: private/public name: Type
            dep_pattern = re.compile(r'(?:private|public)\s+\w+\s*:\s*(\w+)')
            for match in dep_pattern.finditer(params):
                deps.append(match.group(1))
        
        return deps
    
    def _parse_package_json(self, content: str, file_path: str) -> list[DependencyInfo]:
        """Parse package.json for dependencies."""
        deps = []
        
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return deps
        
        for dep_type, section in [
            ("runtime", "dependencies"),
            ("dev", "devDependencies"),
            ("peer", "peerDependencies"),
            ("optional", "optionalDependencies"),
        ]:
            if section in data:
                for name, version in data[section].items():
                    deps.append(DependencyInfo(
                        name=name,
                        version=version,
                        type=dep_type,
                        source_file=file_path,
                        ecosystem="npm",
                    ))
        
        return deps
