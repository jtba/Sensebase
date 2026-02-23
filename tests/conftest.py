"""Shared test fixtures."""

import json

import pytest

from src.analyzers.base import (
    AnalysisResult,
    SchemaInfo,
    APIInfo,
    BusinessLogicInfo,
    DependencyInfo,
)


@pytest.fixture
def sample_schema():
    """A minimal SchemaInfo for testing."""
    return SchemaInfo(
        name="User",
        type="model",
        source_file="models/user.py",
        fields=[
            {"name": "id", "type": "int", "constraints": ["primary_key"]},
            {"name": "email", "type": "str", "constraints": ["unique"]},
            {"name": "name", "type": "str", "constraints": []},
        ],
        relationships=[
            {"type": "has_many", "target": "Order", "field": "orders"},
        ],
    )


@pytest.fixture
def sample_api():
    """A minimal APIInfo for testing."""
    return APIInfo(
        path="/api/users",
        method="GET",
        source_file="routes/users.py",
        handler="list_users",
        params=[{"name": "limit", "type": "int"}],
        request_body=None,
        response={"type": "list", "items": "User"},
        description="List all users",
    )


@pytest.fixture
def sample_service():
    """A minimal BusinessLogicInfo for testing."""
    return BusinessLogicInfo(
        name="UserService",
        type="service",
        source_file="services/user_service.py",
        description="Handles user operations",
        methods=[
            {"name": "create_user", "params": ["email", "name"], "returns": "User"},
        ],
        dependencies=["EmailService"],
        data_accessed=["User"],
    )


@pytest.fixture
def sample_dependency():
    """A minimal DependencyInfo for testing."""
    return DependencyInfo(
        name="fastapi",
        version="0.109.0",
        type="runtime",
        source_file="pyproject.toml",
        ecosystem="pip",
    )


@pytest.fixture
def sample_analysis_result(sample_schema, sample_api, sample_service, sample_dependency):
    """An AnalysisResult populated with sample data."""
    return AnalysisResult(
        repo_path="/tmp/test-repo",
        repo_name="test-repo",
        schemas=[sample_schema],
        apis=[sample_api],
        business_logic=[sample_service],
        dependencies=[sample_dependency],
        languages={"python": 100.0},
        file_count=5,
        analyzed_files=["models/user.py", "routes/users.py"],
    )


@pytest.fixture
def sample_kb_json(sample_analysis_result, tmp_path):
    """Write a minimal knowledge_base.json and return its path."""
    from dataclasses import asdict

    result = sample_analysis_result
    data = {
        "summary": {
            "repositories_analyzed": 1,
            "total_schemas": 1,
            "total_apis": 1,
            "total_services": 1,
            "total_dependencies": 1,
            "unique_schemas": 1,
            "unique_dependencies": 1,
        },
        "schemas": [
            {"repo": result.repo_name, **asdict(s)} for s in result.schemas
        ],
        "apis": [
            {"repo": result.repo_name, **asdict(a)} for a in result.apis
        ],
        "services": [
            {"repo": result.repo_name, **asdict(s)} for s in result.business_logic
        ],
        "dependencies": [
            {"repo": result.repo_name, **asdict(d)} for d in result.dependencies
        ],
        "contexts": [],
        "relationships": {},
        "semantic_layers": [],
    }

    kb_path = tmp_path / "knowledge_base.json"
    kb_path.write_text(json.dumps(data, indent=2, default=str))
    return kb_path
