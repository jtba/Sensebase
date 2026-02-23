"""Tests for the analyzer registry and Python analyzer."""

from pathlib import Path

from src.analyzers.base import AnalysisResult
from src.analyzers.registry import create_default_registry


def test_create_default_registry():
    registry = create_default_registry()
    assert registry.get_analyzer("python") is not None
    assert registry.get_analyzer("java") is not None
    assert registry.get_analyzer("go") is not None
    assert registry.get_analyzer("javascript") is not None


def test_registry_file_dispatch():
    registry = create_default_registry()
    analyzers = registry.get_analyzers_for_file(Path("example.py"))
    assert len(analyzers) >= 1
    assert analyzers[0].language == "python"


def test_registry_unknown_extension():
    registry = create_default_registry()
    analyzers = registry.get_analyzers_for_file(Path("file.xyz"))
    assert analyzers == []


def test_python_analyzer_extracts_class():
    registry = create_default_registry()
    analyzer = registry.get_analyzer("python")

    source = '''
class UserService:
    """Handles user operations."""

    def create_user(self, name: str) -> dict:
        return {"name": name}
'''
    result = analyzer.analyze_file(Path("services/user.py"), source)
    assert isinstance(result, AnalysisResult)
    service_names = [s.name for s in result.business_logic]
    assert "UserService" in service_names


def test_python_analyzer_handles_syntax_error():
    registry = create_default_registry()
    analyzer = registry.get_analyzer("python")

    bad_source = "def broken(:\n    pass"
    result = analyzer.analyze_file(Path("bad.py"), bad_source)
    assert len(result.errors) > 0
