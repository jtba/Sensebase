"""Tests for the SearchEngine."""

from src.query.search import SearchEngine


def test_search_finds_schema(sample_kb_json):
    engine = SearchEngine(kb_path=sample_kb_json)
    results = engine.search("User")

    names = [r["name"] for r in results]
    assert "User" in names


def test_search_finds_service(sample_kb_json):
    engine = SearchEngine(kb_path=sample_kb_json)
    results = engine.search("UserService")

    names = [r["name"] for r in results]
    assert "UserService" in names


def test_search_finds_dependency(sample_kb_json):
    engine = SearchEngine(kb_path=sample_kb_json)
    results = engine.search("fastapi")

    types = [r["type"] for r in results]
    assert "dependency" in types


def test_search_respects_limit(sample_kb_json):
    engine = SearchEngine(kb_path=sample_kb_json)
    results = engine.search("user", limit=1)
    assert len(results) <= 1


def test_find_schema_by_name(sample_kb_json):
    engine = SearchEngine(kb_path=sample_kb_json)
    results = engine.find_schema("User")
    assert len(results) == 1
    assert results[0]["name"] == "User"


def test_find_service_by_name(sample_kb_json):
    engine = SearchEngine(kb_path=sample_kb_json)
    results = engine.find_service("UserService")
    assert len(results) == 1


def test_score_match_exact():
    engine = SearchEngine.__new__(SearchEngine)
    score = engine._score_match("user", ["User", "something else"])
    assert score > 0


def test_search_no_results(sample_kb_json):
    engine = SearchEngine(kb_path=sample_kb_json)
    results = engine.search("zzz_nonexistent_zzz")
    assert results == []
