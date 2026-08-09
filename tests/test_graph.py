"""Graph substrate: entity resolution, typed edges, k-hop traversal, propagation.

The point of these tests is to prove the graph does the thing the product
claims — cross-spec retrieval and cascade invalidation — rather than the
within-spec containment filtering the previous implementation did.
"""

import os
import pytest
from uuid import uuid4

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from src.models import Spec, Assertion, AssertionType, AssertionStatus, SpecStatus


@pytest.fixture
def store(tmp_path):
    # The graph engine resolves the store through the module singleton, so the
    # test database has to be installed there rather than just handed around.
    import src.store as store_mod
    from src.store import Store
    s = Store(str(tmp_path / "graph_test.db"))
    s.init()
    prev = store_mod._store_instance
    store_mod._store_instance = s
    yield s
    store_mod._store_instance = prev


@pytest.fixture
def two_specs(store):
    """Two unrelated specs, each with one assertion. Nothing links them yet."""
    api = Spec(name="payments-api", summary="Payment service contract",
               status=SpecStatus.ACTIVE)
    slo = Spec(name="platform-slo", summary="Platform reliability targets",
               status=SpecStatus.ACTIVE)
    store.upsert_spec(api)
    store.upsert_spec(slo)

    a1 = Assertion(spec_id=api.id, assertion_type=AssertionType.POSITIONING, priority=1,
                   content="Checkout endpoint is limited to 1000 req/min per API key.",
                   status=AssertionStatus.APPROVED)
    a2 = Assertion(spec_id=slo.id, assertion_type=AssertionType.POSITIONING, priority=1,
                   content="Gateway sheds load above 1200 req/min aggregate.",
                   status=AssertionStatus.APPROVED)
    store.upsert_assertion(a1)
    store.upsert_assertion(a2)
    return api, slo, a1, a2


# ── Entity resolution ────────────────────────────────────────────────────

def test_entity_resolution_folds_surface_forms(store):
    a = store.resolve_entity("Payments API")
    b = store.resolve_entity("payments-api")
    c = store.resolve_entity("payments_api")
    assert a == b == c, "surface variants must resolve to one entity"


def test_entity_resolution_distinguishes_real_differences(store):
    a = store.resolve_entity("payments-api")
    b = store.resolve_entity("billing-api")
    assert a != b


def test_resolve_entity_no_create_returns_none(store):
    assert store.resolve_entity("never-seen", create=False) is None


def test_alias_match_resolves_to_existing_entity(store):
    eid = store.resolve_entity("payments-api")
    other = store.resolve_entity("checkout-service")
    store.merge_entities(eid, other)
    # the merged name is now an alias of the survivor
    assert store.resolve_entity("checkout-service") == eid


def test_merge_repoints_mentions(store, two_specs):
    _, _, a1, _ = two_specs
    keep = store.resolve_entity("payments-api")
    dupe = store.resolve_entity("Payment Service")
    store.add_entity_mention(dupe, str(a1.id), str(a1.spec_id))
    store.merge_entities(keep, dupe)
    mentions = store.list_entity_mentions()
    assert all(m["entity_id"] == keep for m in mentions)
    assert len(store.list_entities()) == 1


# ── Edge integrity ───────────────────────────────────────────────────────

def test_add_edge_rejects_missing_endpoint(store, two_specs):
    _, _, a1, _ = two_specs
    with pytest.raises(ValueError, match="dst node not found"):
        store.add_edge("assertion", str(a1.id), "assertion", str(uuid4()), "DEPENDS_ON")


def test_add_edge_is_idempotent(store, two_specs):
    _, _, a1, a2 = two_specs
    e1 = store.add_edge("assertion", str(a1.id), "assertion", str(a2.id), "DEPENDS_ON")
    e2 = store.add_edge("assertion", str(a1.id), "assertion", str(a2.id), "DEPENDS_ON")
    assert e1 == e2
    assert len(store.list_edges()) == 1


# ── Traversal: the actual claim ──────────────────────────────────────────

def test_expansion_crosses_spec_boundary_via_shared_entity(store, two_specs):
    """Two assertions in different specs, joined only by mentioning the same
    entity, must be reachable from each other. This is the capability the old
    filter-by-spec implementation could not express at all."""
    api, slo, a1, a2 = two_specs
    eid = store.resolve_entity("checkout-endpoint")
    store.add_entity_mention(eid, str(a1.id), str(api.id))
    store.add_entity_mention(eid, str(a2.id), str(slo.id))

    from src.grounding.graph import get_graph_engine
    engine = get_graph_engine()
    engine.rebuild()

    found = engine.expand([str(a1.id)], hops=2)
    ids = {f["id"] for f in found}
    assert str(a2.id) in ids, "should reach the other spec's assertion in 2 hops"

    hit = next(f for f in found if f["id"] == str(a2.id))
    assert hit["hops"] == 2
    assert "MENTIONS" in "".join(hit["graph_path"])


def test_expansion_follows_explicit_typed_edge(store, two_specs):
    api, slo, a1, a2 = two_specs
    store.add_edge("assertion", str(a1.id), "assertion", str(a2.id), "DEPENDS_ON")

    from src.grounding.graph import get_graph_engine
    engine = get_graph_engine()
    engine.rebuild()

    found = engine.expand([str(a1.id)], hops=1)
    assert str(a2.id) in {f["id"] for f in found}


def test_expansion_respects_hop_limit(store, two_specs):
    api, slo, a1, a2 = two_specs
    eid = store.resolve_entity("checkout-endpoint")
    store.add_entity_mention(eid, str(a1.id), str(api.id))
    store.add_entity_mention(eid, str(a2.id), str(slo.id))

    from src.grounding.graph import get_graph_engine
    engine = get_graph_engine()
    engine.rebuild()

    assert str(a2.id) not in {f["id"] for f in engine.expand([str(a1.id)], hops=1)}
    assert str(a2.id) in {f["id"] for f in engine.expand([str(a1.id)], hops=2)}


def test_expansion_filters_by_rel_type(store, two_specs):
    api, slo, a1, a2 = two_specs
    store.add_edge("assertion", str(a1.id), "assertion", str(a2.id), "CONTRADICTS")

    from src.grounding.graph import get_graph_engine
    engine = get_graph_engine()
    engine.rebuild()

    assert str(a2.id) in {f["id"] for f in engine.expand([str(a1.id)], hops=1)}
    got = engine.expand([str(a1.id)], hops=1, rel_types=["DEPENDS_ON"])
    assert str(a2.id) not in {f["id"] for f in got}


def test_expansion_weight_decays_with_distance(store, two_specs):
    api, slo, a1, a2 = two_specs
    store.add_edge("assertion", str(a1.id), "assertion", str(a2.id), "DEPENDS_ON")
    from src.grounding.graph import get_graph_engine
    engine = get_graph_engine()
    engine.rebuild()
    hit = next(f for f in engine.expand([str(a1.id)], hops=2) if f["id"] == str(a2.id))
    assert 0 < hit["graph_weight"] < 1.0


def test_expansion_excludes_seed_from_results(store, two_specs):
    _, _, a1, a2 = two_specs
    store.add_edge("assertion", str(a1.id), "assertion", str(a2.id), "DEPENDS_ON")
    from src.grounding.graph import get_graph_engine
    engine = get_graph_engine()
    engine.rebuild()
    assert str(a1.id) not in {f["id"] for f in engine.expand([str(a1.id)], hops=2)}


# ── Change propagation ───────────────────────────────────────────────────

def test_propagation_marks_dependent_outdated(store, two_specs):
    """a1 DEPENDS_ON a2 — editing a2 must invalidate a1, across specs."""
    _, _, a1, a2 = two_specs
    store.add_edge("assertion", str(a1.id), "assertion", str(a2.id), "DEPENDS_ON")

    a2.content = "Gateway now sheds load above 2000 req/min aggregate."
    store.upsert_assertion(a2)

    refreshed = store.get_assertion(a1.id)
    assert str(refreshed.status) == "outdated"


def test_propagation_is_transitive(store, two_specs):
    api, slo, a1, a2 = two_specs
    a3 = Assertion(spec_id=api.id, assertion_type=AssertionType.POSITIONING, priority=1,
                   content="Docs quote the checkout rate limit.",
                   status=AssertionStatus.APPROVED)
    store.upsert_assertion(a3)
    store.add_edge("assertion", str(a3.id), "assertion", str(a1.id), "DEPENDS_ON")
    store.add_edge("assertion", str(a1.id), "assertion", str(a2.id), "DEPENDS_ON")

    a2.content = "changed upstream"
    store.upsert_assertion(a2)

    assert str(store.get_assertion(a1.id).status) == "outdated"
    assert str(store.get_assertion(a3.id).status) == "outdated", "must cascade two levels"


def test_propagation_terminates_on_cycle(store, two_specs):
    """Nothing stops an author creating a dependency cycle; it must not hang."""
    _, _, a1, a2 = two_specs
    store.add_edge("assertion", str(a1.id), "assertion", str(a2.id), "DEPENDS_ON")
    store.add_edge("assertion", str(a2.id), "assertion", str(a1.id), "DEPENDS_ON")

    a2.content = "mutually dependent change"
    store.upsert_assertion(a2)  # must return rather than recurse forever
    assert str(store.get_assertion(a1.id).status) == "outdated"


def test_non_propagating_rel_does_not_invalidate(store, two_specs):
    """MENTIONS is navigational — it must not cascade staleness."""
    _, _, a1, a2 = two_specs
    store.add_edge("assertion", str(a1.id), "assertion", str(a2.id), "MENTIONS")
    a2.content = "changed"
    store.upsert_assertion(a2)
    assert str(store.get_assertion(a1.id).status) != "outdated"


def test_get_dependents_only_returns_propagating_rels(store, two_specs):
    _, _, a1, a2 = two_specs
    store.add_edge("assertion", str(a1.id), "assertion", str(a2.id), "DEPENDS_ON")
    store.add_edge("assertion", str(a1.id), "assertion", str(a2.id), "MENTIONS")
    deps = store.get_dependents("assertion", str(a2.id))
    assert len(deps) == 1
    assert deps[0]["rel_type"] == "DEPENDS_ON"


# ── Hybrid fusion ────────────────────────────────────────────────────────

def _engine(store):
    from src.grounding.search import GroundingEngine
    return GroundingEngine.__new__(GroundingEngine).__class__.__new__(GroundingEngine) \
        if False else _bare_engine(store)


def _bare_engine(store):
    """A GroundingEngine with the store attached but no vector index — enough
    to exercise fusion without embedding anything."""
    from src.grounding.search import GroundingEngine
    e = object.__new__(GroundingEngine)
    e.store = store
    e.index = None
    return e


def _vector_match(assertion_id, score, spec_id):
    return {
        "id": f"chunk-{assertion_id}",
        "score": score,
        "metadata": {
            "assertion_id": str(assertion_id), "spec_id": str(spec_id),
            "spec_name": "", "spec_summary": "", "content": "seed",
            "assertion_type": "positioning", "priority": 1,
            "audience": None, "channel": "all",
            "last_synced": None, "content_tier": None,
        },
    }


def test_fusion_pulls_in_cross_spec_assertion(store, two_specs):
    """Vector search only sees spec A. Fusion must surface spec B's assertion,
    reached by traversal, in the final ranking."""
    from src.models import SearchFilters
    api, slo, a1, a2 = two_specs
    eid = store.resolve_entity("checkout-endpoint")
    store.add_entity_mention(eid, str(a1.id), str(api.id))
    store.add_entity_mention(eid, str(a2.id), str(slo.id))
    from src.grounding.graph import get_graph_engine
    get_graph_engine().rebuild()

    eng = _bare_engine(store)
    vector_only = [_vector_match(a1.id, 0.9, api.id)]
    fused = eng._fuse_with_graph(vector_only, SearchFilters(), top_k=8)

    ids = {m["metadata"]["assertion_id"] for m in fused}
    assert str(a1.id) in ids
    assert str(a2.id) in ids, "graph-reached assertion from another spec must be fused in"
    reached = next(m for m in fused if m["metadata"]["assertion_id"] == str(a2.id))
    assert reached["metadata"]["spec_id"] == str(slo.id)
    assert "graph:" in reached["rerank_reason"]


def test_fusion_ranks_dual_hits_above_single(store, two_specs):
    """A document found by both vector and graph must outrank one found by
    vector alone — that is the whole reason to fuse.

    Seeds are the top 5 vector hits and are excluded from their own expansion,
    so the dual-retrieved document has to sit below that cut for the effect to
    be observable at all.
    """
    from src.models import SearchFilters
    api, slo, a1, a2 = two_specs
    filler = []
    for i in range(5):
        f = Assertion(spec_id=api.id, assertion_type=AssertionType.POSITIONING,
                      priority=1, content=f"filler {i}", status=AssertionStatus.APPROVED)
        store.upsert_assertion(f)
        filler.append(f)
    # a1 (rank 1) is a seed; a2 sits last on vectors but is one hop from a1
    store.add_edge("assertion", str(a1.id), "assertion", str(a2.id), "DEPENDS_ON")
    from src.grounding.graph import get_graph_engine
    get_graph_engine().rebuild()

    eng = _bare_engine(store)
    matches = ([_vector_match(a1.id, 0.9, api.id)]
               + [_vector_match(f.id, 0.8 - i * 0.05, api.id) for i, f in enumerate(filler)]
               + [_vector_match(a2.id, 0.5, slo.id)])
    fused = eng._fuse_with_graph(matches, SearchFilters(), top_k=8)
    order = [m["metadata"]["assertion_id"] for m in fused]
    assert order.index(str(a2.id)) < order.index(str(filler[-1].id)), \
        "a2 is retrieved by both routes and must outrank the vector-only tail"


def test_fusion_is_noop_without_graph_edges(store, two_specs):
    from src.models import SearchFilters
    api, _, a1, _ = two_specs
    from src.grounding.graph import get_graph_engine
    get_graph_engine().rebuild()
    eng = _bare_engine(store)
    matches = [_vector_match(a1.id, 0.9, api.id)]
    assert eng._fuse_with_graph(matches, SearchFilters(), top_k=8) == matches


def test_fusion_respects_lifecycle_gate(store, two_specs):
    """A draft assertion reached by traversal must not enter results."""
    from src.models import SearchFilters
    api, slo, a1, a2 = two_specs
    a2.status = AssertionStatus.DRAFT
    store.upsert_assertion(a2)
    store.add_edge("assertion", str(a1.id), "assertion", str(a2.id), "DEPENDS_ON")
    from src.grounding.graph import get_graph_engine
    get_graph_engine().rebuild()

    eng = _bare_engine(store)
    fused = eng._fuse_with_graph([_vector_match(a1.id, 0.9, api.id)],
                                 SearchFilters(), top_k=8)
    assert str(a2.id) not in {m["metadata"]["assertion_id"] for m in fused}


def test_shared_channel_does_not_connect_unrelated_assertions(store, two_specs):
    """Regression: every assertion carries channel "all", so traversing
    APPLIES_TO put every assertion two hops from every other one and the graph
    degenerated into a complete graph. Channel membership is not a relationship.
    """
    api, slo, a1, a2 = two_specs
    a1.channels = ["all"]
    a2.channels = ["all"]
    store.upsert_assertion(a1)
    store.upsert_assertion(a2)

    from src.grounding.graph import get_graph_engine
    engine = get_graph_engine()
    engine.rebuild()

    found = engine.expand([str(a1.id)], hops=3)
    assert str(a2.id) not in {f["id"] for f in found}, \
        "sharing a channel must not make two unrelated assertions reachable"


def test_hub_node_is_not_traversed_through(store):
    """A node above the hub-degree threshold may be reached but not expanded
    through, whatever relationship type connects it."""
    from src.grounding.graph import get_graph_engine
    spec = Spec(name="hub-spec", summary="", status=SpecStatus.ACTIVE)
    store.upsert_spec(spec)
    hub = store.resolve_entity("ubiquitous-thing")
    assertions = []
    for i in range(engine_hub_count := 30):
        a = Assertion(spec_id=spec.id, assertion_type=AssertionType.POSITIONING,
                      priority=1, content=f"a{i}", status=AssertionStatus.APPROVED)
        store.upsert_assertion(a)
        store.add_entity_mention(hub, str(a.id), str(spec.id))
        assertions.append(a)

    engine = get_graph_engine()
    engine.rebuild()
    # the entity now has 30 mentions — well over the hub threshold
    found = engine.expand([str(assertions[0].id)], hops=2)
    assert found == [] or len(found) < engine_hub_count - 1, \
        "expansion must not fan out through a high-degree hub"
