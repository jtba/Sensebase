"""Tests for the KnowledgeBase store."""

from src.store.knowledge_base import KnowledgeBase


def test_add_result_indexes_schemas(sample_analysis_result):
    kb = KnowledgeBase(output_dir="/tmp/kb-test")
    kb.add_result(sample_analysis_result)

    schemas = kb.find_schema("User")
    assert len(schemas) == 1
    assert schemas[0]["name"] == "User"


def test_add_result_indexes_services(sample_analysis_result):
    kb = KnowledgeBase(output_dir="/tmp/kb-test")
    kb.add_result(sample_analysis_result)

    services = kb.find_service("UserService")
    assert len(services) == 1
    assert services[0]["name"] == "UserService"


def test_add_result_indexes_dependencies(sample_analysis_result):
    kb = KnowledgeBase(output_dir="/tmp/kb-test")
    kb.add_result(sample_analysis_result)

    deps = kb.find_dependency("fastapi")
    assert len(deps) == 1
    assert deps[0]["version"] == "0.109.0"


def test_get_summary(sample_analysis_result):
    kb = KnowledgeBase(output_dir="/tmp/kb-test")
    kb.add_result(sample_analysis_result)

    summary = kb.get_summary()
    assert summary["repositories_analyzed"] == 1
    assert summary["total_schemas"] == 1
    assert summary["total_apis"] == 1
    assert summary["total_services"] == 1


def test_save_and_load(sample_analysis_result, tmp_path):
    kb = KnowledgeBase(output_dir=str(tmp_path))
    kb.add_result(sample_analysis_result)

    save_path = tmp_path / "kb.json"
    kb.save(save_path)

    loaded = KnowledgeBase.load(save_path)
    assert len(loaded.find_schema("User")) == 1
    assert len(loaded.find_service("UserService")) == 1
