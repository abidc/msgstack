"""Knowledge graph engine — deterministic retrieval via typed entity relationships.

Graph schema
------------
CanonDomain
  ├─[HAS_SECTION]──► Section (one per section_type present in the canon_domain)
  │                    └─[CONTAINS]──► CanonEntry
  ├─[HAS_PILLAR]───► Pillar (optional user grouping, orthogonal to sections)
  │                    └─[GROUPS]────► CanonEntry
  └─[TARGETS]──────► Persona
                       └─[HAS_QA_PAIR]───► Objection

CanonEntry
  ├─[ADDRESSES]──► Persona
  ├─[APPLIES_TO]─► Channel
  └─[MENTIONS]───► Entity        ← crosses canon_domain boundaries

Typed cross-canon_domain edges (DEPENDS_ON, INFORMS, SUPERSEDES, CONTRADICTS, OWNS,
IMPLEMENTS) connect any two nodes and are loaded from the `edges` table.
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
    "constraint":          "Constraints",
    "sla":                 "SLAs",
    "deprecation":         "Deprecations",
    "config_default":      "Config Defaults",
    "dependency":          "Dependencies",
    "capability":          "Capabilities",
    "limitation":          "Limitations",
    "security_posture":    "Security Posture",
    "interface_contract":  "Interface Contracts",
    "version_policy":      "Version Policy",
    "runbook_step":        "Runbook Steps",
    "decision":            "Decisions",
    "positioning":         "Positioning",
    "source_markdown":     "Source Document",
}

_SECTION_ORDER: dict[str, int] = {
    "positioning": 0, "capability": 1, "interface_contract": 2,
    "constraint": 3, "sla": 4, "dependency": 5, "config_default": 6,
    "limitation": 7, "security_posture": 8, "version_policy": 9,
    "deprecation": 10, "decision": 11, "runbook_step": 12,
    "source_markdown": 13,
}

_SECTION_COLORS: dict[str, str] = {
    "constraint":          "#f59e0b",
    "sla":                 "#22c55e",
    "deprecation":         "#ef4444",
    "config_default":      "#64748b",
    "dependency":          "#8b5cf6",
    "capability":          "#3b82f6",
    "limitation":          "#fb923c",
    "security_posture":    "#14b8a6",
    "interface_contract":  "#0ea5e9",
    "version_policy":      "#a855f7",
    "runbook_step":        "#84cc16",
    "decision":            "#ec4899",
    "positioning":         "#6366f1",
    "source_markdown":     "#9ca3af",
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
        canon_domains = store.list_canon_domains()
        ch_meta_map = {c["id"]: c for c in store.get_channels()}

        for canon_domain in canon_domains:
            spec_node = f"canon_domain:{canon_domain.id}"
            g.add_node(spec_node, type="CanonDomain",
                       id=str(canon_domain.id), name=canon_domain.name,
                       grounding_type=str(canon_domain.grounding_type),
                       tagline=getattr(canon_domain, "tagline", ""),
                       positioning=getattr(canon_domain, "positioning", ""),
                       summary=canon_domain.summary,
                       # Phase 2 additions:
                       parent_domain_id=str(canon_domain.parent_domain_id) if canon_domain.parent_domain_id else None,
                       inheritance_policy=str(canon_domain.inheritance_policy))

            # Add relationship edge to parent if linked
            if canon_domain.parent_domain_id:
                parent_node = f"canon_domain:{canon_domain.parent_domain_id}"
                g.add_edge(spec_node, parent_node, rel="INHERITS_FROM")

            # Pillars — optional user-defined groupings (orthogonal to sections)
            pillars = store.list_pillars(canon_domain.id)
            pillar_map: dict[int, str] = {}
            for pillar in pillars:
                pil_node = f"pillar:{pillar.id}"
                g.add_node(pil_node, type="Pillar",
                           id=str(pillar.id), name=pillar.name,
                           description=pillar.description or "",
                           canon_domain_id=str(canon_domain.id))
                g.add_edge(spec_node, pil_node, rel="HAS_PILLAR")
                pillar_map[pillar.id] = pil_node

            # Audiences + their QA pairs (built before canon_entries so edges resolve)
            for persona in store.get_personas(canon_domain.id):
                pnode = f"persona:{canon_domain.id}:{persona.name}"
                g.add_node(pnode, type="Persona", name=persona.name,
                           canon_domain_id=str(canon_domain.id),
                           description=getattr(persona, "description", ""))
                g.add_edge(spec_node, pnode, rel="TARGETS")

                db_obs = store.list_objections(str(persona.id))
                if db_obs:
                    for ob in db_obs:
                        n = f"qa_pair_db:{ob.id}"
                        g.add_node(n, type="Objection", id=str(ob.id),
                                   statement=ob.statement, response=ob.response or "",
                                   audience_name=persona.name, canon_domain_id=str(canon_domain.id))
                        g.add_edge(pnode, n, rel="HAS_QA_PAIR")
                else:
                    for i, ob in enumerate(persona.objections or []):
                        n = f"objection:{canon_domain.id}:{persona.name}:{i}"
                        stmt = ob.get("statement", "") if isinstance(ob, dict) else str(ob)
                        resp = ob.get("response", "") if isinstance(ob, dict) else ""
                        g.add_node(n, type="Objection", id=n, statement=stmt, response=resp,
                                   audience_name=persona.name, canon_domain_id=str(canon_domain.id))
                        g.add_edge(pnode, n, rel="HAS_QA_PAIR")

            # Sections + KeyMessages
            by_section: dict[str, list] = {}
            for msg in store.get_key_messages(canon_domain.id):
                by_section.setdefault(str(msg.section_type), []).append(msg)

            for section_type, msgs in by_section.items():
                sec_node = f"section:{canon_domain.id}:{section_type}"
                label = _SECTION_LABELS.get(section_type,
                                             section_type.replace("_", " ").title())
                g.add_node(sec_node, type="Section",
                           id=sec_node, section_type=section_type, label=label,
                           canon_domain_id=str(canon_domain.id), count=len(msgs))
                g.add_edge(spec_node, sec_node, rel="HAS_SECTION")

                for msg in msgs:
                    chunk_node = f"chunk:{msg.id}"
                    g.add_node(chunk_node, type="CanonEntry",
                               id=str(msg.id), content=msg.content,
                               section_type=section_type, priority=msg.priority,
                               status=getattr(msg, "status", "draft"),
                               variants=msg.variants or {})
                    g.add_edge(sec_node, chunk_node, rel="CONTAINS")

                    if msg.pillar_id and msg.pillar_id in pillar_map:
                        g.add_edge(pillar_map[msg.pillar_id], chunk_node, rel="GROUPS")

                    for audience_name in (msg.personas or []):
                        pnode = f"persona:{canon_domain.id}:{audience_name}"
                        if not g.has_node(pnode):
                            g.add_node(pnode, type="Persona", name=audience_name,
                                       canon_domain_id=str(canon_domain.id), description="")
                            g.add_edge(spec_node, pnode, rel="TARGETS")
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

        # ── Entities + typed edges ───────────────────────────────────────
        # Everything above is containment: each edge stays inside one canon_domain.
        # These two loops are what make the structure an actual graph — entity
        # nodes join canon_entries across canon_domains, and typed edges express explicit
        # cross-canon_domain relationships.
        for ent in store.list_entities():
            g.add_node(f"entity:{ent['id']}", type="Entity",
                       id=ent["id"], name=ent["name"],
                       entity_type=ent["entity_type"],
                       description=ent.get("description", ""),
                       aliases=ent.get("aliases", []))

        for m in store.list_entity_mentions():
            a_node, e_node = f"chunk:{m['canon_entry_id']}", f"entity:{m['entity_id']}"
            if g.has_node(a_node) and g.has_node(e_node):
                g.add_edge(a_node, e_node, rel="MENTIONS", confidence=m.get("confidence", 1.0))

        _PREFIX = {"canon_entry": "chunk:", "canon_domain": "canon_domain:", "entity": "entity:"}
        for e in store.list_edges():
            src = _PREFIX.get(e["src_type"], "") + e["src_id"]
            dst = _PREFIX.get(e["dst_type"], "") + e["dst_id"]
            if g.has_node(src) and g.has_node(dst):
                g.add_edge(src, dst, rel=e["rel_type"],
                           confidence=e.get("confidence", 1.0),
                           edge_id=e["id"], provenance=e.get("provenance", ""))

        self._graph = g
        self._built = True
        log.debug("Graph rebuilt: %d nodes, %d edges",
                  g.number_of_nodes(), g.number_of_edges())

    def _ensure_built(self) -> None:
        if not self._built:
            self.rebuild()

    def _spec_chunk_nodes(self, canon_domain_id: str) -> set[str]:
        """All CanonEntry node IDs for a canon_domain, traversing through Section nodes."""
        spec_node = f"canon_domain:{canon_domain_id}"
        chunk_nodes: set[str] = set()
        for _, sec_node, d in self._graph.out_edges(spec_node, data=True):
            if d.get("rel") == "HAS_SECTION":
                for _, chunk_node, d2 in self._graph.out_edges(sec_node, data=True):
                    if d2.get("rel") == "CONTAINS":
                        chunk_nodes.add(chunk_node)
        return chunk_nodes

    # ── Traversal ────────────────────────────────────────────────────────
    #: Edges worth walking during retrieval expansion, and what a hop costs.
    #: Lower decay = the relationship carries less relevance across the hop.
    _TRAVERSAL_DECAY: dict[str, float] = {
        "MENTIONS": 0.75,      # canon_entry -> entity: the cross-canon_domain bridge
        "DEPENDS_ON": 0.85,
        "INFORMS": 0.80,
        "IMPLEMENTS": 0.75,
        "SUPERSEDES": 0.90,
        "CONTRADICTS": 0.85,   # a contradiction is highly relevant to surface
        "OWNS": 0.60,
        "GROUPS": 0.50,
        "INHERITS_FROM": 0.70,
        "ADDRESSES": 0.55,
    }

    #: Relationships never walked during retrieval. APPLIES_TO connects every
    #: canon_entry to the channel it publishes on, and almost everything carries
    #: channel "all" — so traversing it makes every canon_entry two hops from
    #: every other one and the graph degenerates into a complete graph.
    #: CONTAINS is the Section containment edge and has the same problem within
    #: a canon_domain. Both remain in the graph for structural queries; they are simply
    #: not paths for relevance.
    _NON_TRAVERSABLE: frozenset = frozenset({"APPLIES_TO", "CONTAINS", "HAS_SECTION"})

    #: A node connected to more than this many others is a hub, not a
    #: relationship. Traversal may *reach* it but never continues *through* it.
    #: Guards against any future node type acquiring hub-like degree.
    _HUB_DEGREE = 25

    def _is_hub(self, node: str) -> bool:
        return (self._graph.in_degree(node) + self._graph.out_degree(node)) > self._HUB_DEGREE

    def expand(
        self,
        seed_assertion_ids: list[str],
        hops: int = 2,
        rel_types: list[str] | None = None,
        min_weight: float = 0.15,
        limit: int = 50,
    ) -> list[dict]:
        """Breadth-first k-hop expansion from seed canon_entries.

        Walks edges in both directions — a dependency is relevant read either
        way — decaying a path weight per hop by relationship type. Returns
        canon_entry nodes only (entities are waypoints, not results), each with
        the weight and the path that reached it, best first.

        This is the traversal the previous `graph` retrieval mode claimed to do
        and did not: it filtered chunks by canon_domain id and never left the canon_domain.
        """
        self._ensure_built()
        if not _NX_AVAILABLE or self._graph is None:
            return []

        allowed = set(rel_types) if rel_types else None
        g = self._graph
        seeds = [f"chunk:{a}" for a in seed_assertion_ids]

        best: dict[str, float] = {}
        path_to: dict[str, list[str]] = {}
        frontier: list[tuple[str, float, list[str]]] = []
        for s in seeds:
            if g.has_node(s):
                best[s] = 1.0
                path_to[s] = []
                frontier.append((s, 1.0, []))

        for _ in range(max(0, hops)):
            nxt: list[tuple[str, float, list[str]]] = []
            for node, weight, path in frontier:
                # Stop at hubs: reaching one is fine, continuing through it
                # would connect every node to every other node.
                if path and self._is_hub(node):
                    continue
                neighbours = (
                    [(v, d, "out") for _, v, d in g.out_edges(node, data=True)]
                    + [(u, d, "in") for u, _, d in g.in_edges(node, data=True)]
                )
                for other, data, direction in neighbours:
                    rel = data.get("rel", "")
                    if rel in self._NON_TRAVERSABLE:
                        continue
                    if allowed is not None and rel not in allowed:
                        continue
                    decay = self._TRAVERSAL_DECAY.get(rel, 0.4)
                    w = weight * decay * float(data.get("confidence", 1.0))
                    if w < min_weight or w <= best.get(other, 0.0):
                        continue
                    best[other] = w
                    arrow = "->" if direction == "out" else "<-"
                    path_to[other] = path + [f"{arrow}{rel}"]
                    nxt.append((other, w, path_to[other]))
            if not nxt:
                break
            frontier = nxt

        out: list[dict] = []
        seed_set = set(seeds)
        for node, weight in best.items():
            if node in seed_set or not node.startswith("chunk:"):
                continue
            attrs = dict(g.nodes[node])
            attrs["graph_weight"] = round(weight, 4)
            attrs["graph_path"] = path_to.get(node, [])
            attrs["hops"] = len(path_to.get(node, []))
            out.append(attrs)

        out.sort(key=lambda a: a["graph_weight"], reverse=True)
        return out[:limit]

    def neighbours(self, node_type: str, node_id: str) -> dict:
        """Immediate typed neighbourhood of a node, grouped by relationship."""
        self._ensure_built()
        if not _NX_AVAILABLE or self._graph is None:
            return {}
        prefix = {"canon_entry": "chunk:", "canon_domain": "canon_domain:", "entity": "entity:"}.get(node_type, "")
        node = f"{prefix}{node_id}"
        if not self._graph.has_node(node):
            return {}
        g = self._graph
        grouped: dict[str, list[dict]] = {}
        for _, v, d in g.out_edges(node, data=True):
            grouped.setdefault(d.get("rel", "?"), []).append(
                {"direction": "out", "node": v, **dict(g.nodes[v])})
        for u, _, d in g.in_edges(node, data=True):
            grouped.setdefault(d.get("rel", "?"), []).append(
                {"direction": "in", "node": u, **dict(g.nodes[u])})
        return grouped

    def get_chunks_for_spec(self, canon_domain_id: str) -> list[dict]:
        """All KeyMessages for a canon_domain, sorted by priority."""
        self._ensure_built()
        if not _NX_AVAILABLE:
            return []
        spec_node = f"canon_domain:{canon_domain_id}"
        if spec_node not in self._graph:
            return []
        chunks: list[dict] = []
        for _, sec_node, d in self._graph.out_edges(spec_node, data=True):
            if d.get("rel") == "HAS_SECTION":
                for _, chunk_node, d2 in self._graph.out_edges(sec_node, data=True):
                    if d2.get("rel") == "CONTAINS":
                        chunks.append(dict(self._graph.nodes[chunk_node]))
        return sorted(chunks, key=lambda c: c.get("priority", 3))

    def get_sections_for_spec(self, canon_domain_id: str) -> list[dict]:
        """Section nodes for a canon_domain with their KeyMessages nested, ordered by section type."""
        self._ensure_built()
        if not _NX_AVAILABLE:
            return []
        spec_node = f"canon_domain:{canon_domain_id}"
        if spec_node not in self._graph:
            return []
        sections: list[dict] = []
        for _, sec_node, d in self._graph.out_edges(spec_node, data=True):
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

    def get_chunks_for_audience(self, canon_domain_id: str, audience_name: str) -> list[dict]:
        """KeyMessages that ADDRESS a specific persona within a canon_domain."""
        self._ensure_built()
        if not _NX_AVAILABLE:
            return []
        audience_node = f"persona:{canon_domain_id}:{audience_name}"
        if audience_node not in self._graph:
            return []
        return [dict(self._graph.nodes[n]) for n, _, d
                in self._graph.in_edges(audience_node, data=True)
                if d.get("rel") == "ADDRESSES"]

    def get_chunks_for_channel(self, canon_domain_id: str, channel: str) -> list[dict]:
        """KeyMessages that APPLY_TO a specific channel within a canon_domain."""
        self._ensure_built()
        if not _NX_AVAILABLE:
            return []
        channel_node = f"channel:{channel}"
        if channel_node not in self._graph:
            return []
        spec_chunks = self._spec_chunk_nodes(canon_domain_id)
        return [dict(self._graph.nodes[n]) for n, _, d
                in self._graph.in_edges(channel_node, data=True)
                if d.get("rel") == "APPLIES_TO" and n in spec_chunks]

    def get_connections(self, canon_domain_id: str,
                        persona: str | None = None,
                        channel: str | None = None) -> list[dict]:
        """Graph query entry point — filter by optional persona and/or channel."""
        self._ensure_built()
        if not _NX_AVAILABLE:
            return []
        if persona and channel:
            by_p = {c["id"] for c in self.get_chunks_for_audience(canon_domain_id, persona)}
            by_c = {c["id"] for c in self.get_chunks_for_channel(canon_domain_id, channel)}
            ids = by_p & by_c
            results = [c for c in self.get_chunks_for_spec(canon_domain_id) if c.get("id") in ids]
        elif persona:
            results = self.get_chunks_for_audience(canon_domain_id, persona)
        elif channel:
            results = self.get_chunks_for_channel(canon_domain_id, channel)
        else:
            results = self.get_chunks_for_spec(canon_domain_id)
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
            elif ntype == "Section":
                label = attrs.get("label", attrs.get("section_type", nid))
            else:
                content = attrs.get("content", "")
                label = (attrs.get("name")
                         or (content[:35] + "…" if len(content) > 35 else content)
                         or nid)
            entry: dict[str, Any] = {"id": nid, "type": ntype, "label": label}
            if ntype == "CanonDomain":
                entry.update({"name": attrs.get("name", ""),
                               "grounding_type": attrs.get("grounding_type", ""),
                               "tagline": attrs.get("tagline", ""),
                               "summary": (attrs.get("summary") or "")[:150]})
            elif ntype == "Section":
                entry.update({"section_type": attrs.get("section_type", ""),
                               "label": attrs.get("label", ""),
                               "count": attrs.get("count", 0),
                               "canon_domain_id": attrs.get("canon_domain_id", "")})
                entry["color"] = _SECTION_COLORS.get(attrs.get("section_type", ""), "#6366f1")
            elif ntype == "CanonEntry":
                entry.update({"section_type": attrs.get("section_type", ""),
                               "priority": attrs.get("priority"),
                               "content": (attrs.get("content") or "")[:150],
                               "status": attrs.get("status", "draft")})
                entry["color"] = _STATUS_COLORS.get(attrs.get("status", "draft"), "#9ca3af")
            elif ntype == "Pillar":
                entry.update({"name": attrs.get("name", ""),
                               "description": attrs.get("description", ""),
                               "canon_domain_id": attrs.get("canon_domain_id", "")})
            elif ntype == "Persona":
                entry.update({"name": attrs.get("name", ""),
                               "canon_domain_id": attrs.get("canon_domain_id", "")})
            elif ntype == "Channel":
                entry["name"] = attrs.get("name", "")
            elif ntype == "Entity":
                entry.update({"name": attrs.get("name", ""),
                               "entity_type": attrs.get("entity_type", ""),
                               "description": (attrs.get("description") or "")[:150]})
            elif ntype == "Objection":
                entry.update({"statement": (attrs.get("statement") or "")[:150],
                               "response": (attrs.get("response") or "")[:150],
                               "audience_name": attrs.get("audience_name", ""),
                               "canon_domain_id": attrs.get("canon_domain_id", "")})
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
