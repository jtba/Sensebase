"""Configuration file analyzer for YAML, TOML, JSON configs."""

import json
import re
from pathlib import Path

import yaml

from ..analyzers.base import (
    Analyzer,
    AnalysisResult,
    DependencyInfo,
)


class ConfigAnalyzer(Analyzer):
    """Analyzer for configuration files."""
    
    extensions = [".yaml", ".yml", ".toml", ".json"]
    language = "config"
    
    # Known config file patterns
    DOCKER_COMPOSE = re.compile(r'docker-compose.*\.ya?ml$')
    K8S_PATTERNS = ['deployment', 'service', 'configmap', 'ingress', 'pod']
    
    def analyze_file(self, file_path: Path, content: str) -> AnalysisResult:
        result = AnalysisResult(
            repo_path=str(file_path.parent),
            repo_name=file_path.parent.name,
        )
        
        rel_path = str(file_path)
        
        # Parse the content
        data = self._parse_content(file_path, content)
        if data is None:
            return result
        
        # Docker Compose
        if self.DOCKER_COMPOSE.match(file_path.name):
            self._analyze_docker_compose(data, rel_path, result)
        
        # Kubernetes manifests
        elif self._is_k8s_manifest(data):
            self._analyze_k8s_manifest(data, rel_path, result)
        
        # OpenAPI/Swagger
        elif 'openapi' in data or 'swagger' in data:
            self._analyze_openapi(data, rel_path, result)
        
        # Database configs
        elif 'database' in data or 'databases' in data or 'datasource' in data:
            self._analyze_database_config(data, rel_path, result)
        
        return result
    
    def _parse_content(self, file_path: Path, content: str) -> dict | None:
        """Parse config file content."""
        try:
            if file_path.suffix in ('.yaml', '.yml'):
                return yaml.safe_load(content)
            elif file_path.suffix == '.json':
                return json.loads(content)
            elif file_path.suffix == '.toml':
                try:
                    import toml
                    return toml.loads(content)
                except ImportError:
                    return None
        except Exception:
            return None
        return None
    
    def _is_k8s_manifest(self, data: dict) -> bool:
        """Check if data looks like a Kubernetes manifest."""
        if not isinstance(data, dict):
            return False
        return 'apiVersion' in data and 'kind' in data
    
    def _analyze_docker_compose(
        self,
        data: dict,
        file_path: str,
        result: AnalysisResult,
    ) -> None:
        """Analyze Docker Compose file."""
        services = data.get('services', {})
        
        for name, config in services.items():
            # Extract image as dependency
            if 'image' in config:
                result.dependencies.append(DependencyInfo(
                    name=config['image'],
                    version=None,
                    type="runtime",
                    source_file=file_path,
                    ecosystem="docker",
                ))
            
            # Extract environment variables for context
            # (Could add to a separate metadata structure)
            
            # Extract depends_on for service relationships
            depends = config.get('depends_on', [])
            if isinstance(depends, list):
                for dep in depends:
                    # Could add as a data flow relationship
                    pass
    
    def _analyze_k8s_manifest(
        self,
        data: dict,
        file_path: str,
        result: AnalysisResult,
    ) -> None:
        """Analyze Kubernetes manifest."""
        kind = data.get('kind', '')
        metadata = data.get('metadata', {})
        spec = data.get('spec', {})
        
        # Extract container images
        containers = []
        
        if kind == 'Deployment':
            pod_spec = spec.get('template', {}).get('spec', {})
            containers = pod_spec.get('containers', [])
        elif kind == 'Pod':
            containers = spec.get('containers', [])
        
        for container in containers:
            if 'image' in container:
                result.dependencies.append(DependencyInfo(
                    name=container['image'],
                    version=None,
                    type="runtime",
                    source_file=file_path,
                    ecosystem="kubernetes",
                ))
    
    def _analyze_openapi(
        self,
        data: dict,
        file_path: str,
        result: AnalysisResult,
    ) -> None:
        """Analyze OpenAPI/Swagger specification."""
        from ..analyzers.base import APIInfo, SchemaInfo
        
        # Extract API endpoints
        paths = data.get('paths', {})
        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue
            
            for method, details in methods.items():
                if method.lower() not in ('get', 'post', 'put', 'delete', 'patch'):
                    continue
                
                if not isinstance(details, dict):
                    continue
                
                result.apis.append(APIInfo(
                    path=path,
                    method=method.upper(),
                    source_file=file_path,
                    handler=details.get('operationId', ''),
                    params=self._extract_openapi_params(details),
                    request_body=details.get('requestBody'),
                    response=details.get('responses'),
                    description=details.get('summary') or details.get('description'),
                ))
        
        # Extract schemas
        schemas = data.get('components', {}).get('schemas', {})
        # Also check Swagger 2.0 location
        if not schemas:
            schemas = data.get('definitions', {})
        
        for name, schema in schemas.items():
            if not isinstance(schema, dict):
                continue
            
            fields = []
            properties = schema.get('properties', {})
            required = set(schema.get('required', []))
            
            for prop_name, prop_def in properties.items():
                if not isinstance(prop_def, dict):
                    continue
                
                constraints = []
                if prop_name in required:
                    constraints.append("required")
                
                fields.append({
                    "name": prop_name,
                    "type": prop_def.get('type', 'any'),
                    "constraints": constraints,
                    "description": prop_def.get('description'),
                })
            
            result.schemas.append(SchemaInfo(
                name=name,
                type="interface",
                source_file=file_path,
                fields=fields,
                relationships=[],
            ))
    
    def _extract_openapi_params(self, operation: dict) -> list[dict]:
        """Extract parameters from OpenAPI operation."""
        params = []
        
        for param in operation.get('parameters', []):
            if not isinstance(param, dict):
                continue
            
            params.append({
                "name": param.get('name'),
                "in": param.get('in'),  # query, path, header
                "type": param.get('schema', {}).get('type', 'any'),
                "required": param.get('required', False),
            })
        
        return params
    
    def _analyze_database_config(
        self,
        data: dict,
        file_path: str,
        result: AnalysisResult,
    ) -> None:
        """Analyze database configuration."""
        # Look for database connection info
        db_keys = ['database', 'databases', 'datasource', 'db']
        
        for key in db_keys:
            if key in data:
                db_config = data[key]
                
                if isinstance(db_config, dict):
                    # Single database
                    self._extract_db_dependency(db_config, file_path, result)
                elif isinstance(db_config, list):
                    # Multiple databases
                    for db in db_config:
                        if isinstance(db, dict):
                            self._extract_db_dependency(db, file_path, result)
    
    def _extract_db_dependency(
        self,
        config: dict,
        file_path: str,
        result: AnalysisResult,
    ) -> None:
        """Extract database as dependency."""
        db_type = config.get('type') or config.get('driver') or config.get('engine')
        db_name = config.get('name') or config.get('database')
        
        if db_type:
            result.dependencies.append(DependencyInfo(
                name=f"{db_type}:{db_name}" if db_name else db_type,
                version=None,
                type="runtime",
                source_file=file_path,
                ecosystem="database",
            ))
