"""Knowledge graph engine — deterministic retrieval via typed entity relationships."""

import logging
from typing import Any

log = logging.getLogger(__name__)

try:
    import networkx as nx
    _NX_AVAILABLE = True
except ImportError:
    _NX_AVAILABLE = False
    log.warning("networkx not installed — graph engine disabled. Run: pip install networkx")


class GraphEngine:
    def __init__(self):
        self._graph = nx.DiGraph() if _NX_AVAILABLE else None
        self._built = False

    def rebuild(self) -> None:
        if not _NX_AVAILABLE:
            return
        from src.store import get_store
        store = get_store()

        g = nx.DiGraph()
        houses = store.list_houses()

        # Cache channel metadata for efficient lookup
        ch_meta_list = store.get_channels()
        ch_meta_map = {c["id"]: c for c in ch_meta_list}

        for house in houses:
            doc_node = f"doc:{house.id}"
            g.add_node(doc_node, type="GroundingDocument",
                       id=str(house.id), name=house.name,
                       document_type=str(house.document_type),
                       summary=house.summary)

            # ── Pillars ──────────────────────────────────────────────────
            pillars = store.list_pillars(house.id)
            pillar_map = {}  # pillar_id -> node_id
            for pillar in pillars:
                pil_node = f"pillar:{pillar.id}"
                g.add_node(pil_node, type="MessagingPillar",
                           id=str(pillar.id), name=pillar.name,
                           description=pillar.description or "",
                           house_id=str(house.id))
                g.add_edge(doc_node, pil_node, rel="CONTAINS")
                pillar_map[pillar.id] = pil_node

            # ── Personas + sub-nodes (BEFORE chunks so edges can reference them) ─
            personas = store.get_personas(house.id)
            for persona in personas:
                pnode = f"persona:{house.id}:{persona.name}"
                g.add_node(pnode, type="Persona", name=persona.name,
                           house_id=str(house.id),
                           description=getattr(persona, 'description', ''))
                g.add_edge(doc_node, pnode, rel="TARGETS")

                # Phase 2g: Use DB IDs when available, otherwise fallback to JSON arrays
                db_pain_points = store.list_pain_points(str(persona.id))
                if db_pain_points:
                    for pp in db_pain_points:
                        pp_node = f"pain_point_db:{pp.id}"
                        g.add_node(pp_node, type="PainPoint",
                                   id=str(pp.id), content=pp.content,
                                   persona_name=persona.name,
                                   house_id=str(house.id))
                        g.add_edge(pnode, pp_node, rel="HAS_PAIN_POINT")
                else:
                    # Phase 1 fallback: create from JSON array with synthetic IDs
                    for i, pp_text in enumerate(persona.pain_points or []):
                        pp_node = f"pain_point:{house.id}:{persona.name}:{i}"
                        g.add_node(pp_node, type="PainPoint",
                                   id=pp_node, content=str(pp_text),
                                   persona_name=persona.name,
                                   house_id=str(house.id))
                        g.add_edge(pnode, pp_node, rel="HAS_PAIN_POINT")

                # BuyingTrigger nodes
                db_triggers = store.list_buying_triggers(str(persona.id))
                if db_triggers:
                    for bt in db_triggers:
                        tr_node = f"trigger_db:{bt.id}"
                        g.add_node(tr_node, type="BuyingTrigger",
                                   id=str(bt.id), content=bt.content,
                                   persona_name=persona.name,
                                   house_id=str(house.id))
                        g.add_edge(pnode, tr_node, rel="HAS_TRIGGER")
                else:
                    for i, tr_text in enumerate(persona.buying_triggers or []):
                        tr_node = f"trigger:{house.id}:{persona.name}:{i}"
                        g.add_node(tr_node, type="BuyingTrigger",
                                   id=tr_node, content=str(tr_text),
                                   persona_name=persona.name,
                                   house_id=str(house.id))
                        g.add_edge(pnode, tr_node, rel="HAS_TRIGGER")

                # Objection nodes - Phase 2g: DB first, then JSON fallback
                db_objections = store.list_objections(str(persona.id))
                if db_objections:
                    for ob in db_objections:
                        ob_node = f"objection_db:{ob.id}"
                        g.add_node(ob_node, type="Objection",
                                   id=str(ob.id), statement=ob.statement,
                                   response=ob.response or "",
                                   persona_name=persona.name,
                                   house_id=str(house.id))
                        g.add_edge(pnode, ob_node, rel="HAS_OBJECTION")
                else:
                    for i, ob in enumerate(persona.objections or []):
                        ob_node = f"objection:{house.id}:{persona.name}:{i}"
                        if isinstance(ob, dict):
                            statement = ob.get("statement", "")
                            response = ob.get("response", "")
                        else:
                            statement = str(ob)
                            response = ""
                        g.add_node(ob_node, type="Objection",
                                   id=ob_node, statement=statement,
                                   response=response,
                                   persona_name=persona.name,
                                   house_id=str(house.id))
                        g.add_edge(pnode, ob_node, rel="HAS_OBJECTION")

            # ── Chunks ───────────────────────────────────────────────────
            messages = store.get_key_messages(house.id)
            for msg in messages:
                chunk_node = f"chunk:{msg.id}"
                g.add_node(chunk_node, type="GroundingChunk",
                           id=str(msg.id), content=msg.content,
                           section_type=str(msg.section_type),
                           priority=msg.priority)

                if msg.pillar_id and msg.pillar_id in pillar_map:
                    g.add_edge(pillar_map[msg.pillar_id], chunk_node, rel="CONTAINS")
                else:
                    g.add_edge(doc_node, chunk_node, rel="CONTAINS")

                for persona_name in (msg.personas or []):
                    pnode = f"persona:{house.id}:{persona_name}"
                    if not g.has_node(pnode):
                        g.add_node(pnode, type="Persona", name=persona_name,
                                   house_id=str(house.id))
                        g.add_edge(doc_node, pnode, rel="TARGETS")
                    g.add_edge(chunk_node, pnode, rel="ADDRESSES")

                for channel in (msg.channels or []):
                    ch_str = str(channel)
                    cnode = f"channel:{ch_str}"
                    if not g.has_node(cnode):
                        meta = ch_meta_map.get(ch_str)
                        if meta:
                            g.add_node(cnode, type="Channel", name=meta["name"],
                                       description=meta.get("description", ""),
                                       is_custom=meta.get("is_custom", True))
                        else:
                            g.add_node(cnode, type="Channel", name=ch_str,
                                       description="", is_custom=True)
                    g.add_edge(chunk_node, cnode, rel="APPLIES_TO")

                # Phase 2: edges to pain points and objections
                for pp_id in (getattr(msg, 'pain_point_ids', None) or []):
                    pp_node = f"pain_point_db:{pp_id}"
                    if g.has_node(pp_node):
                        g.add_edge(chunk_node, pp_node, rel="ADDRESSES")

                for ob_id in (getattr(msg, 'objection_ids', None) or []):
                    ob_node = f"objection_db:{ob_id}"
                    if g.has_node(ob_node):
                        g.add_edge(chunk_node, ob_node, rel="RESOLVES")

        self._graph = g
        self._built = True
        log.debug("Graph rebuilt: %d nodes, %d edges", g.number_of_nodes(), g.number_of_edges())

    def _ensure_built(self) -> None:
        if not self._built:
            self.rebuild()

    def get_chunks_for_house(self, house_id: str) -> list[dict]:
        """Deterministic: all chunks for a house via graph traversal, sorted by priority."""
        self._ensure_built()
        if not _NX_AVAILABLE:
            return []
        doc_node = f"doc:{house_id}"
        if doc_node not in self._graph:
            return []
        chunks = []
        for _, chunk_node, data in self._graph.out_edges(doc_node, data=True):
            if data.get("rel") == "CONTAINS":
                attrs = dict(self._graph.nodes[chunk_node])
                chunks.append(attrs)
        return sorted(chunks, key=lambda c: c.get("priority", 3))

    def get_chunks_for_persona(self, house_id: str, persona_name: str) -> list[dict]:
        """Return chunks that ADDRESS a specific persona within a house."""
        self._ensure_built()
        if not _NX_AVAILABLE:
            return []
        persona_node = f"persona:{house_id}:{persona_name}"
        if persona_node not in self._graph:
            return []
        chunks = []
        for chunk_node, _, data in self._graph.in_edges(persona_node, data=True):
            if data.get("rel") == "ADDRESSES":
                attrs = dict(self._graph.nodes[chunk_node])
                chunks.append(attrs)
        return chunks

    def get_chunks_for_channel(self, house_id: str, channel: str) -> list[dict]:
        """Return chunks that APPLY_TO a specific channel within a house."""
        self._ensure_built()
        if not _NX_AVAILABLE:
            return []
        channel_node = f"channel:{channel}"
        doc_node = f"doc:{house_id}"
        if channel_node not in self._graph or doc_node not in self._graph:
            return []
        doc_chunks = {
            n for _, n, d in self._graph.out_edges(doc_node, data=True)
            if d.get("rel") == "CONTAINS"
        }
        chunks = []
        for chunk_node, _, data in self._graph.in_edges(channel_node, data=True):
            if data.get("rel") == "APPLIES_TO" and chunk_node in doc_chunks:
                attrs = dict(self._graph.nodes[chunk_node])
                chunks.append(attrs)
        return chunks

    def get_connections(self, house_id: str,
                        persona: str | None = None,
                        channel: str | None = None) -> list[dict]:
        """Graph query entry point — filters by optional persona and/or channel."""
        self._ensure_built()
        if not _NX_AVAILABLE:
            return []
        if persona and channel:
            by_persona = {c["id"] for c in self.get_chunks_for_persona(house_id, persona)}
            by_channel = {c["id"] for c in self.get_chunks_for_channel(house_id, channel)}
            ids = by_persona & by_channel
            all_chunks = self.get_chunks_for_house(house_id)
            return [c for c in all_chunks if c.get("id") in ids]
        if persona:
            return self.get_chunks_for_persona(house_id, persona)
        if channel:
            return self.get_chunks_for_channel(house_id, channel)
        return self.get_chunks_for_house(house_id)

    def get_graph_data(self) -> dict:
        """Serialize all nodes and edges for the graph explorer UI."""
        self._ensure_built()
        if not _NX_AVAILABLE:
            return {"available": False, "nodes": [], "edges": [], "rel_counts": {}}
        g = self._graph

        # Status → color map for GroundingChunk nodes
        _STATUS_COLORS = {
            "approved": "#22c55e",   # green
            "draft": "#9ca3af",      # gray
            "in_review": "#eab308",   # yellow/amber
            "outdated": "#f97316",    # orange
            "locked": "#ef4444",      # red
        }

        nodes = []
        for nid, attrs in g.nodes(data=True):
            ntype = attrs.get("type", "unknown")
            content = attrs.get("content", "")
            # Custom label logic for different node types
            if ntype == "Objection":
                raw = attrs.get("statement", "") or ""
                label = (raw[:32] + "…") if len(raw) > 32 else raw or nid
            elif ntype in ("PainPoint", "BuyingTrigger"):
                raw = attrs.get("content", "") or ""
                label = (raw[:32] + "…") if len(raw) > 32 else raw or nid
            else:
                label = attrs.get("name") or (content[:35] + "…" if len(content) > 35 else content) or nid
            entry: dict[str, Any] = {"id": nid, "type": ntype, "label": label}
            if ntype == "GroundingDocument":
                entry.update({"name": attrs.get("name", ""),
                               "document_type": attrs.get("document_type", ""),
                               "summary": (attrs.get("summary") or "")[:150]})
            elif ntype == "MessagingPillar":
                entry.update({"name": attrs.get("name", ""),
                               "description": attrs.get("description", ""),
                               "house_id": attrs.get("house_id", "")})
            elif ntype == "GroundingChunk":
                entry.update({"section_type": attrs.get("section_type", ""),
                               "priority": attrs.get("priority"),
                               "content": (attrs.get("content") or "")[:150],
                               "status": attrs.get("status", "draft")})
                # Color-code by status
                status = attrs.get("status", "draft")
                entry["color"] = _STATUS_COLORS.get(status, "#9ca3af")
            elif ntype == "Persona":
                entry.update({"name": attrs.get("name", ""), "house_id": attrs.get("house_id", "")})
            elif ntype == "Channel":
                entry["name"] = attrs.get("name", "")
            elif ntype == "PainPoint":
                entry.update({"content": (attrs.get("content") or "")[:150],
                              "persona_name": attrs.get("persona_name", ""),
                              "house_id": attrs.get("house_id", "")})
            elif ntype == "BuyingTrigger":
                entry.update({"content": (attrs.get("content") or "")[:150],
                              "persona_name": attrs.get("persona_name", ""),
                              "house_id": attrs.get("house_id", "")})
            elif ntype == "Objection":
                entry.update({"statement": (attrs.get("statement") or "")[:150],
                              "response": (attrs.get("response") or "")[:150],
                              "persona_name": attrs.get("persona_name", ""),
                              "house_id": attrs.get("house_id", "")})
            nodes.append(entry)
        edges = [{"source": s, "target": t, "rel": d.get("rel", "")}
                 for s, t, d in g.edges(data=True)]
        rel_counts: dict[str, int] = {}
        for e in edges:
            rel_counts[e["rel"]] = rel_counts.get(e["rel"], 0) + 1
        return {"available": True, "nodes": nodes, "edges": edges, "rel_counts": rel_counts}

    def get_stats(self) -> dict:
        """Graph statistics for the dashboard widget."""
        self._ensure_built()
        if not _NX_AVAILABLE:
            return {"available": False, "reason": "networkx not installed"}
        g = self._graph
        by_type: dict[str, int] = {}
        for _, attrs in g.nodes(data=True):
            t = attrs.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
        return {
            "available": True,
            "nodes": g.number_of_nodes(),
            "edges": g.number_of_edges(),
            "by_type": by_type,
        }


_graph_engine: GraphEngine | None = None


def get_graph_engine() -> GraphEngine:
    global _graph_engine
    if _graph_engine is None:
        _graph_engine = GraphEngine()
    return _graph_engine
