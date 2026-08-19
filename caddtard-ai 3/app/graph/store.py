"""
GraphStore: the interface the API talks to for Layer 2 (Scientific Knowledge
Graph). PostgresGraphStore is the v1/v2 implementation, backed by the
graph_nodes/graph_edges tables in models.py, so the whole graph layer works
against the same SQLite/Postgres database as everything else with no extra
infrastructure.

Documented upgrade path: a Neo4jGraphStore implementing this same interface
(get_node, upsert_node, upsert_edge, neighbors, subgraph) would let the API
and frontend switch to a native graph database without any router or
JavaScript changes - see ARCHITECTURE.md. docker-compose.yml already
provisions a `neo4j` service behind the `extended` profile
(`docker compose --profile extended up`) for when that adapter is written;
it isn't wired to the app in this version.
"""
import json
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GraphEdge, GraphNode


@dataclass
class NodeView:
    id: int
    node_type: str
    label: str
    external_ref: str
    properties: dict = field(default_factory=dict)


@dataclass
class EdgeView:
    id: int
    source_id: int
    target_id: int
    edge_type: str
    properties: dict = field(default_factory=dict)


class PostgresGraphStore:
    def __init__(self, db: Session):
        self.db = db

    def upsert_node(self, node_type: str, label: str, external_ref: str = "", properties: dict | None = None) -> GraphNode:
        # Normalize "" -> None: the uq_node_type_ref unique constraint on
        # (node_type, external_ref) must not treat two different nodes with
        # no external ref yet as duplicates. SQL enforces uniqueness on NULL
        # as "distinct from every other NULL", so this keeps unref'd nodes
        # (e.g. internally-tracked drug candidates) independently insertable.
        external_ref = external_ref or None
        existing = self.db.scalar(
            select(GraphNode).where(GraphNode.node_type == node_type, GraphNode.external_ref == external_ref)
        ) if external_ref else None
        if existing:
            existing.label = label
            existing.properties_json = json.dumps(properties or {})
            existing.version += 1
            node = existing
        else:
            node = GraphNode(
                node_type=node_type,
                label=label,
                external_ref=external_ref,
                properties_json=json.dumps(properties or {}),
            )
            self.db.add(node)
        self.db.flush()
        return node

    def upsert_edge(self, source_id: int, target_id: int, edge_type: str, properties: dict | None = None) -> GraphEdge:
        existing = self.db.scalar(
            select(GraphEdge).where(
                GraphEdge.source_node_id == source_id,
                GraphEdge.target_node_id == target_id,
                GraphEdge.edge_type == edge_type,
            )
        )
        if existing:
            existing.properties_json = json.dumps(properties or {})
            existing.version += 1
            edge = existing
        else:
            edge = GraphEdge(
                source_node_id=source_id,
                target_node_id=target_id,
                edge_type=edge_type,
                properties_json=json.dumps(properties or {}),
            )
            self.db.add(edge)
        self.db.flush()
        return edge

    def nodes(self, node_type: str | None = None) -> list[GraphNode]:
        stmt = select(GraphNode)
        if node_type:
            stmt = stmt.where(GraphNode.node_type == node_type)
        return list(self.db.scalars(stmt).all())

    def neighbors(self, node_id: int) -> list[GraphEdge]:
        stmt = select(GraphEdge).where(
            (GraphEdge.source_node_id == node_id) | (GraphEdge.target_node_id == node_id)
        )
        return list(self.db.scalars(stmt).all())

    def subgraph(self, node_id: int, depth: int = 1) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Breadth-first traversal to `depth` hops from node_id. Kept simple
        (Python-side BFS over per-hop SQL queries) rather than a recursive CTE
        so it behaves identically on SQLite and Postgres."""
        visited_node_ids = {node_id}
        frontier = {node_id}
        collected_edges: dict[int, GraphEdge] = {}

        for _ in range(max(depth, 1)):
            if not frontier:
                break
            stmt = select(GraphEdge).where(
                (GraphEdge.source_node_id.in_(frontier)) | (GraphEdge.target_node_id.in_(frontier))
            )
            next_frontier = set()
            for edge in self.db.scalars(stmt).all():
                collected_edges[edge.id] = edge
                for nid in (edge.source_node_id, edge.target_node_id):
                    if nid not in visited_node_ids:
                        next_frontier.add(nid)
                        visited_node_ids.add(nid)
            frontier = next_frontier

        nodes = list(self.db.scalars(select(GraphNode).where(GraphNode.id.in_(visited_node_ids))).all())
        return nodes, list(collected_edges.values())
