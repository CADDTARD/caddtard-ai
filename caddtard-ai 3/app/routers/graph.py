import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.graph.store import PostgresGraphStore
from app.models import GraphNode
from app.schemas import GraphEdgeOut, GraphNodeOut, SubgraphOut

router = APIRouter(prefix="/api/graph", tags=["knowledge-graph"])


def _node_out(n: GraphNode) -> GraphNodeOut:
    return GraphNodeOut(id=n.id, node_type=n.node_type, label=n.label, external_ref=n.external_ref or "",
                         properties=json.loads(n.properties_json or "{}"))


@router.get("/nodes", response_model=list[GraphNodeOut])
def list_nodes(node_type: str | None = Query(None), db: Session = Depends(get_db)):
    """Layer 2 - Scientific Knowledge Graph. Node types: gene, disease,
    pathway, drug (see ARCHITECTURE.md for the full target taxonomy and the
    Neo4j upgrade path)."""
    store = PostgresGraphStore(db)
    return [_node_out(n) for n in store.nodes(node_type)]


@router.get("/nodes/{node_id}/subgraph", response_model=SubgraphOut)
def get_subgraph(node_id: int, depth: int = Query(1, ge=1, le=4), db: Session = Depends(get_db)):
    """Breadth-first subgraph around one node - e.g. a gene's disease,
    pathway, and candidate-therapeutic neighbors. Powers the pathway-map
    panel on the executive dashboard (Layer 6)."""
    store = PostgresGraphStore(db)
    node = db.get(GraphNode, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    nodes, edges = store.subgraph(node_id, depth=depth)
    return SubgraphOut(
        nodes=[_node_out(n) for n in nodes],
        edges=[
            GraphEdgeOut(id=e.id, source_id=e.source_node_id, target_id=e.target_node_id,
                         edge_type=e.edge_type, properties=json.loads(e.properties_json or "{}"))
            for e in edges
        ],
    )


@router.get("/genes/{symbol}/subgraph", response_model=SubgraphOut)
def get_gene_subgraph(symbol: str, depth: int = Query(2, ge=1, le=4), db: Session = Depends(get_db)):
    """Convenience lookup: subgraph by gene symbol instead of an internal
    node id, since that's what the dashboard and API consumers actually have."""
    store = PostgresGraphStore(db)
    node = next((n for n in store.nodes("gene") if n.label.upper() == symbol.upper()), None)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Gene node '{symbol}' not found in the graph")
    nodes, edges = store.subgraph(node.id, depth=depth)
    return SubgraphOut(
        nodes=[_node_out(n) for n in nodes],
        edges=[
            GraphEdgeOut(id=e.id, source_id=e.source_node_id, target_id=e.target_node_id,
                         edge_type=e.edge_type, properties=json.loads(e.properties_json or "{}"))
            for e in edges
        ],
    )
