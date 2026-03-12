"""Tests for the four ontology v2 improvements:
1. First-class bidirectional link types
2. Interfaces for cross-repo type polymorphism
3. Entity lifecycle status
4. Graph-queryable store
"""

from src.analyzers.base import (
    AnalysisResult,
    SchemaInfo,
    APIInfo,
    BusinessLogicInfo,
    DependencyInfo,
)
from src.analyzers.ontology import (
    EntityStatus,
    FieldInfo,
    InterfaceProperty,
    InterfaceType,
    LinkCardinality,
    LinkTypeInfo,
    RelationshipRef,
    RelationshipType,
    SchemaType,
    BusinessLogicType,
    DependencyType,
    Ecosystem,
    HTTPMethod,
    ParamInfo,
    normalize_entity_status,
    normalize_link_cardinality,
)
from src.store.graph import GraphEdge, GraphNode, OntologyGraph
from src.store.knowledge_base import KnowledgeBase


# ---------------------------------------------------------------
# 1. First-class bidirectional link types
# ---------------------------------------------------------------


class TestLinkTypes:
    def test_link_type_from_relationship_ref(self):
        ref = RelationshipRef(
            type=RelationshipType.HAS_MANY, target="Order", field="orders",
        )
        link = LinkTypeInfo.from_relationship_ref(ref, "User", "models/user.py")

        assert link.name == "User__Order"
        assert link.source_type == "User"
        assert link.target_type == "Order"
        assert link.cardinality == LinkCardinality.ONE_TO_MANY
        assert link.bidirectional is True
        assert link.inverse_name == "Order__User"

    def test_link_type_belongs_to_cardinality(self):
        ref = RelationshipRef(
            type=RelationshipType.BELONGS_TO, target="User",
        )
        link = LinkTypeInfo.from_relationship_ref(ref, "Order", "models/order.py")
        assert link.cardinality == LinkCardinality.MANY_TO_ONE

    def test_link_type_auto_created_from_schema_relationships(self):
        """When a schema has RelationshipRefs, add_result should auto-create LinkTypeInfo."""
        result = AnalysisResult(
            repo_path="/tmp/test",
            repo_name="test-repo",
            schemas=[
                SchemaInfo(
                    name="User",
                    type=SchemaType.MODEL,
                    source_file="models/user.py",
                    fields=[FieldInfo(name="id", type="int")],
                    relationships=[
                        RelationshipRef(
                            type=RelationshipType.HAS_MANY,
                            target="Order",
                            field="orders",
                        ),
                    ],
                ),
                SchemaInfo(
                    name="Order",
                    type=SchemaType.MODEL,
                    source_file="models/order.py",
                    fields=[FieldInfo(name="id", type="int")],
                    relationships=[],
                ),
            ],
        )

        kb = KnowledgeBase(output_dir="/tmp/kb-test-links")
        kb.add_result(result)

        link_types = kb.get_all_link_types()
        assert len(link_types) == 1
        assert link_types[0]["name"] == "User__Order"
        assert link_types[0]["source_type"] == "User"
        assert link_types[0]["target_type"] == "Order"

    def test_bidirectional_edges_in_graph(self):
        """Link types should create edges in both directions."""
        result = AnalysisResult(
            repo_path="/tmp/test",
            repo_name="test-repo",
            schemas=[
                SchemaInfo(
                    name="User", type=SchemaType.MODEL,
                    source_file="m/user.py",
                    fields=[FieldInfo(name="id", type="int")],
                    relationships=[
                        RelationshipRef(type=RelationshipType.HAS_MANY, target="Order"),
                    ],
                ),
                SchemaInfo(
                    name="Order", type=SchemaType.MODEL,
                    source_file="m/order.py",
                    fields=[FieldInfo(name="id", type="int")],
                    relationships=[],
                ),
            ],
        )

        kb = KnowledgeBase(output_dir="/tmp/kb-test-bidir")
        kb.add_result(result)

        # Should be able to navigate from Order back to User
        order_nodes = kb.graph.find_by_name("Order", "schema")
        assert len(order_nodes) == 1
        incoming = kb.graph.neighbors(order_nodes[0].id, direction="incoming")
        # Should have at least one incoming edge (linked_from or links_to)
        edge_types = {e.type for e, _ in incoming}
        assert "linked_from" in edge_types or "links_to" in edge_types


# ---------------------------------------------------------------
# 2. Interfaces for cross-repo type polymorphism
# ---------------------------------------------------------------


class TestInterfaces:
    def test_compute_interfaces_cross_repo(self):
        """Schemas across repos sharing fields should produce an interface."""
        result_a = AnalysisResult(
            repo_path="/tmp/repo-a", repo_name="repo-a",
            schemas=[SchemaInfo(
                name="User", type=SchemaType.MODEL,
                source_file="models.py",
                fields=[
                    FieldInfo(name="id", type="int"),
                    FieldInfo(name="email", type="str"),
                    FieldInfo(name="created_at", type="datetime"),
                    FieldInfo(name="updated_at", type="datetime"),
                ],
                relationships=[],
            )],
        )
        result_b = AnalysisResult(
            repo_path="/tmp/repo-b", repo_name="repo-b",
            schemas=[SchemaInfo(
                name="Account", type=SchemaType.MODEL,
                source_file="models.py",
                fields=[
                    FieldInfo(name="id", type="int"),
                    FieldInfo(name="email", type="str"),
                    FieldInfo(name="created_at", type="datetime"),
                    FieldInfo(name="updated_at", type="datetime"),
                    FieldInfo(name="plan", type="str"),
                ],
                relationships=[],
            )],
        )

        kb = KnowledgeBase(output_dir="/tmp/kb-iface-test")
        kb.add_result(result_a)
        kb.add_result(result_b)

        interfaces = kb.compute_interfaces(min_shared_fields=3, min_implementors=2)
        assert len(interfaces) >= 1

        iface = interfaces[0]
        assert iface.inferred is True
        assert "User" in iface.implemented_by or "Account" in iface.implemented_by
        assert len(iface.properties) >= 3

    def test_no_interfaces_single_repo(self):
        """Schemas within the same repo should not produce interfaces."""
        result = AnalysisResult(
            repo_path="/tmp/test", repo_name="same-repo",
            schemas=[
                SchemaInfo(
                    name="A", type=SchemaType.MODEL, source_file="a.py",
                    fields=[
                        FieldInfo(name="id", type="int"),
                        FieldInfo(name="name", type="str"),
                        FieldInfo(name="created_at", type="datetime"),
                    ],
                    relationships=[],
                ),
                SchemaInfo(
                    name="B", type=SchemaType.MODEL, source_file="b.py",
                    fields=[
                        FieldInfo(name="id", type="int"),
                        FieldInfo(name="name", type="str"),
                        FieldInfo(name="created_at", type="datetime"),
                    ],
                    relationships=[],
                ),
            ],
        )

        kb = KnowledgeBase(output_dir="/tmp/kb-iface-same")
        kb.add_result(result)
        interfaces = kb.compute_interfaces(min_shared_fields=3, min_implementors=2)
        assert len(interfaces) == 0

    def test_interface_updates_schema_implements(self):
        """compute_interfaces should tag schemas with the interface name."""
        result_a = AnalysisResult(
            repo_path="/tmp/a", repo_name="a",
            schemas=[SchemaInfo(
                name="X", type=SchemaType.MODEL, source_file="x.py",
                fields=[
                    FieldInfo(name="id", type="int"),
                    FieldInfo(name="name", type="str"),
                    FieldInfo(name="created_at", type="datetime"),
                ],
                relationships=[],
            )],
        )
        result_b = AnalysisResult(
            repo_path="/tmp/b", repo_name="b",
            schemas=[SchemaInfo(
                name="Y", type=SchemaType.MODEL, source_file="y.py",
                fields=[
                    FieldInfo(name="id", type="int"),
                    FieldInfo(name="name", type="str"),
                    FieldInfo(name="created_at", type="datetime"),
                ],
                relationships=[],
            )],
        )

        kb = KnowledgeBase(output_dir="/tmp/kb-impl")
        kb.add_result(result_a)
        kb.add_result(result_b)
        ifaces = kb.compute_interfaces(min_shared_fields=3, min_implementors=2)

        # Schema data should now have the interface in 'implements'
        schemas = kb.get_all_schemas()
        for s in schemas:
            assert len(s.get("implements", [])) >= 1


# ---------------------------------------------------------------
# 3. Entity lifecycle status
# ---------------------------------------------------------------


class TestEntityStatus:
    def test_default_status_is_active(self):
        schema = SchemaInfo(
            name="Test", type=SchemaType.MODEL,
            source_file="test.py", fields=[], relationships=[],
        )
        assert schema.status == EntityStatus.ACTIVE

    def test_status_serializes_in_kb(self):
        schema = SchemaInfo(
            name="Legacy", type=SchemaType.MODEL,
            source_file="legacy.py", fields=[], relationships=[],
            status=EntityStatus.DEPRECATED,
        )
        result = AnalysisResult(
            repo_path="/tmp/test", repo_name="test",
            schemas=[schema],
        )
        kb = KnowledgeBase(output_dir="/tmp/kb-status")
        kb.add_result(result)

        found = kb.find_schema("Legacy")
        assert len(found) == 1
        assert found[0]["status"] == "deprecated"

    def test_normalize_entity_status(self):
        assert normalize_entity_status("active") == EntityStatus.ACTIVE
        assert normalize_entity_status("DEPRECATED") == EntityStatus.DEPRECATED
        assert normalize_entity_status("experimental") == EntityStatus.EXPERIMENTAL
        assert normalize_entity_status("draft") == EntityStatus.DRAFT
        assert normalize_entity_status("unknown") == EntityStatus.ACTIVE  # fallback

    def test_status_on_all_entity_types(self):
        api = APIInfo(
            path="/test", method=HTTPMethod.GET, source_file="r.py",
            handler="h", params=[], request_body=None, response=None,
            description="test", status=EntityStatus.EXPERIMENTAL,
        )
        assert api.status == EntityStatus.EXPERIMENTAL

        dep = DependencyInfo(
            name="old-lib", version="1.0", type=DependencyType.RUNTIME,
            source_file="req.txt", ecosystem=Ecosystem.PIP,
            status=EntityStatus.DEPRECATED,
        )
        assert dep.status == EntityStatus.DEPRECATED


# ---------------------------------------------------------------
# 4. Graph-queryable store
# ---------------------------------------------------------------


class TestOntologyGraph:
    def test_add_and_retrieve_nodes(self):
        g = OntologyGraph()
        g.add_node(GraphNode(id="s:1", type="schema", repo="r", data={"name": "User"}))
        g.add_node(GraphNode(id="s:2", type="schema", repo="r", data={"name": "Order"}))

        assert g.node_count == 2
        assert len(g.get_nodes_by_type("schema")) == 2

    def test_find_by_name_case_insensitive(self):
        g = OntologyGraph()
        g.add_node(GraphNode(id="s:1", type="schema", repo="r", data={"name": "User"}))

        assert len(g.find_by_name("user")) == 1
        assert len(g.find_by_name("USER")) == 1
        assert len(g.find_by_name("User")) == 1

    def test_edges_and_neighbors(self):
        g = OntologyGraph()
        g.add_node(GraphNode(id="a", type="schema", repo="r", data={"name": "A"}))
        g.add_node(GraphNode(id="b", type="schema", repo="r", data={"name": "B"}))
        g.add_edge(GraphEdge(source_id="a", target_id="b", type="links_to"))

        out = g.neighbors("a", direction="outgoing")
        assert len(out) == 1
        assert out[0][1].id == "b"

        inc = g.neighbors("b", direction="incoming")
        assert len(inc) == 1
        assert inc[0][1].id == "a"

    def test_traverse_bfs(self):
        g = OntologyGraph()
        g.add_node(GraphNode(id="a", type="s", repo="r", data={"name": "A"}))
        g.add_node(GraphNode(id="b", type="s", repo="r", data={"name": "B"}))
        g.add_node(GraphNode(id="c", type="s", repo="r", data={"name": "C"}))
        g.add_edge(GraphEdge(source_id="a", target_id="b", type="dep"))
        g.add_edge(GraphEdge(source_id="b", target_id="c", type="dep"))

        results = g.traverse("a", max_depth=3, direction="outgoing")
        reached_ids = {node.id for _, node in results}
        assert "b" in reached_ids
        assert "c" in reached_ids

    def test_traverse_respects_depth(self):
        g = OntologyGraph()
        g.add_node(GraphNode(id="a", type="s", repo="r", data={"name": "A"}))
        g.add_node(GraphNode(id="b", type="s", repo="r", data={"name": "B"}))
        g.add_node(GraphNode(id="c", type="s", repo="r", data={"name": "C"}))
        g.add_edge(GraphEdge(source_id="a", target_id="b", type="dep"))
        g.add_edge(GraphEdge(source_id="b", target_id="c", type="dep"))

        results = g.traverse("a", max_depth=1, direction="outgoing")
        reached_ids = {node.id for _, node in results}
        assert "b" in reached_ids
        assert "c" not in reached_ids

    def test_find_paths(self):
        g = OntologyGraph()
        for n in ["a", "b", "c"]:
            g.add_node(GraphNode(id=n, type="s", repo="r", data={"name": n}))
        g.add_edge(GraphEdge(source_id="a", target_id="b", type="dep"))
        g.add_edge(GraphEdge(source_id="b", target_id="c", type="dep"))

        paths = g.find_paths("a", "c")
        assert len(paths) >= 1
        assert paths[0] == ["a", "b", "c"]

    def test_remove_by_repo(self):
        g = OntologyGraph()
        g.add_node(GraphNode(id="r1:s", type="schema", repo="r1", data={"name": "A"}))
        g.add_node(GraphNode(id="r2:s", type="schema", repo="r2", data={"name": "B"}))
        g.add_edge(GraphEdge(source_id="r1:s", target_id="r2:s", type="links_to"))

        g.remove_by_repo("r1")
        assert g.node_count == 1
        assert g.get_node("r1:s") is None
        assert g.get_node("r2:s") is not None

    def test_serialize_roundtrip(self):
        g = OntologyGraph()
        g.add_node(GraphNode(id="a", type="schema", repo="r", data={"name": "A"}))
        g.add_node(GraphNode(id="b", type="schema", repo="r", data={"name": "B"}))
        g.add_edge(GraphEdge(source_id="a", target_id="b", type="links_to"))

        d = g.to_dict()
        g2 = OntologyGraph.from_dict(d)
        assert g2.node_count == 2
        assert g2.edge_count == 1
        assert len(g2.find_by_name("A")) == 1


class TestKBGraphIntegration:
    def test_graph_populated_on_add_result(self, sample_analysis_result):
        kb = KnowledgeBase(output_dir="/tmp/kb-graph")
        kb.add_result(sample_analysis_result)

        assert kb.graph.node_count > 0
        # Should have repo node + schema + api + service + dependency + link_type
        repo_nodes = kb.graph.get_nodes_by_type("repo")
        assert len(repo_nodes) == 1

    def test_service_accesses_schema_edge(self):
        result = AnalysisResult(
            repo_path="/tmp/test", repo_name="test",
            schemas=[SchemaInfo(
                name="User", type=SchemaType.MODEL, source_file="m.py",
                fields=[], relationships=[],
            )],
            business_logic=[BusinessLogicInfo(
                name="UserService", type=BusinessLogicType.SERVICE,
                source_file="s.py", description="",
                methods=[], dependencies=[], data_accessed=["User"],
            )],
        )
        kb = KnowledgeBase(output_dir="/tmp/kb-access")
        kb.add_result(result)

        svc_nodes = kb.graph.find_by_name("UserService", "service")
        assert len(svc_nodes) == 1
        neighbors = kb.graph.neighbors(svc_nodes[0].id, direction="outgoing", edge_type="accesses")
        assert len(neighbors) == 1
        assert neighbors[0][1].data["name"] == "User"

    def test_impact_analysis(self):
        result = AnalysisResult(
            repo_path="/tmp/test", repo_name="test",
            schemas=[SchemaInfo(
                name="User", type=SchemaType.MODEL, source_file="m.py",
                fields=[], relationships=[],
            )],
            business_logic=[BusinessLogicInfo(
                name="UserService", type=BusinessLogicType.SERVICE,
                source_file="s.py", description="",
                methods=[], dependencies=[], data_accessed=["User"],
            )],
        )
        kb = KnowledgeBase(output_dir="/tmp/kb-impact")
        kb.add_result(result)

        impact = kb.get_impact_analysis("User")
        assert impact["affected_count"] >= 1

    def test_save_load_preserves_graph(self, tmp_path):
        result = AnalysisResult(
            repo_path="/tmp/test", repo_name="test",
            schemas=[
                SchemaInfo(
                    name="User", type=SchemaType.MODEL, source_file="m.py",
                    fields=[FieldInfo(name="id", type="int")],
                    relationships=[
                        RelationshipRef(type=RelationshipType.HAS_MANY, target="Order"),
                    ],
                ),
                SchemaInfo(
                    name="Order", type=SchemaType.MODEL, source_file="o.py",
                    fields=[FieldInfo(name="id", type="int")],
                    relationships=[],
                ),
            ],
        )
        kb = KnowledgeBase(output_dir=str(tmp_path))
        kb.add_result(result)

        save_path = tmp_path / "kb.json"
        kb.save(save_path)

        loaded = KnowledgeBase.load(save_path)
        assert loaded.graph.node_count == kb.graph.node_count
        assert loaded.graph.edge_count == kb.graph.edge_count
        assert len(loaded.get_all_link_types()) == 1
