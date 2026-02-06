"""Go code analyzer."""

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


class GoAnalyzer(Analyzer):
    """Analyzer for Go source files."""
    
    extensions = [".go", ".mod"]
    language = "go"
    
    # Struct patterns
    STRUCT_PATTERN = re.compile(
        r'type\s+(\w+)\s+struct\s*\{([^}]+)\}',
        re.MULTILINE | re.DOTALL
    )
    
    # Field with tags pattern
    FIELD_PATTERN = re.compile(
        r'(\w+)\s+(\S+)\s*(?:`([^`]+)`)?',
        re.MULTILINE
    )
    
    # Interface pattern
    INTERFACE_PATTERN = re.compile(
        r'type\s+(\w+)\s+interface\s*\{([^}]+)\}',
        re.MULTILINE | re.DOTALL
    )
    
    # HTTP handler patterns
    HANDLER_PATTERN = re.compile(
        r'(?:HandleFunc|Handle)\s*\(\s*["\']([^"\']+)["\']',
        re.MULTILINE
    )
    
    # Gin/Echo/Chi route patterns
    ROUTE_PATTERN = re.compile(
        r'\.(GET|POST|PUT|DELETE|PATCH)\s*\(\s*["\']([^"\']+)["\']',
        re.MULTILINE
    )
    
    def analyze_file(self, file_path: Path, content: str) -> AnalysisResult:
        result = AnalysisResult(
            repo_path=str(file_path.parent),
            repo_name=file_path.parent.name,
        )
        
        rel_path = str(file_path)
        
        if file_path.suffix == ".mod":
            result.dependencies.extend(self._parse_go_mod(content, rel_path))
            return result
        
        # Extract structs
        for match in self.STRUCT_PATTERN.finditer(content):
            struct_name = match.group(1)
            body = match.group(2)
            
            fields = self._parse_struct_fields(body)
            
            # Check if it's a model (has db/gorm tags)
            is_model = any(
                'gorm:' in f.get('tags', '') or 'db:' in f.get('tags', '')
                for f in fields
            )
            
            result.schemas.append(SchemaInfo(
                name=struct_name,
                type="model" if is_model else "type",
                source_file=rel_path,
                fields=fields,
                relationships=self._extract_relationships(fields),
                raw_definition=match.group(0),
            ))
        
        # Extract interfaces (for understanding contracts)
        for match in self.INTERFACE_PATTERN.finditer(content):
            interface_name = match.group(1)
            body = match.group(2)
            
            methods = self._parse_interface_methods(body)
            
            result.business_logic.append(BusinessLogicInfo(
                name=interface_name,
                type="interface",
                source_file=rel_path,
                description=None,
                methods=methods,
                dependencies=[],
                data_accessed=[],
            ))
        
        # Extract HTTP routes
        result.apis.extend(self._extract_routes(content, rel_path))
        
        # Look for service structs and their methods
        result.business_logic.extend(
            self._extract_services(content, rel_path)
        )
        
        return result
    
    def _parse_struct_fields(self, body: str) -> list[dict]:
        """Parse struct field definitions."""
        fields = []
        
        for line in body.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            
            match = self.FIELD_PATTERN.match(line)
            if match:
                name = match.group(1)
                field_type = match.group(2)
                tags = match.group(3) or ""
                
                constraints = []
                
                # Parse common tags
                if 'primaryKey' in tags or 'primary_key' in tags:
                    constraints.append("primary_key")
                if 'not null' in tags.lower():
                    constraints.append("not_null")
                if 'unique' in tags.lower():
                    constraints.append("unique")
                
                # Extract JSON name
                json_match = re.search(r'json:"([^"]+)"', tags)
                json_name = json_match.group(1).split(',')[0] if json_match else None
                
                fields.append({
                    "name": name,
                    "type": field_type,
                    "constraints": constraints,
                    "tags": tags,
                    "json_name": json_name,
                })
        
        return fields
    
    def _extract_relationships(self, fields: list[dict]) -> list[dict]:
        """Extract relationships from struct fields."""
        relationships = []
        
        for field in fields:
            field_type = field.get("type", "")
            
            # Pointer or slice to another struct
            if field_type.startswith("*") or field_type.startswith("[]"):
                target = field_type.lstrip("*[]")
                if target[0].isupper():  # Likely a struct reference
                    rel_type = "has_many" if "[]" in field_type else "belongs_to"
                    relationships.append({
                        "type": rel_type,
                        "target": target,
                        "field": field["name"],
                    })
        
        return relationships
    
    def _parse_interface_methods(self, body: str) -> list[dict]:
        """Parse interface method signatures."""
        methods = []
        
        for line in body.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            
            # Match method signature: MethodName(params) returns
            match = re.match(r'(\w+)\s*\(([^)]*)\)\s*(.*)', line)
            if match:
                methods.append({
                    "name": match.group(1),
                    "params": match.group(2),
                    "returns": match.group(3).strip(),
                })
        
        return methods
    
    def _extract_routes(self, content: str, file_path: str) -> list[APIInfo]:
        """Extract HTTP route definitions."""
        routes = []
        
        # Standard http package
        for match in self.HANDLER_PATTERN.finditer(content):
            routes.append(APIInfo(
                path=match.group(1),
                method="ANY",
                source_file=file_path,
                handler="",
                params=[],
                request_body=None,
                response=None,
                description=None,
            ))
        
        # Framework routes (Gin, Echo, Chi, etc.)
        for match in self.ROUTE_PATTERN.finditer(content):
            routes.append(APIInfo(
                path=match.group(2),
                method=match.group(1),
                source_file=file_path,
                handler="",
                params=[],
                request_body=None,
                response=None,
                description=None,
            ))
        
        return routes
    
    def _extract_services(self, content: str, file_path: str) -> list[BusinessLogicInfo]:
        """Extract service-like structs with their methods."""
        services = []
        
        # Find structs ending in Service, Handler, Controller, etc.
        service_pattern = re.compile(
            r'type\s+(\w+(?:Service|Handler|Controller|Manager|Repository))\s+struct',
            re.MULTILINE
        )
        
        for match in service_pattern.finditer(content):
            service_name = match.group(1)
            
            # Find methods on this struct
            methods = self._find_receiver_methods(content, service_name)
            
            # Find dependencies (struct fields)
            deps = self._find_struct_deps(content, service_name)
            
            if methods:
                services.append(BusinessLogicInfo(
                    name=service_name,
                    type="service",
                    source_file=file_path,
                    description=None,
                    methods=methods,
                    dependencies=deps,
                    data_accessed=[],
                ))
        
        return services
    
    def _find_receiver_methods(self, content: str, struct_name: str) -> list[dict]:
        """Find methods with a receiver of the given struct type."""
        methods = []
        
        # Match: func (s *StructName) MethodName(params) returns
        pattern = re.compile(
            rf'func\s+\(\w+\s+\*?{struct_name}\)\s+(\w+)\s*\(([^)]*)\)\s*([^{{]*)',
            re.MULTILINE
        )
        
        for match in pattern.finditer(content):
            if not match.group(1).startswith("_"):  # Skip private methods
                methods.append({
                    "name": match.group(1),
                    "params": match.group(2),
                    "returns": match.group(3).strip(),
                })
        
        return methods
    
    def _find_struct_deps(self, content: str, struct_name: str) -> list[str]:
        """Find dependencies from struct fields."""
        deps = []
        
        # Find the struct definition
        pattern = re.compile(
            rf'type\s+{struct_name}\s+struct\s*\{{([^}}]+)\}}',
            re.MULTILINE | re.DOTALL
        )
        
        match = pattern.search(content)
        if match:
            body = match.group(1)
            for line in body.splitlines():
                line = line.strip()
                if not line:
                    continue
                
                # Look for interface or pointer types
                field_match = re.match(r'\w+\s+(\*?\w+)', line)
                if field_match:
                    field_type = field_match.group(1).lstrip("*")
                    if field_type[0].isupper():  # Exported type
                        deps.append(field_type)
        
        return deps
    
    def _parse_go_mod(self, content: str, file_path: str) -> list[DependencyInfo]:
        """Parse go.mod file for dependencies."""
        deps = []
        
        in_require = False
        for line in content.splitlines():
            line = line.strip()
            
            if line.startswith("require ("):
                in_require = True
                continue
            elif line == ")":
                in_require = False
                continue
            
            if in_require or line.startswith("require "):
                # Parse: module/path v1.2.3
                match = re.match(r'(?:require\s+)?(\S+)\s+(v\S+)', line)
                if match:
                    deps.append(DependencyInfo(
                        name=match.group(1),
                        version=match.group(2),
                        type="runtime",
                        source_file=file_path,
                        ecosystem="go",
                    ))
        
        return deps
