"""Central ontology definitions for the ContextPedia knowledge model.

This module defines the formal vocabulary (enums, typed dataclasses,
normalization functions) used across all analyzers, extractors, and
the knowledge store. It is the single source of truth for:

- Entity classification types (SchemaType, BusinessLogicType, etc.)
- Typed inner structures (FieldInfo, RelationshipRef, MethodInfo, etc.)
- Relationship type aliases and normalization
- Ontology versioning
- Stable entity identity generation
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Ontology version — increment on breaking changes to serialized format
# ---------------------------------------------------------------------------

ONTOLOGY_VERSION = "2"


# ---------------------------------------------------------------------------
# Enum types — use (str, Enum) for Python 3.10 compat and JSON serialization
# ---------------------------------------------------------------------------

class SchemaType(str, Enum):
    """Classification of extracted data schemas."""
    TABLE = "table"
    MODEL = "model"
    ENTITY = "entity"
    TYPE = "type"
    INTERFACE = "interface"
    INPUT = "input"          # GraphQL input types
    MESSAGE = "message"      # Protobuf messages
    ENUM = "enum"            # Enum definitions


class BusinessLogicType(str, Enum):
    """Classification of business logic components."""
    SERVICE = "service"
    HANDLER = "handler"
    RULE = "rule"
    WORKFLOW = "workflow"
    VALIDATOR = "validator"
    INTERFACE = "interface"      # Go interfaces
    CONTROLLER = "controller"
    MANAGER = "manager"
    REPOSITORY = "repository"


class DependencyType(str, Enum):
    """Classification of package dependencies."""
    RUNTIME = "runtime"
    DEV = "dev"
    OPTIONAL = "optional"
    PEER = "peer"


class Ecosystem(str, Enum):
    """Package ecosystem / language platform."""
    PIP = "pip"
    NPM = "npm"
    MAVEN = "maven"
    GO = "go"
    CARGO = "cargo"
    NUGET = "nuget"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    DATABASE = "database"


class DataFlowType(str, Enum):
    """Type of data flow between components."""
    READ = "read"
    WRITE = "write"
    TRANSFORM = "transform"
    PUBLISH = "publish"
    SUBSCRIBE = "subscribe"


class HTTPMethod(str, Enum):
    """HTTP methods for API endpoints."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"
    ANY = "ANY"  # Go stdlib http.HandleFunc, catch-all routes


class RelationshipType(str, Enum):
    """Type of relationship between schemas/entities."""
    HAS_MANY = "has_many"
    BELONGS_TO = "belongs_to"
    HAS_ONE = "has_one"
    MANY_TO_MANY = "many_to_many"
    FOREIGN_KEY = "foreign_key"
    RELATIONSHIP = "relationship"  # Generic / unclassified


class EntityStatus(str, Enum):
    """Lifecycle status of an ontology entity."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"
    DRAFT = "draft"


class LinkCardinality(str, Enum):
    """Cardinality of a link type."""
    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    MANY_TO_MANY = "many_to_many"


# ---------------------------------------------------------------------------
# Alias maps for normalization
# ---------------------------------------------------------------------------

_RELATIONSHIP_ALIASES: dict[str, str] = {
    "one_to_many": "has_many",
    "many_to_one": "belongs_to",
    "one_to_one": "has_one",
    "onetomany": "has_many",
    "manytoone": "belongs_to",
    "onetoone": "has_one",
    "manytomany": "many_to_many",
    "fk": "foreign_key",
}

_SCHEMA_TYPE_ALIASES: dict[str, str] = {
    "class": "model",
    "struct": "model",
    "record": "model",
    "dataclass": "model",
    "schema": "type",
    "typedef": "type",
    "proto": "message",
}

_HTTP_METHOD_ALIASES: dict[str, str] = {
    "get": "GET",
    "post": "POST",
    "put": "PUT",
    "delete": "DELETE",
    "patch": "PATCH",
    "options": "OPTIONS",
    "head": "HEAD",
    "any": "ANY",
    "*": "ANY",
}


# ---------------------------------------------------------------------------
# Normalization functions — tolerant of aliases and unknown values
# ---------------------------------------------------------------------------

def normalize_schema_type(value: str) -> SchemaType:
    """Normalize a schema type string to the canonical enum value."""
    lowered = value.lower().strip()
    canonical = _SCHEMA_TYPE_ALIASES.get(lowered, lowered)
    try:
        return SchemaType(canonical)
    except ValueError:
        return SchemaType.TYPE  # safe fallback


def normalize_business_logic_type(value: str) -> BusinessLogicType:
    """Normalize a business logic type string to the canonical enum value."""
    lowered = value.lower().strip()
    try:
        return BusinessLogicType(lowered)
    except ValueError:
        return BusinessLogicType.SERVICE  # safe fallback


def normalize_dependency_type(value: str) -> DependencyType:
    """Normalize a dependency type string to the canonical enum value."""
    lowered = value.lower().strip()
    try:
        return DependencyType(lowered)
    except ValueError:
        return DependencyType.RUNTIME  # safe fallback


def normalize_ecosystem(value: str) -> Ecosystem:
    """Normalize an ecosystem string to the canonical enum value."""
    lowered = value.lower().strip()
    try:
        return Ecosystem(lowered)
    except ValueError:
        return Ecosystem.PIP  # safe fallback


def normalize_data_flow_type(value: str) -> DataFlowType:
    """Normalize a data flow type string to the canonical enum value."""
    lowered = value.lower().strip()
    try:
        return DataFlowType(lowered)
    except ValueError:
        return DataFlowType.READ  # safe fallback


def normalize_http_method(value: str) -> HTTPMethod:
    """Normalize an HTTP method string to the canonical enum value."""
    stripped = value.strip()
    canonical = _HTTP_METHOD_ALIASES.get(stripped.lower(), stripped.upper())
    try:
        return HTTPMethod(canonical)
    except ValueError:
        return HTTPMethod.GET  # safe fallback


def normalize_relationship_type(value: str) -> RelationshipType:
    """Normalize a relationship type string to the canonical enum value."""
    lowered = value.lower().strip()
    canonical = _RELATIONSHIP_ALIASES.get(lowered, lowered)
    try:
        return RelationshipType(canonical)
    except ValueError:
        return RelationshipType.RELATIONSHIP  # safe fallback


def normalize_entity_status(value: str) -> EntityStatus:
    """Normalize an entity status string to the canonical enum value."""
    lowered = value.lower().strip()
    try:
        return EntityStatus(lowered)
    except ValueError:
        return EntityStatus.ACTIVE  # safe fallback


def normalize_link_cardinality(value: str) -> LinkCardinality:
    """Normalize a link cardinality string to the canonical enum value."""
    lowered = value.lower().strip().replace("-", "_").replace(" ", "_")
    try:
        return LinkCardinality(lowered)
    except ValueError:
        return LinkCardinality.MANY_TO_ONE  # safe fallback


# ---------------------------------------------------------------------------
# Typed inner dataclasses — replace list[dict[str, Any]] in entity models
# ---------------------------------------------------------------------------

@dataclass
class FieldInfo:
    """A field/column within a schema or data structure.

    Covers SQL columns, model fields, GraphQL fields, Protobuf fields,
    TypeScript interface members, Go struct fields, etc.
    """
    name: str = ""
    type: str = ""
    constraints: list[str] = field(default_factory=list)
    description: str | None = None
    # Language-specific optional properties
    nullable: bool | None = None        # GraphQL, SQL
    optional: bool | None = None        # TypeScript
    annotations: str | None = None      # Java annotations
    tags: str | None = None             # Go struct tags
    json_name: str | None = None        # Go JSON name from tags
    field_number: int | None = None     # Protobuf field number

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FieldInfo:
        """Create from a dict, tolerating unknown keys."""
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in d.items() if k in known}
        return cls(**filtered)


@dataclass
class RelationshipRef:
    """A relationship from one schema/entity to another."""
    type: RelationshipType = RelationshipType.RELATIONSHIP
    target: str = ""
    field: str | None = None
    description: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RelationshipRef:
        """Create from a dict, normalizing the relationship type."""
        return cls(
            type=normalize_relationship_type(d.get("type", "relationship")),
            target=d.get("target", ""),
            field=d.get("field") or d.get("via"),
            description=d.get("description"),
        )


@dataclass
class ParamInfo:
    """A parameter for a method or API endpoint."""
    name: str = ""
    type: str = "Any"
    # API-specific
    location: str | None = None   # "path", "query", "body", "header"
    required: bool | None = None
    description: str | None = None

    @classmethod
    def from_dict(cls, d: Any) -> ParamInfo:
        """Create from a dict or string."""
        if isinstance(d, str):
            return cls(name=d)
        if not isinstance(d, dict):
            return cls(name=str(d))
        return cls(
            name=d.get("name", ""),
            type=d.get("type", "Any"),
            location=d.get("in") or d.get("location"),
            required=d.get("required"),
            description=d.get("description"),
        )


@dataclass
class MethodInfo:
    """A method within a service or business logic component."""
    name: str = ""
    params: list[ParamInfo] = field(default_factory=list)
    returns: str | None = None
    return_type: str | None = None    # Alias used by some analyzers
    docstring: str | None = None
    description: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MethodInfo:
        """Create from a dict, converting nested params."""
        raw_params = d.get("params", [])
        if isinstance(raw_params, str):
            # Some analyzers store params as a raw signature string
            params = [ParamInfo(name=raw_params)]
        else:
            params = [ParamInfo.from_dict(p) for p in raw_params]
        return cls(
            name=d.get("name", ""),
            params=params,
            returns=d.get("returns"),
            return_type=d.get("return_type"),
            docstring=d.get("docstring"),
            description=d.get("description"),
        )


@dataclass
class DataOwnershipEntry:
    """An entity owned by a repository (source of truth tracking)."""
    entity: str = ""
    description: str = ""
    is_source_of_truth: bool = False

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DataOwnershipEntry:
        return cls(
            entity=d.get("entity", ""),
            description=d.get("description", ""),
            is_source_of_truth=d.get("is_source_of_truth", False),
        )


@dataclass
class ServiceDependencyEntry:
    """A service dependency reference."""
    service: str = ""
    reason: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ServiceDependencyEntry:
        return cls(
            service=d.get("service", ""),
            reason=d.get("reason", ""),
        )


@dataclass
class GlossaryEntry:
    """A business glossary entry mapping domain terms to definitions."""
    term: str = ""
    definition: str = ""
    related_schemas: list[str] = field(default_factory=list)
    related_apis: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GlossaryEntry:
        return cls(
            term=d.get("term", ""),
            definition=d.get("definition", ""),
            related_schemas=d.get("related_schemas", []),
            related_apis=d.get("related_apis", []),
        )


@dataclass
class QueryRecipe:
    """A recipe for answering a business question using the knowledge base."""
    question: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    answer_format: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> QueryRecipe:
        return cls(
            question=d.get("question", ""),
            steps=d.get("steps", []),
            answer_format=d.get("answer_format", ""),
        )


@dataclass
class LinkPropertyInfo:
    """A property carried by a link type (metadata about the relationship itself).

    For example, an "Employment" link between Person and Company might carry
    ``start_date``, ``role``, and ``salary`` as link properties.
    """
    name: str = ""
    type: str = ""
    description: str | None = None


@dataclass
class LinkTypeInfo:
    """First-class, bidirectional link between two entity types.

    Promotes relationships from thin annotations (``RelationshipRef``) to
    full ontology entities that can carry properties, be traversed in both
    directions, and be queried independently.
    """
    name: str = ""
    source_type: str = ""
    target_type: str = ""
    cardinality: LinkCardinality = LinkCardinality.MANY_TO_ONE
    properties: list[LinkPropertyInfo] = field(default_factory=list)
    description: str | None = None
    source_file: str = ""
    bidirectional: bool = True
    inverse_name: str | None = None
    entity_id: str = ""
    status: EntityStatus = EntityStatus.ACTIVE

    _CARDINALITY_FROM_REL: dict[str, LinkCardinality] = field(
        default=None, repr=False, init=False,
    )

    def __post_init__(self):
        # Class-level constant stored on the instance to keep the dataclass
        # decorator happy (avoids mutable default at class level).
        object.__setattr__(self, "_CARDINALITY_FROM_REL", {
            RelationshipType.HAS_MANY: LinkCardinality.ONE_TO_MANY,
            RelationshipType.BELONGS_TO: LinkCardinality.MANY_TO_ONE,
            RelationshipType.HAS_ONE: LinkCardinality.ONE_TO_ONE,
            RelationshipType.MANY_TO_MANY: LinkCardinality.MANY_TO_MANY,
            RelationshipType.FOREIGN_KEY: LinkCardinality.MANY_TO_ONE,
            RelationshipType.RELATIONSHIP: LinkCardinality.MANY_TO_ONE,
        })

    @classmethod
    def from_relationship_ref(
        cls,
        ref: RelationshipRef,
        source_schema: str,
        source_file: str,
    ) -> LinkTypeInfo:
        """Promote a ``RelationshipRef`` to a first-class ``LinkTypeInfo``."""
        cardinality_map = {
            RelationshipType.HAS_MANY: LinkCardinality.ONE_TO_MANY,
            RelationshipType.BELONGS_TO: LinkCardinality.MANY_TO_ONE,
            RelationshipType.HAS_ONE: LinkCardinality.ONE_TO_ONE,
            RelationshipType.MANY_TO_MANY: LinkCardinality.MANY_TO_MANY,
            RelationshipType.FOREIGN_KEY: LinkCardinality.MANY_TO_ONE,
            RelationshipType.RELATIONSHIP: LinkCardinality.MANY_TO_ONE,
        }
        return cls(
            name=f"{source_schema}__{ref.target}",
            source_type=source_schema,
            target_type=ref.target,
            cardinality=cardinality_map.get(ref.type, LinkCardinality.MANY_TO_ONE),
            description=ref.description,
            source_file=source_file,
            bidirectional=True,
            inverse_name=f"{ref.target}__{source_schema}",
        )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LinkTypeInfo:
        """Create from a dict, normalizing enum values."""
        props = [LinkPropertyInfo(**p) if isinstance(p, dict) else p
                 for p in d.get("properties", [])]
        return cls(
            name=d.get("name", ""),
            source_type=d.get("source_type", ""),
            target_type=d.get("target_type", ""),
            cardinality=normalize_link_cardinality(d.get("cardinality", "many_to_one")),
            properties=props,
            description=d.get("description"),
            source_file=d.get("source_file", ""),
            bidirectional=d.get("bidirectional", True),
            inverse_name=d.get("inverse_name"),
            entity_id=d.get("entity_id", ""),
            status=normalize_entity_status(d.get("status", "active")),
        )


@dataclass
class InterfaceProperty:
    """A property required by an interface contract."""
    name: str = ""
    type: str = ""
    description: str | None = None


@dataclass
class InterfaceType:
    """Abstract type definition that schema types can implement.

    Interfaces enable cross-repo type polymorphism — if ``User`` in repo-A
    and ``Account`` in repo-B both carry ``id``, ``email``, and
    ``created_at``, an ``Identifiable`` interface captures that shared shape.
    """
    name: str = ""
    description: str | None = None
    properties: list[InterfaceProperty] = field(default_factory=list)
    extends: list[str] = field(default_factory=list)
    implemented_by: list[str] = field(default_factory=list)
    inferred: bool = False
    entity_id: str = ""
    status: EntityStatus = EntityStatus.ACTIVE

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> InterfaceType:
        """Create from a dict."""
        props = [InterfaceProperty(**p) if isinstance(p, dict) else p
                 for p in d.get("properties", [])]
        return cls(
            name=d.get("name", ""),
            description=d.get("description"),
            properties=props,
            extends=d.get("extends", []),
            implemented_by=d.get("implemented_by", []),
            inferred=d.get("inferred", False),
            entity_id=d.get("entity_id", ""),
            status=normalize_entity_status(d.get("status", "active")),
        )


# ---------------------------------------------------------------------------
# Entity identity
# ---------------------------------------------------------------------------

def make_entity_id(
    entity_type: str,
    name: str,
    repo: str,
    source_file: str,
) -> str:
    """Generate a stable, unique entity identifier.

    Format: ``{type}:{repo}:{name}:{file_hash8}``

    The source file path is hashed to keep IDs compact while still
    disambiguating entities with the same name in different files.
    """
    file_hash = hashlib.sha256(source_file.encode()).hexdigest()[:8]
    return f"{entity_type}:{repo}:{name}:{file_hash}"
