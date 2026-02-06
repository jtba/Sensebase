"""Schema-specific extractors for SQL, GraphQL, Protobuf, etc."""

import re
from pathlib import Path

from ..analyzers.base import (
    Analyzer,
    AnalysisResult,
    SchemaInfo,
)


class SchemaAnalyzer(Analyzer):
    """Analyzer for schema definition files."""
    
    extensions = [".sql", ".graphql", ".gql", ".proto"]
    language = "schema"
    
    def analyze_file(self, file_path: Path, content: str) -> AnalysisResult:
        result = AnalysisResult(
            repo_path=str(file_path.parent),
            repo_name=file_path.parent.name,
        )
        
        rel_path = str(file_path)
        
        if file_path.suffix == ".sql":
            result.schemas.extend(self._parse_sql(content, rel_path))
        elif file_path.suffix in (".graphql", ".gql"):
            result.schemas.extend(self._parse_graphql(content, rel_path))
        elif file_path.suffix == ".proto":
            result.schemas.extend(self._parse_protobuf(content, rel_path))
        
        return result
    
    def _parse_sql(self, content: str, file_path: str) -> list[SchemaInfo]:
        """Parse SQL CREATE TABLE statements."""
        schemas = []
        
        # Match CREATE TABLE statements
        table_pattern = re.compile(
            r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"\']?(\w+)[`"\']?\s*\(([^;]+)\)',
            re.IGNORECASE | re.MULTILINE | re.DOTALL
        )
        
        for match in table_pattern.finditer(content):
            table_name = match.group(1)
            body = match.group(2)
            
            fields = self._parse_sql_columns(body)
            relationships = self._parse_sql_foreign_keys(body)
            
            schemas.append(SchemaInfo(
                name=table_name,
                type="table",
                source_file=file_path,
                fields=fields,
                relationships=relationships,
                raw_definition=match.group(0),
            ))
        
        return schemas
    
    def _parse_sql_columns(self, body: str) -> list[dict]:
        """Parse SQL column definitions."""
        fields = []
        
        # Split by comma, but be careful with complex types
        lines = []
        current = ""
        paren_depth = 0
        
        for char in body:
            if char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth -= 1
            elif char == ',' and paren_depth == 0:
                lines.append(current.strip())
                current = ""
                continue
            current += char
        if current.strip():
            lines.append(current.strip())
        
        for line in lines:
            # Skip constraints
            if any(line.upper().startswith(kw) for kw in 
                   ['PRIMARY', 'FOREIGN', 'UNIQUE', 'CHECK', 'INDEX', 'CONSTRAINT', 'KEY']):
                continue
            
            # Match column definition: name TYPE [constraints]
            col_match = re.match(
                r'[`"\']?(\w+)[`"\']?\s+(\w+(?:\([^)]+\))?)',
                line.strip(),
                re.IGNORECASE
            )
            
            if col_match:
                name = col_match.group(1)
                col_type = col_match.group(2)
                
                constraints = []
                line_upper = line.upper()
                
                if 'PRIMARY KEY' in line_upper:
                    constraints.append("primary_key")
                if 'NOT NULL' in line_upper:
                    constraints.append("not_null")
                if 'UNIQUE' in line_upper:
                    constraints.append("unique")
                if 'AUTO_INCREMENT' in line_upper or 'SERIAL' in line_upper:
                    constraints.append("auto_increment")
                if 'DEFAULT' in line_upper:
                    default_match = re.search(r'DEFAULT\s+([^\s,]+)', line, re.IGNORECASE)
                    if default_match:
                        constraints.append(f"default={default_match.group(1)}")
                
                fields.append({
                    "name": name,
                    "type": col_type,
                    "constraints": constraints,
                })
        
        return fields
    
    def _parse_sql_foreign_keys(self, body: str) -> list[dict]:
        """Parse SQL foreign key constraints."""
        relationships = []
        
        # Match FOREIGN KEY ... REFERENCES
        fk_pattern = re.compile(
            r'FOREIGN\s+KEY\s*\([`"\']?(\w+)[`"\']?\)\s*REFERENCES\s*[`"\']?(\w+)[`"\']?',
            re.IGNORECASE
        )
        
        for match in fk_pattern.finditer(body):
            relationships.append({
                "type": "foreign_key",
                "field": match.group(1),
                "target": match.group(2),
            })
        
        return relationships
    
    def _parse_graphql(self, content: str, file_path: str) -> list[SchemaInfo]:
        """Parse GraphQL type definitions."""
        schemas = []
        
        # Match type definitions
        type_pattern = re.compile(
            r'type\s+(\w+)(?:\s+implements\s+[^{]+)?\s*\{([^}]+)\}',
            re.MULTILINE | re.DOTALL
        )
        
        for match in type_pattern.finditer(content):
            type_name = match.group(1)
            body = match.group(2)
            
            # Skip Query, Mutation, Subscription
            if type_name in ('Query', 'Mutation', 'Subscription'):
                continue
            
            fields = self._parse_graphql_fields(body)
            
            schemas.append(SchemaInfo(
                name=type_name,
                type="type",
                source_file=file_path,
                fields=fields,
                relationships=self._infer_graphql_relationships(fields),
                raw_definition=match.group(0),
            ))
        
        # Match input types
        input_pattern = re.compile(
            r'input\s+(\w+)\s*\{([^}]+)\}',
            re.MULTILINE | re.DOTALL
        )
        
        for match in input_pattern.finditer(content):
            type_name = match.group(1)
            body = match.group(2)
            
            fields = self._parse_graphql_fields(body)
            
            schemas.append(SchemaInfo(
                name=type_name,
                type="input",
                source_file=file_path,
                fields=fields,
                relationships=[],
                raw_definition=match.group(0),
            ))
        
        return schemas
    
    def _parse_graphql_fields(self, body: str) -> list[dict]:
        """Parse GraphQL field definitions."""
        fields = []
        
        # Match: fieldName(args): Type! or fieldName: Type
        field_pattern = re.compile(
            r'(\w+)(?:\([^)]*\))?\s*:\s*(\[?\w+\]?!?)',
            re.MULTILINE
        )
        
        for match in field_pattern.finditer(body):
            name = match.group(1)
            field_type = match.group(2)
            
            constraints = []
            if field_type.endswith('!'):
                constraints.append("required")
            if field_type.startswith('['):
                constraints.append("array")
            
            # Clean type
            clean_type = field_type.strip('[]!')
            
            fields.append({
                "name": name,
                "type": clean_type,
                "constraints": constraints,
                "nullable": not field_type.endswith('!'),
            })
        
        return fields
    
    def _infer_graphql_relationships(self, fields: list[dict]) -> list[dict]:
        """Infer relationships from GraphQL fields."""
        relationships = []
        
        for field in fields:
            field_type = field.get("type", "")
            
            # If type starts with uppercase and isn't a scalar, it's likely a relation
            if field_type and field_type[0].isupper():
                if field_type not in ('String', 'Int', 'Float', 'Boolean', 'ID', 'DateTime'):
                    is_array = "array" in field.get("constraints", [])
                    relationships.append({
                        "type": "has_many" if is_array else "has_one",
                        "target": field_type,
                        "field": field["name"],
                    })
        
        return relationships
    
    def _parse_protobuf(self, content: str, file_path: str) -> list[SchemaInfo]:
        """Parse Protocol Buffers message definitions."""
        schemas = []
        
        # Match message definitions
        message_pattern = re.compile(
            r'message\s+(\w+)\s*\{([^}]+)\}',
            re.MULTILINE | re.DOTALL
        )
        
        for match in message_pattern.finditer(content):
            message_name = match.group(1)
            body = match.group(2)
            
            fields = self._parse_protobuf_fields(body)
            
            schemas.append(SchemaInfo(
                name=message_name,
                type="message",
                source_file=file_path,
                fields=fields,
                relationships=self._infer_protobuf_relationships(fields),
                raw_definition=match.group(0),
            ))
        
        return schemas
    
    def _parse_protobuf_fields(self, body: str) -> list[dict]:
        """Parse Protobuf field definitions."""
        fields = []
        
        # Match: [repeated] type name = number;
        field_pattern = re.compile(
            r'(repeated\s+)?(\w+)\s+(\w+)\s*=\s*(\d+)',
            re.MULTILINE
        )
        
        for match in field_pattern.finditer(body):
            is_repeated = match.group(1) is not None
            field_type = match.group(2)
            name = match.group(3)
            number = match.group(4)
            
            constraints = []
            if is_repeated:
                constraints.append("repeated")
            
            fields.append({
                "name": name,
                "type": field_type,
                "constraints": constraints,
                "field_number": int(number),
            })
        
        return fields
    
    def _infer_protobuf_relationships(self, fields: list[dict]) -> list[dict]:
        """Infer relationships from Protobuf fields."""
        relationships = []
        
        scalar_types = {
            'double', 'float', 'int32', 'int64', 'uint32', 'uint64',
            'sint32', 'sint64', 'fixed32', 'fixed64', 'sfixed32', 'sfixed64',
            'bool', 'string', 'bytes'
        }
        
        for field in fields:
            field_type = field.get("type", "")
            
            if field_type.lower() not in scalar_types:
                is_repeated = "repeated" in field.get("constraints", [])
                relationships.append({
                    "type": "has_many" if is_repeated else "has_one",
                    "target": field_type,
                    "field": field["name"],
                })
        
        return relationships
