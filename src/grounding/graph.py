"""Knowledge graph engine — deterministic retrieval via typed entity relationships.

Graph schema
------------
MessageHouse
  ├─[HAS_SECTION]──► Section (one per section_type present in the house)
  │                    └─[CONTAINS]──► KeyMessage
  ├─[HAS_PILLAR]───► MessagingPillar (optional user grouping, orthogonal to sections)
  │                    └─[GROUPS]────► KeyMessage
  └─[TARGETS]──────► Persona
                       ├─[HAS_PAIN_POINT]──► PainPoint
                       ├─[HAS_TRIGGER]─────► BuyingTrigger
                       └─[HAS_OBJECTION]───► Objection

KeyMessage
  ├─[ADDRESSES]──► Persona
  └─[APPLIES_TO]─► Channel
"""

import logging
from typing import Any

log = logging.getLogger(__name__)

try:
    import networkx as nx
    _NX_AVAILABLE = True
except ImportError:
    _NX_AVAILABLE = False
    log.warning("networkx not installed — graph engine disabled. Run: pip install networkx")

_SECTION_LABELS: dict[str, str] = {
    "headline":            "Headlines",
    "subhead":             "Sub-headlines",
    "benefit":             "Benefits",
    "use_case":            "Use Cases",
    "proof_point":         "Proof Points",
    "objection":           "Objections",
    "social_proof":        "Social Proof",
    "positioning":         "Positioning",
    "know_your_market":    "Know Your Market",
    "brand_voice":         "Brand Voice",
    "style_rule":          "Style Rules",
    "word_list":           "Word List",
    "competitor_strength":   "Competitor Strengths",
    "competitor_weakness":   "Competitor Weaknesses",
    "competitive_response":  "Competitive Responses",
    "narrative_pillar":    "Narrative Pillars",
    "company_value":       "Company Values",
    "founding_story":      "Founding Story",
    "persona_detail":      "Persona Details",
}

_SECTION_ORDER: dict[str, int] = {
    "positioning": 0, "headline": 1, "subhead": 2, "benefit": 3,
    "use_case": 4, "proof_point": 5, "social_proof": 6, "objection": 7,
    "know_your_market": 8, "brand_voice": 9, "style_rule": 10,
    "word_list": 11, "competitor_strength": 12, "competitor_weakness": 13,
    "competitive_response": 14, "narrative_pillar": 15,
    "company_value": 16, "founding_story": 17, "persona_detail": 18,
}

_SECTION_COLORS: dict[str, str] = {
    "headline":            "#3b82f6",
    "subhead":             "#60a5fa",
    "benefit":             "#22c55e",
    "proof_point":         "#f59e0b",
    "objection":           "#ef4444",
    "social_proof":        "#a855f7",
    "positioning":         "#0ea5e9",
    "use_case":            "#14b8a6",
    "know_your_market":    "#f97316",
    "brand_voice":         "#ec4899",
    "style_rule":          "#84cc16",
    "word_list":           "#64748b",
    "competitor_strength":   "#fbbf24",
    "competitor_weakness":   "#fb923c",
    "competitive_response":  "#f43f5e",
    "narrative_pillar":    "#8b5cf6",
    "company_value":       "#06b6d4",
    "founding_story":      "#d97706",
    "persona_detail":      "#6366f1",
}

_STATUS_COLORS: dict[str, str] = {
    "approved":  "#22c55e",
    "draft":     "#9ca3af",
    "in_review": "#eab308",
    "outdated":  "#f97316",
    "locked":    "#ef4444",
}


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
        ch_meta_map = {c["id"]: c for c in store.get_channels()}

        for house in houses:
            house_node = f"house:{house.id}"
            g.add_node(house_node, type="MessageHouse",
                       id=str(house.id), name=house.name,
                       document_type=str(house.document_type),
                       tagline=getattr(house, "tagline", ""),
                       positioning=getattr(house, "positioning", ""),
                       summary=house.summary,
                       # Phase 2 additions:
                       parent_domain_id=str(house.parent_domain_id) if house.parent_domain_id else None,
                       inheritance_policy=str(house.inheritance_policy))

            # Add relationship edge to parent if linked
            if house.parent_domain_id:
                parent_node = f"house:{house.parent_domain_id}"
                g.add_edge(house_node, parent_node, rel="INHERITS_FROM")

            # Pillars — optional user-defined groupings (orthogonal to sections)
            pillars = store.list_pillars(house.id)
            pillar_map: dict[int, str] = {}
            for pillar in pillars:
                pil_node = f"pillar:{pillar.id}"
                g.add_node(pil_node, type="MessagingPillar",
                           id=str(pillar.id), name=pillar.name,
                           description=pillar.description or "",
                           house_id=str(house.id))
                g.add_edge(house_node, pil_node, rel="HAS_PILLAR")
                pillar_map[pillar.id] = pil_node

            # Personas + sub-nodes (built before messages so edges can reference them)
            for persona in store.get_personas(house.id):
                pnode = f"persona:{house.id}:{persona.name}"
                g.add_node(pnode, type="Persona", name=persona.name,
                           house_id=str(house.id),
                           description=getattr(persona, "description", ""))
                g.add_edge(house_node, pnode, rel="TARGETS")

                db_pps = store.list_pain_points(str(persona.id))
                if db_pps:
                    for pp in db_pps:
                        n = f"pain_point_db:{pp.id}"
                        g.add_node(n, type="PainPoint", id=str(pp.id), content=pp.content,
                                   persona_name=persona.name, house_id=str(house.id))
                        g.add_edge(pnode, n, rel="HAS_PAIN_POINT")
                else:
                    for i, txt in enumerate(persona.pain_points or []):
                        n = f"pain_point:{house.id}:{persona.name}:{i}"
                        g.add_node(n, type="PainPoint", id=n, content=str(txt),
                                   persona_name=persona.name, house_id=str(house.id))
                        g.add_edge(pnode, n, rel="HAS_PAIN_POINT")

                db_trigs = store.list_buying_triggers(str(persona.id))
                if db_trigs:
                    for bt in db_trigs:
                        n = f"trigger_db:{bt.id}"
                        g.add_node(n, type="BuyingTrigger", id=str(bt.id), content=bt.content,
                                   persona_name=persona.name, house_id=str(house.id))
                        g.add_edge(pnode, n, rel="HAS_TRIGGER")
                else:
                    for i, txt in enumerate(persona.buying_triggers or []):
                        n = f"trigger:{house.id}:{persona.name}:{i}"
                        g.add_node(n, type="BuyingTrigger", id=n, content=str(txt),
                                   persona_name=persona.name, house_id=str(house.id))
                        g.add_edge(pnode, n, rel="HAS_TRIGGER")

                db_obs = store.list_objections(str(persona.id))
                if db_obs:
                    for ob in db_obs:
                        n = f"objection_db:{ob.id}"
                        g.add_node(n, type="Objection", id=str(ob.id),
                                   statement=ob.statement, response=ob.response or "",
                                   persona_name=persona.name, house_id=str(house.id))
                        g.add_edge(pnode, n, rel="HAS_OBJECTION")
                else:
                    for i, ob in enumerate(persona.objections or []):
                        n = f"objection:{house.id}:{persona.name}:{i}"
                        stmt = ob.get("statement", "") if isinstance(ob, dict) else str(ob)
                        resp = ob.get("response", "") if isinstance(ob, dict) else ""
                        g.add_node(n, type="Objection", id=n, statement=stmt, response=resp,
                                   persona_name=persona.name, house_id=str(house.id))
                        g.add_edge(pnode, n, rel="HAS_OBJECTION")

            # Sections + KeyMessages
            by_section: dict[str, list] = {}
            for msg in store.get_key_messages(house.id):
                by_section.setdefault(str(msg.section_type), []).append(msg)

            for section_type, msgs in by_section.items():
                sec_node = f"section:{house.id}:{section_type}"
                label = _SECTION_LABELS.get(section_type,
                                             section_type.replace("_", " ").title())
                g.add_node(sec_node, type="Section",
                           id=sec_node, section_type=section_type, label=label,
                           house_id=str(house.id), count=len(msgs))
                g.add_edge(house_node, sec_node, rel="HAS_SECTION")

                for msg in msgs:
                    chunk_node = f"chunk:{msg.id}"
                    g.add_node(chunk_node, type="KeyMessage",
                               id=str(msg.id), content=msg.content,
                               section_type=section_type, priority=msg.priority,
                               status=getattr(msg, "status", "draft"),
                               variants=msg.variants or {})
                    g.add_edge(sec_node, chunk_node, rel="CONTAINS")

                    if msg.pillar_id and msg.pillar_id in pillar_map:
                        g.add_edge(pillar_map[msg.pillar_id], chunk_node, rel="GROUPS")

                    for persona_name in (msg.personas or []):
                        pnode = f"persona:{house.id}:{persona_name}"
                        if not g.has_node(pnode):
                            g.add_node(pnode, type="Persona", name=persona_name,
                                       house_id=str(house.id), description="")
                            g.add_edge(house_node, pnode, rel="TARGETS")
                        g.add_edge(chunk_node, pnode, rel="ADDRESSES")

                    for ch in (msg.channels or []):
                        ch_str = str(ch)
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

        self._graph = g
        self._built = True
        log.debug("Graph rebuilt: %d nodes, %d edges",
                  g.number_of_nodes(), g.number_of_edges())

    def _ensure_built(self) -> None:
        if not self._built:
            self.rebuild()

    def _house_chunk_nodes(self, house_id: str) -> set[str]:
        """All KeyMessage node IDs for a house, traversing through Section nodes."""
        house_node = f"house:{house_id}"
        chunk_nodes: set[str] = set()
        for _, sec_node, d in self._graph.out_edges(house_node, data=True):
            if d.get("rel") == "HAS_SECTION":
                for _, chunk_node, d2 in self._graph.out_edges(sec_node, data=True):
                    if d2.get("rel") == "CONTAINS":
                        chunk_nodes.add(chunk_node)
        return chunk_nodes

    def get_chunks_for_house(self, house_id: str) -> list[dict]:
        """All KeyMessages for a house, sorted by priority."""
        self._ensure_built()
        if not _NX_AVAILABLE:
            return []
        house_node = f"house:{house_id}"
        if house_node not in self._graph:
            return []
        chunks: list[dict] = []
        for _, sec_node, d in self._graph.out_edges(house_node, data=True):
            if d.get("rel") == "HAS_SECTION":
                for _, chunk_node, d2 in self._graph.out_edges(sec_node, data=True):
                    if d2.get("rel") == "CONTAINS":
                        chunks.append(dict(self._graph.nodes[chunk_node]))
        return sorted(chunks, key=lambda c: c.get("priority", 3))

    def get_sections_for_house(self, house_id: str) -> list[dict]:
        """Section nodes for a house with their KeyMessages nested, ordered by section type."""
        self._ensure_built()
        if not _NX_AVAILABLE:
            return []
        house_node = f"house:{house_id}"
        if house_node not in self._graph:
            return []
        sections: list[dict] = []
        for _, sec_node, d in self._graph.out_edges(house_node, data=True):
            if d.get("rel") == "HAS_SECTION":
                sec_attrs = dict(self._graph.nodes[sec_node])
                messages: list[dict] = []
                for _, chunk_node, d2 in self._graph.out_edges(sec_node, data=True):
                    if d2.get("rel") == "CONTAINS":
                        messages.append(dict(self._graph.nodes[chunk_node]))
                sec_attrs["messages"] = sorted(messages, key=lambda m: m.get("priority", 3))
                sections.append(sec_attrs)
        return sorted(sections,
                      key=lambda s: _SECTION_ORDER.get(s.get("section_type", ""), 99))

    def get_chunks_for_persona(self, house_id: str, persona_name: str) -> list[dict]:
        """KeyMessages that ADDRESS a specific persona within a house."""
        self._ensure_built()
        if not _NX_AVAILABLE:
            return []
        persona_node = f"persona:{house_id}:{persona_name}"
        if persona_node not in self._graph:
            return []
        return [dict(self._graph.nodes[n]) for n, _, d
                in self._graph.in_edges(persona_node, data=True)
                if d.get("rel") == "ADDRESSES"]

    def get_chunks_for_channel(self, house_id: str, channel: str) -> list[dict]:
        """KeyMessages that APPLY_TO a specific channel within a house."""
        self._ensure_built()
        if not _NX_AVAILABLE:
            return []
        channel_node = f"channel:{channel}"
        if channel_node not in self._graph:
            return []
        house_chunks = self._house_chunk_nodes(house_id)
        return [dict(self._graph.nodes[n]) for n, _, d
                in self._graph.in_edges(channel_node, data=True)
                if d.get("rel") == "APPLIES_TO" and n in house_chunks]

    def get_connections(self, house_id: str,
                        persona: str | None = None,
                        channel: str | None = None) -> list[dict]:
        """Graph query entry point — filter by optional persona and/or channel."""
        self._ensure_built()
        if not _NX_AVAILABLE:
            return []
        if persona and channel:
            by_p = {c["id"] for c in self.get_chunks_for_persona(house_id, persona)}
            by_c = {c["id"] for c in self.get_chunks_for_channel(house_id, channel)}
            ids = by_p & by_c
            results = [c for c in self.get_chunks_for_house(house_id) if c.get("id") in ids]
        elif persona:
            results = self.get_chunks_for_persona(house_id, persona)
        elif channel:
            results = self.get_chunks_for_channel(house_id, channel)
        else:
            results = self.get_chunks_for_house(house_id)
        # Filter out nodes with no content (fix #8)
        return [c for c in results if c.get("content", "").strip()]

    def get_graph_data(self) -> dict:
        """Serialise all nodes and edges for the graph explorer UI."""
        self._ensure_built()
        if not _NX_AVAILABLE:
            return {"available": False, "nodes": [], "edges": [], "rel_counts": {}}
        g = self._graph
        nodes: list[dict] = []
        for nid, attrs in g.nodes(data=True):
            ntype = attrs.get("type", "unknown")
            if ntype == "Objection":
                raw = attrs.get("statement", "") or ""
                label = (raw[:32] + "…") if len(raw) > 32 else raw or nid
            elif ntype in ("PainPoint", "BuyingTrigger"):
                raw = attrs.get("content", "") or ""
                label = (raw[:32] + "…") if len(raw) > 32 else raw or nid
            elif ntype == "Section":
                label = attrs.get("label", attrs.get("section_type", nid))
            else:
                content = attrs.get("content", "")
                label = (attrs.get("name")
                         or (content[:35] + "…" if len(content) > 35 else content)
                         or nid)
            entry: dict[str, Any] = {"id": nid, "type": ntype, "label": label}
            if ntype == "MessageHouse":
                entry.update({"name": attrs.get("name", ""),
                               "document_type": attrs.get("document_type", ""),
                               "tagline": attrs.get("tagline", ""),
                               "summary": (attrs.get("summary") or "")[:150]})
            elif ntype == "Section":
                entry.update({"section_type": attrs.get("section_type", ""),
                               "label": attrs.get("label", ""),
                               "count": attrs.get("count", 0),
                               "house_id": attrs.get("house_id", "")})
                entry["color"] = _SECTION_COLORS.get(attrs.get("section_type", ""), "#6366f1")
            elif ntype == "KeyMessage":
                entry.update({"section_type": attrs.get("section_type", ""),
                               "priority": attrs.get("priority"),
                               "content": (attrs.get("content") or "")[:150],
                               "status": attrs.get("status", "draft")})
                entry["color"] = _STATUS_COLORS.get(attrs.get("status", "draft"), "#9ca3af")
            elif ntype == "MessagingPillar":
                entry.update({"name": attrs.get("name", ""),
                               "description": attrs.get("description", ""),
                               "house_id": attrs.get("house_id", "")})
            elif ntype == "Persona":
                entry.update({"name": attrs.get("name", ""),
                               "house_id": attrs.get("house_id", "")})
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
        return {"available": True, "nodes": g.number_of_nodes(),
                "edges": g.number_of_edges(), "by_type": by_type}


_graph_engine: GraphEngine | None = None


def get_graph_engine() -> GraphEngine:
    global _graph_engine
    if _graph_engine is None:
        _graph_engine = GraphEngine()
    return _graph_engine
