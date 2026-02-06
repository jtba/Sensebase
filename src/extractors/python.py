"""Python code analyzer."""

import ast
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


class PythonAnalyzer(Analyzer):
    """Analyzer for Python source files."""
    
    extensions = [".py", ".pyi"]
    language = "python"
    
    # SQLAlchemy/Django model patterns
    MODEL_BASES = {
        'Base', 'Model', 'db.Model', 'models.Model', 'DeclarativeBase',
        'SQLModel', 'BaseModel',  # Pydantic
    }
    
    # Service/Handler patterns
    SERVICE_PATTERNS = [
        r'class\s+(\w+Service)',
        r'class\s+(\w+Handler)',
        r'class\s+(\w+Manager)',
        r'class\s+(\w+Controller)',
    ]
    
    def analyze_file(self, file_path: Path, content: str) -> AnalysisResult:
        result = AnalysisResult(
            repo_path=str(file_path.parent),
            repo_name=file_path.parent.name,
        )
        
        rel_path = str(file_path)
        
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            result.errors.append(f"Syntax error in {file_path}: {e}")
            return result
        
        # Analyze classes
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                self._analyze_class(node, content, rel_path, result)
            elif isinstance(node, ast.FunctionDef):
                # Check for route decorators (Flask/FastAPI)
                self._check_route(node, rel_path, result)
        
        # Check for requirements.txt style imports
        if file_path.name in ("requirements.txt", "pyproject.toml", "setup.py"):
            result.dependencies.extend(
                self._parse_dependencies(content, file_path.name, rel_path)
            )
        
        return result
    
    def _analyze_class(
        self,
        node: ast.ClassDef,
        content: str,
        file_path: str,
        result: AnalysisResult,
    ) -> None:
        """Analyze a class definition."""
        base_names = [self._get_name(base) for base in node.bases]
        
        # Check if it's a model/schema
        if any(base in self.MODEL_BASES for base in base_names):
            schema = self._extract_schema(node, content, file_path)
            if schema:
                result.schemas.append(schema)
        
        # Check if it's a Pydantic model
        if 'BaseModel' in base_names:
            schema = self._extract_pydantic_model(node, file_path)
            if schema:
                result.schemas.append(schema)
        
        # Check if it's a service/handler
        if any(
            re.match(pattern, f"class {node.name}")
            for pattern in self.SERVICE_PATTERNS
        ):
            logic = self._extract_business_logic(node, file_path)
            if logic:
                result.business_logic.append(logic)
    
    def _get_name(self, node: ast.expr) -> str:
        """Get the name from an AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        return ""
    
    def _extract_schema(
        self,
        node: ast.ClassDef,
        content: str,
        file_path: str,
    ) -> SchemaInfo | None:
        """Extract schema from SQLAlchemy/Django model."""
        fields = []
        relationships = []
        
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        field_info = self._parse_column(item.value)
                        if field_info:
                            field_info["name"] = target.id
                            fields.append(field_info)
            
            elif isinstance(item, ast.AnnAssign):
                if isinstance(item.target, ast.Name):
                    field_info = {
                        "name": item.target.id,
                        "type": self._get_annotation_type(item.annotation),
                        "constraints": [],
                    }
                    fields.append(field_info)
        
        # Check for relationship() calls
        for item in node.body:
            if isinstance(item, ast.Assign):
                if isinstance(item.value, ast.Call):
                    func_name = self._get_name(item.value.func)
                    if func_name == "relationship":
                        rel = self._parse_relationship(item)
                        if rel:
                            relationships.append(rel)
        
        if fields:
            return SchemaInfo(
                name=node.name,
                type="model",
                source_file=file_path,
                fields=fields,
                relationships=relationships,
                raw_definition=ast.get_source_segment(content, node),
            )
        return None
    
    def _parse_column(self, node: ast.expr) -> dict | None:
        """Parse SQLAlchemy Column definition."""
        if not isinstance(node, ast.Call):
            return None
        
        func_name = self._get_name(node.func)
        if func_name not in ("Column", "db.Column"):
            return None
        
        field_type = "unknown"
        constraints = []
        
        for arg in node.args:
            if isinstance(arg, ast.Call):
                field_type = self._get_name(arg.func)
            elif isinstance(arg, ast.Name):
                field_type = arg.id
        
        for keyword in node.keywords:
            if keyword.arg == "primary_key" and self._is_true(keyword.value):
                constraints.append("primary_key")
            elif keyword.arg == "nullable":
                if not self._is_true(keyword.value):
                    constraints.append("not_null")
            elif keyword.arg == "unique" and self._is_true(keyword.value):
                constraints.append("unique")
        
        return {"type": field_type, "constraints": constraints}
    
    def _is_true(self, node: ast.expr) -> bool:
        """Check if an AST node represents True."""
        return isinstance(node, ast.Constant) and node.value is True
    
    def _parse_relationship(self, item: ast.Assign) -> dict | None:
        """Parse SQLAlchemy relationship."""
        if not isinstance(item.value, ast.Call):
            return None
        
        target = None
        rel_type = "relationship"
        
        for arg in item.value.args:
            if isinstance(arg, ast.Constant):
                target = arg.value
        
        if target and isinstance(item.targets[0], ast.Name):
            return {
                "type": rel_type,
                "target": target,
                "field": item.targets[0].id,
            }
        return None
    
    def _get_annotation_type(self, node: ast.expr) -> str:
        """Get type from annotation."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Subscript):
            base = self._get_name(node.value)
            return f"{base}[...]"
        elif isinstance(node, ast.Constant):
            return str(node.value)
        return "unknown"
    
    def _extract_pydantic_model(
        self,
        node: ast.ClassDef,
        file_path: str,
    ) -> SchemaInfo | None:
        """Extract schema from Pydantic model."""
        fields = []
        
        for item in node.body:
            if isinstance(item, ast.AnnAssign):
                if isinstance(item.target, ast.Name):
                    field_info = {
                        "name": item.target.id,
                        "type": self._get_annotation_type(item.annotation),
                        "constraints": [],
                    }
                    
                    # Check for Field() with constraints
                    if item.value and isinstance(item.value, ast.Call):
                        field_info["constraints"] = self._parse_pydantic_field(item.value)
                    
                    fields.append(field_info)
        
        if fields:
            return SchemaInfo(
                name=node.name,
                type="interface",
                source_file=file_path,
                fields=fields,
                relationships=[],
            )
        return None
    
    def _parse_pydantic_field(self, node: ast.Call) -> list[str]:
        """Parse Pydantic Field() constraints."""
        constraints = []
        
        for keyword in node.keywords:
            if keyword.arg == "min_length":
                constraints.append(f"min_length={self._get_value(keyword.value)}")
            elif keyword.arg == "max_length":
                constraints.append(f"max_length={self._get_value(keyword.value)}")
            elif keyword.arg == "ge":
                constraints.append(f"ge={self._get_value(keyword.value)}")
            elif keyword.arg == "le":
                constraints.append(f"le={self._get_value(keyword.value)}")
        
        return constraints
    
    def _get_value(self, node: ast.expr) -> str:
        """Get constant value from AST."""
        if isinstance(node, ast.Constant):
            return str(node.value)
        return "?"
    
    def _extract_business_logic(
        self,
        node: ast.ClassDef,
        file_path: str,
    ) -> BusinessLogicInfo:
        """Extract business logic from service class."""
        methods = []
        dependencies = []
        
        # Find __init__ for dependencies
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                for arg in item.args.args[1:]:  # Skip self
                    if arg.annotation:
                        dependencies.append(self._get_annotation_type(arg.annotation))
        
        # Extract methods
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                methods.append({
                    "name": item.name,
                    "params": [
                        {"name": arg.arg, "type": self._get_annotation_type(arg.annotation) if arg.annotation else "Any"}
                        for arg in item.args.args[1:]
                    ],
                    "returns": self._get_annotation_type(item.returns) if item.returns else None,
                    "docstring": ast.get_docstring(item),
                })
        
        return BusinessLogicInfo(
            name=node.name,
            type="service",
            source_file=file_path,
            description=ast.get_docstring(node),
            methods=methods,
            dependencies=dependencies,
            data_accessed=[],
        )
    
    def _check_route(
        self,
        node: ast.FunctionDef,
        file_path: str,
        result: AnalysisResult,
    ) -> None:
        """Check for Flask/FastAPI route decorators."""
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                func_name = self._get_name(decorator.func)
                
                # FastAPI routes
                if func_name in ("app.get", "app.post", "app.put", "app.delete", "router.get", "router.post"):
                    method = func_name.split(".")[-1].upper()
                    path = ""
                    
                    if decorator.args and isinstance(decorator.args[0], ast.Constant):
                        path = decorator.args[0].value
                    
                    result.apis.append(APIInfo(
                        path=path,
                        method=method,
                        source_file=file_path,
                        handler=node.name,
                        params=[
                            {"name": arg.arg, "type": self._get_annotation_type(arg.annotation) if arg.annotation else "Any"}
                            for arg in node.args.args
                        ],
                        request_body=None,
                        response=None,
                        description=ast.get_docstring(node),
                    ))
                
                # Flask routes
                elif func_name == "app.route":
                    if decorator.args and isinstance(decorator.args[0], ast.Constant):
                        path = decorator.args[0].value
                        methods = ["GET"]
                        
                        for kw in decorator.keywords:
                            if kw.arg == "methods" and isinstance(kw.value, ast.List):
                                methods = [
                                    elt.value for elt in kw.value.elts
                                    if isinstance(elt, ast.Constant)
                                ]
                        
                        for method in methods:
                            result.apis.append(APIInfo(
                                path=path,
                                method=method,
                                source_file=file_path,
                                handler=node.name,
                                params=[],
                                request_body=None,
                                response=None,
                                description=ast.get_docstring(node),
                            ))
    
    def _parse_dependencies(
        self,
        content: str,
        filename: str,
        file_path: str,
    ) -> list[DependencyInfo]:
        """Parse Python dependency files."""
        deps = []
        
        if filename == "requirements.txt":
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    # Parse package==version or package>=version etc.
                    match = re.match(r'^([a-zA-Z0-9_-]+)(?:[<>=!]+(.+))?', line)
                    if match:
                        deps.append(DependencyInfo(
                            name=match.group(1),
                            version=match.group(2),
                            type="runtime",
                            source_file=file_path,
                            ecosystem="pip",
                        ))
        
        elif filename == "pyproject.toml":
            # Simple TOML parsing for dependencies
            in_deps = False
            for line in content.splitlines():
                if "dependencies" in line and "=" in line:
                    in_deps = True
                elif in_deps:
                    if line.strip().startswith("]"):
                        in_deps = False
                    else:
                        match = re.search(r'"([a-zA-Z0-9_-]+)(?:[<>=!]+([^"]+))?"', line)
                        if match:
                            deps.append(DependencyInfo(
                                name=match.group(1),
                                version=match.group(2),
                                type="runtime",
                                source_file=file_path,
                                ecosystem="pip",
                            ))
        
        return deps
