"""Graph-queryable store for ontology entities and relationships.

Replaces the flat dict-of-lists indexes in KnowledgeBase with a graph
structure supporting bidirectional traversal, path finding, and subgraph
extraction.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphNode:
    """A node in the ontology graph."""
    id: str
    type: str  # "schema", "api", "service", "dependency", "link_type", "interface", "repo"
    repo: str
    data: dict[str, Any]


@dataclass
class GraphEdge:
    """A directed edge in the ontology graph."""
    source_id: str
    target_id: str
    type: str  # "contains", "links_to", "depends_on", "implements", "accesses"
    properties: dict[str, Any] = field(default_factory=dict)


class OntologyGraph:
    """Graph store with traversal queries over ontology entities.

    Nodes represent ontology entities (schemas, APIs, services, etc.).
    Edges represent relationships (contains, links_to, depends_on, etc.).
    Both outgoing and incoming edges are indexed for bidirectional traversal.
    """

    def __init__(self):
        self._nodes: dict[str, GraphNode] = {}
        self._outgoing: dict[str, list[GraphEdge]] = {}
        self._incoming: dict[str, list[GraphEdge]] = {}
        self._type_index: dict[str, set[str]] = {}
        self._name_index: dict[str, set[str]] = {}  # lowered name -> node_ids
        self._repo_index: dict[str, set[str]] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_node(self, node: GraphNode) -> None:
        """Add or replace a node."""
        self._nodes[node.id] = node
        self._type_index.setdefault(node.type, set()).add(node.id)

        name = node.data.get("name", "")
        if name:
            self._name_index.setdefault(name.lower(), set()).add(node.id)

        if node.repo:
            self._repo_index.setdefault(node.repo, set()).add(node.id)

        self._outgoing.setdefault(node.id, [])
        self._incoming.setdefault(node.id, [])

    def add_edge(self, edge: GraphEdge) -> None:
        """Add a directed edge between two nodes."""
        self._outgoing.setdefault(edge.source_id, []).append(edge)
        self._incoming.setdefault(edge.target_id, []).append(edge)

    def remove_by_repo(self, repo: str) -> None:
        """Remove all nodes and their edges for a given repository."""
        node_ids = list(self._repo_index.get(repo, set()))
        for node_id in node_ids:
            self._remove_node(node_id)
        self._repo_index.pop(repo, None)

    def _remove_node(self, node_id: str) -> None:
        node = self._nodes.pop(node_id, None)
        if not node:
            return

        if node.type in self._type_index:
            self._type_index[node.type].discard(node_id)
        name = node.data.get("name", "")
        if name and name.lower() in self._name_index:
            self._name_index[name.lower()].discard(node_id)
            if not self._name_index[name.lower()]:
                del self._name_index[name.lower()]
        if node.repo and node.repo in self._repo_index:
            self._repo_index[node.repo].discard(node_id)

        for edge in self._outgoing.pop(node_id, []):
            if edge.target_id in self._incoming:
                self._incoming[edge.target_id] = [
                    e for e in self._incoming[edge.target_id]
                    if e.source_id != node_id
                ]
        for edge in self._incoming.pop(node_id, []):
            if edge.source_id in self._outgoing:
                self._outgoing[edge.source_id] = [
                    e for e in self._outgoing[edge.source_id]
                    if e.target_id != node_id
                ]

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> GraphNode | None:
        return self._nodes.get(node_id)

    def get_nodes_by_type(self, node_type: str) -> list[GraphNode]:
        return [
            self._nodes[nid]
            for nid in self._type_index.get(node_type, set())
            if nid in self._nodes
        ]

    def find_by_name(
        self, name: str, node_type: str | None = None,
    ) -> list[GraphNode]:
        """Case-insensitive exact name match."""
        ids = self._name_index.get(name.lower(), set())
        nodes = [self._nodes[nid] for nid in ids if nid in self._nodes]
        if node_type:
            nodes = [n for n in nodes if n.type == node_type]
        return nodes

    def find_by_name_substring(
        self, substring: str, node_type: str | None = None,
    ) -> list[GraphNode]:
        """Case-insensitive substring match on node names."""
        sub = substring.lower()
        results: list[GraphNode] = []
        for name_key, ids in self._name_index.items():
            if sub in name_key:
                for nid in ids:
                    node = self._nodes.get(nid)
                    if node and (node_type is None or node.type == node_type):
                        results.append(node)
        return results

    def get_nodes_by_repo(self, repo: str) -> list[GraphNode]:
        return [
            self._nodes[nid]
            for nid in self._repo_index.get(repo, set())
            if nid in self._nodes
        ]

    # ------------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------------

    def neighbors(
        self,
        node_id: str,
        direction: str = "both",
        edge_type: str | None = None,
    ) -> list[tuple[GraphEdge, GraphNode]]:
        """Return (edge, neighbor_node) pairs for a given node."""
        results: list[tuple[GraphEdge, GraphNode]] = []

        if direction in ("outgoing", "both"):
            for edge in self._outgoing.get(node_id, []):
                if edge_type and edge.type != edge_type:
                    continue
                node = self._nodes.get(edge.target_id)
                if node:
                    results.append((edge, node))

        if direction in ("incoming", "both"):
            for edge in self._incoming.get(node_id, []):
                if edge_type and edge.type != edge_type:
                    continue
                node = self._nodes.get(edge.source_id)
                if node:
                    results.append((edge, node))

        return results

    def traverse(
        self,
        start_id: str,
        max_depth: int = 3,
        direction: str = "outgoing",
        edge_types: set[str] | None = None,
    ) -> list[tuple[list[str], GraphNode]]:
        """BFS traversal returning ``(path, node)`` for each reachable node.

        ``path`` is the list of node IDs from *start* to the reached node.
        """
        if start_id not in self._nodes:
            return []

        visited: set[str] = {start_id}
        queue: deque[tuple[list[str], str]] = deque([([start_id], start_id)])
        results: list[tuple[list[str], GraphNode]] = []

        while queue:
            path, current_id = queue.popleft()
            if len(path) > max_depth + 1:
                continue

            if current_id != start_id:
                node = self._nodes.get(current_id)
                if node:
                    results.append((list(path), node))

            edges: list[GraphEdge] = []
            if direction in ("outgoing", "both"):
                edges.extend(self._outgoing.get(current_id, []))
            if direction in ("incoming", "both"):
                edges.extend(self._incoming.get(current_id, []))

            for edge in edges:
                next_id = (
                    edge.target_id
                    if edge.source_id == current_id
                    else edge.source_id
                )
                if next_id in visited:
                    continue
                if edge_types and edge.type not in edge_types:
                    continue
                visited.add(next_id)
                queue.append((path + [next_id], next_id))

        return results

    def find_paths(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
    ) -> list[list[str]]:
        """Find all simple paths between two nodes (BFS)."""
        if source_id not in self._nodes or target_id not in self._nodes:
            return []

        paths: list[list[str]] = []
        queue: deque[list[str]] = deque([[source_id]])

        while queue:
            path = queue.popleft()
            if len(path) > max_depth + 1:
                continue

            current = path[-1]
            if current == target_id and len(path) > 1:
                paths.append(path)
                continue

            for edge in self._outgoing.get(current, []):
                if edge.target_id not in path:
                    queue.append(path + [edge.target_id])
            for edge in self._incoming.get(current, []):
                if edge.source_id not in path:
                    queue.append(path + [edge.source_id])

        return paths

    # ------------------------------------------------------------------
    # Stats & serialization
    # ------------------------------------------------------------------

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return sum(len(edges) for edges in self._outgoing.values())

    def to_dict(self) -> dict[str, Any]:
        """Serialize graph to a JSON-safe dict."""
        return {
            "nodes": [
                {"id": n.id, "type": n.type, "repo": n.repo, "data": n.data}
                for n in self._nodes.values()
            ],
            "edges": [
                {
                    "source_id": e.source_id,
                    "target_id": e.target_id,
                    "type": e.type,
                    "properties": e.properties,
                }
                for edges in self._outgoing.values()
                for e in edges
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OntologyGraph:
        """Reconstruct graph from a serialized dict."""
        graph = cls()
        for n in data.get("nodes", []):
            graph.add_node(GraphNode(
                id=n["id"], type=n["type"], repo=n["repo"], data=n["data"],
            ))
        for e in data.get("edges", []):
            graph.add_edge(GraphEdge(
                source_id=e["source_id"],
                target_id=e["target_id"],
                type=e["type"],
                properties=e.get("properties", {}),
            ))
        return graph
