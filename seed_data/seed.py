"""Seed MsgStack with MsgStack's own product-marketing message house.

MsgStack dogfoods itself here: the demo corpus is the marketing graph for
MsgStack the product, not a fictional third party. One trunk spec holds the
locked positioning, proof points and claim-discipline rules; two branches
consume it — product-marketing (the one-pager, the competitive battlecard)
and campaigns (the launch campaign, its retro) — and a handful of shared
entities bridge the two branches without an explicit spec-to-spec edge.

This is the second corpus this file has held. The first (pre-2026-08-09) used
the old MessageHouse/KeyMessage/Persona schema and described ten fictional
SaaS products; it was cut for an engineering corpus per STRATEGY_V2 §6, which
also retired the marketing-shaped assertion types (headline / benefit /
proof_point / social_proof). This corpus is marketing content again, but it
is expressed entirely in the current, engineering-shaped Assertion vocabulary
(CONSTRAINT, CAPABILITY, DEPENDENCY, DECISION, ...) — no schema changes. A
brand-voice rule really is a CONSTRAINT; a proof point really is a CAPABILITY;
"don't claim what we can't back up" really is a LIMITATION. The typed-graph
thesis doesn't care whether the domain is a payments API or a positioning
statement: editing messaging-house's lead-order proof point is meant to flag
product-positioning and launch-campaign outdated the same way editing a
gateway threshold used to flag payments-api and checkout-web.
"""

from datetime import datetime
from uuid import uuid4

from src.models import (
    Assertion, AssertionStatus, AssertionType, Audience, ContentTier,
    Spec, SpecStatus, SchemaType,
)
from src.store import get_store


# (assertion_type, content, tier, status)
_T1 = ContentTier.TIER_1_LOCKED
_T2 = ContentTier.TIER_2_STRUCTURED
_T3 = ContentTier.TIER_3_GROUNDED
_A = AssertionStatus.APPROVED
_L = AssertionStatus.LOCKED


def _spec(name, summary, schema_type, dri, department="Marketing", positioning="", tagline=""):
    return Spec(
        id=uuid4(), name=name, summary=summary, schema_type=schema_type,
        status=SpecStatus.ACTIVE, department=department, dri=dri,
        positioning=positioning, tagline=tagline, source="seed",
    )


CORPUS: list[dict] = [
    {
        "spec": _spec(
            "messaging-house",
            "The trunk of MsgStack's own message house: one locked positioning "
            "statement, two proof points, and the claim-discipline rules every "
            "downstream product-marketing and campaigns spec traces back to.",
            SchemaType.ENGINEERING_SPEC, "@brand", department="Marketing",
            positioning="MsgStack is sold on its own usefulness test: would you "
                        "point it at your own infrastructure? This spec is itself "
                        "an instance of the product — it dogfoods the graph it sells.",
            tagline="Facts your agents can cite.",
        ),
        "assertions": [
            (AssertionType.POSITIONING,
             "Core positioning: MsgStack is a self-hosted memory layer for agents. "
             "Facts are typed, versioned and provenanced; agents query them over "
             "MCP and cite a source instead of guessing.", _T1, _L, "core-positioning"),
            (AssertionType.CONSTRAINT,
             "Never claim 'zero hallucination' or 'eliminates hallucination' in "
             "any external copy — say 'every fact is traceable to a source'. "
             "Absolute claims invite an easy takedown from a prospect's security "
             "team and we cannot back them with a benchmark.", _T1, _L, "voice-constraint"),
            (AssertionType.CAPABILITY,
             "Proof point — self-host: the entire stack stands up with one "
             "`docker compose up`, no signup, no credit card. This is the "
             "fastest credibility move against governance-platform competitors "
             "who require a sales call before a prospect sees the product.", _T1, _L, "proof-point-selfhost"),
            (AssertionType.CAPABILITY,
             "Proof point — propagation: editing one fact live flags every "
             "downstream assertion that depends on it as outdated, visibly, in "
             "under a second. This is the mechanism prospects don't believe "
             "until they watch it move.", _T1, _L, "proof-point-propagation"),
            (AssertionType.LIMITATION,
             "We do not claim a hallucination-reduction percentage or cite any "
             "accuracy benchmark — none has been run. Every claim stays scoped "
             "to 'traceable to source', never 'more correct'.", _T2, _A, "claim-limit"),
            (AssertionType.LIMITATION,
             "The message house assumes an MCP-literate reader. Do not broaden "
             "the positioning to 'AI memory for everyone' — that dilutes both "
             "proof points above and widens the ICP past what the product "
             "actually serves.", _T2, _A, "icp-scope"),
            (AssertionType.CONFIG_DEFAULT,
             "Default CTA on every external surface — site, one-pagers, campaign "
             "creative — is 'Read the docs', not 'Book a demo'. There is no "
             "sales team; a demo CTA sets an expectation nobody fulfills.", _T2, _A, "default-cta"),
            (AssertionType.VERSION_POLICY,
             "This message house is re-approved every quarter, or immediately "
             "after any STRATEGY_V2-class positioning change, whichever comes "
             "first. A product-marketing or campaign spec built on a stale "
             "house must be flagged, not quietly kept.", _T2, _A, "review-cadence"),
        ],
        "audiences": [
            ("Copywriter drafting external copy",
             "Turns locked positioning into site copy, one-pagers and ads.",
             [("Can I say MsgStack reduces hallucinations?",
               "No — that's a locked claim-limit. Say the fact is traceable to a "
               "source, not that it's more accurate."),
              ("Which proof point goes first in a one-pager?",
               "Self-host, then propagation — see product-positioning's lead-order "
               "guidance, confirmed by the Q3 campaign retro.")]),
        ],
    },
    {
        "spec": _spec(
            "product-positioning",
            "The one-pager and competitive framing PMM ships to prospects. Leads "
            "with the proof points from the message house, in the order the Q3 "
            "retro confirmed converts.",
            SchemaType.ENGINEERING_SPEC, "@pmm", department="Product Marketing",
            positioning="Gets a skeptical engineer to yes on the usefulness test "
                        "in under two minutes.",
        ),
        "assertions": [
            (AssertionType.CAPABILITY,
             "One-pager leads with the self-host proof point before the "
             "propagation one. Procurement objections ('does our data leave our "
             "network') kill deals faster than feature skepticism, so the answer "
             "has to land first.", _T1, _L, "lead-order"),
            (AssertionType.SECURITY_POSTURE,
             "Self-hosted deploy means customer data and API keys never leave "
             "the customer's own infrastructure. An independent proof point from "
             "the self-host story, true by architecture — it doesn't require a "
             "formal security review to state.", _T1, _L, "data-residency"),
            (AssertionType.CONFIG_DEFAULT,
             "One-pager CTA is the message house default ('Read the docs'), "
             "inherited rather than restated.", _T2, _A, "cta-choice"),
            (AssertionType.DECISION,
             "We cut the enterprise RBAC / approval-workflow comparison table "
             "from the one-pager entirely. STRATEGY_V2 confirmed the governance "
             "apparatus isn't shipping, so a comparison table would be "
             "marketing a feature that doesn't exist.", _T2, _A, None),
            (AssertionType.DEPRECATION,
             "The pre-STRATEGY_V2 'organizational canon' one-pager is retired "
             "as of 2026-08-07. Do not resurrect its governance-platform "
             "framing, even for a compliance-minded prospect who asks for it "
             "by name.", _T1, _L, "canon-retired"),
            (AssertionType.LIMITATION,
             "The one-pager makes no enterprise-adoption claim. There are zero "
             "paying enterprise customers; every proof point stays scoped to "
             "self-hoster or homelab scale.", _T2, _A, "no-enterprise-claim"),
        ],
        "audiences": [
            ("Sales-adjacent reader (there is no sales team)",
             "Anyone forwarding the one-pager to a prospect without a call first.",
             [("A prospect asks about SOC2 or RBAC — what do I say?",
               "That the governance apparatus isn't shipping — STRATEGY_V2 cut "
               "it deliberately. Don't imply it's on the roadmap.")]),
        ],
    },
    {
        "spec": _spec(
            "competitive-battlecard",
            "How we talk about governance-platform competitors without implying "
            "we're building the same thing at smaller scale.",
            SchemaType.ENGINEERING_SPEC, "@pmm", department="Product Marketing",
        ),
        "assertions": [
            (AssertionType.DECISION,
             "Framing against governance platforms is 'right-sized for teams "
             "who ship faster than they document', never 'coming soon' or "
             "'roadmap'. We are not building their feature set later — "
             "STRATEGY_V2 cut it as the wrong shape, not as a sequencing "
             "choice.", _T1, _L, "battlecard-framing"),
            (AssertionType.LIMITATION,
             "We concede the multi-department approval-workflow comparison "
             "outright. Say so directly — 'we don't have that, here's why it's "
             "not a gap for a team of one' — rather than deflect.", _T2, _A, "battlecard-honesty"),
            (AssertionType.CAPABILITY,
             "Differentiator that survives every governance-platform comparison: "
             "the propagation demo. No competitor in this category shows a live, "
             "typed change flagging two downstream facts outdated in real time.", _T2, _A, "propagation-proof"),
            (AssertionType.SLA,
             "Battlecard is refreshed within 5 business days of a competitor "
             "announcement. If a refresh slips past 10 days, pull the card from "
             "any outbound use rather than let it go stale in front of a "
             "prospect.", _T2, _A, "refresh-commitment"),
            (AssertionType.VERSION_POLICY,
             "Battlecard inherits every locked claim-limit and voice-constraint "
             "from the message house. A battlecard edit can loosen framing "
             "language but never a locked claim.", _T1, _L, "claim-discipline"),
        ],
        "audiences": [
            ("PMM writing a comparison post",
             "Publishing anything that names a competitor.",
             [("Can I claim we're cheaper?",
               "Only if you can cite a number — there's no approved pricing "
               "comparison yet. Default to the propagation-proof differentiator "
               "instead.")]),
        ],
    },
    {
        "spec": _spec(
            "launch-campaign",
            "The MsgStack v2 launch campaign — creative, cadence and channel "
            "sequencing built on the message house and product-positioning "
            "specs.",
            SchemaType.ENGINEERING_SPEC, "@growth", department="Campaigns",
        ),
        "assertions": [
            (AssertionType.CAPABILITY,
             "Hero creative is a recorded clip of editing a gateway-style "
             "threshold live and watching two downstream facts flip to "
             "'outdated' — the propagation proof point, animated, because it's "
             "a mechanism nobody believes until they watch it move.", _T1, _L, "hero-creative"),
            (AssertionType.CONSTRAINT,
             "Campaign runs on owned channels only (LinkedIn, newsletter) for "
             "the first two weeks. No paid spend is approved until organic CTR "
             "is measured against the self-host-led creative variant.", _T2, _A, "channel-gate"),
            (AssertionType.CONFIG_DEFAULT,
             "Default cadence is two LinkedIn posts a week during the campaign "
             "window, routed through the existing content-desk judge/auto-post "
             "gate rather than a separate campaign queue.", _T2, _A, "cadence-default"),
            (AssertionType.DEPENDENCY,
             "Creative sequencing leads with the self-host proof point, same "
             "order as the one-pager — confirmed by the Q3 retro after the "
             "propagation-led variant underperformed.", _T1, _L, "lead-order"),
            (AssertionType.DECISION,
             "Campaign CTA matches the message house default ('Read the docs') "
             "rather than a lead-capture form — there's nowhere for a captured "
             "lead to go without a sales process.", _T2, _A, "campaign-cta"),
            (AssertionType.DEPRECATION,
             "The pre-STRATEGY_V2 'organizational canon' launch campaign draft "
             "is retired alongside the one-pager it was built from — "
             "2026-08-07.", _T2, _A, None),
        ],
        "audiences": [
            ("Growth marketer scheduling posts",
             "Executes the campaign calendar.",
             [("Which proof point leads the first post?",
               "Self-host, always — the propagation demo is the second post, "
               "not the first. The Q3 retro is why.")]),
        ],
    },
    {
        "spec": _spec(
            "campaign-retro-q3",
            "Retro on the Q3 test that compared a propagation-led launch "
            "variant against a self-host-led one.",
            SchemaType.INCIDENT_RECORD, "@growth", department="Campaigns",
        ),
        "assertions": [
            (AssertionType.DECISION,
             "Root cause of the propagation-led variant's underperformance: it "
             "opens with a mechanism demo before the reader has a reason to "
             "trust the mechanism matters. CTR was 40% lower than the "
             "self-host-led variant run the same week. Confirms lead-order "
             "should be a locked assertion, not a suggestion.", _T1, _L, "root-cause"),
            (AssertionType.RUNBOOK_STEP,
             "Retro process: pull both variants' CTR from the campaign tracker, "
             "compare against the message house's proof-point ordering, and "
             "file any confirmed ordering as a locked assertion so it can't "
             "silently regress in the next campaign.", _T3, _A, None),
            (AssertionType.LIMITATION,
             "Sample size is one campaign week per variant. Treat the 40% "
             "figure as directional, not a benchmark to quote externally — "
             "that would itself violate the message house's claim-limit.", _T2, _A, "retro-limitation"),
        ],
        "audiences": [],
    },
]


#: Cross-spec relationships. (src_spec, src_tag, rel, dst_spec, dst_tag)
#: DEPENDS_ON and INFORMS propagate: editing the destination marks the source
#: outdated. This is the wiring that makes the corpus a graph rather than five
#: unrelated documents — and that ties the campaigns branch and the
#: product-marketing branch back to one trunk.
EDGES = [
    ("product-positioning", "lead-order",       "DEPENDS_ON", "messaging-house",       "proof-point-selfhost"),
    ("product-positioning", "cta-choice",       "DEPENDS_ON", "messaging-house",       "default-cta"),
    ("competitive-battlecard", "claim-discipline", "DEPENDS_ON", "messaging-house",    "claim-limit"),
    ("launch-campaign", "lead-order",           "DEPENDS_ON", "product-positioning",   "lead-order"),
    ("launch-campaign", "hero-creative",        "DEPENDS_ON", "messaging-house",       "proof-point-propagation"),
    ("launch-campaign", "campaign-cta",         "DEPENDS_ON", "product-positioning",   "cta-choice"),
    ("messaging-house", "proof-point-propagation", "INFORMS", "competitive-battlecard", "propagation-proof"),
    ("campaign-retro-q3", "root-cause",         "INFORMS",    "launch-campaign",       "lead-order"),
    ("campaign-retro-q3", "root-cause",         "INFORMS",    "messaging-house",       "proof-point-selfhost"),
]

#: Entities shared across specs. These are the bridges that let a traversal
#: leave one spec without an explicitly authored edge — and, here, the nodes
#: that overlap between the product-marketing branch (product-positioning,
#: competitive-battlecard) and the campaigns branch (launch-campaign,
#: campaign-retro-q3).
ENTITIES = {
    "self-host-proof-point": [("messaging-house", "proof-point-selfhost"),
                              ("product-positioning", "data-residency"),
                              ("launch-campaign", "lead-order")],
    "propagation-proof-point": [("messaging-house", "proof-point-propagation"),
                                ("competitive-battlecard", "propagation-proof"),
                                ("launch-campaign", "hero-creative")],
    "claim-discipline":       [("messaging-house", "claim-limit"),
                               ("competitive-battlecard", "claim-discipline"),
                               ("campaign-retro-q3", "retro-limitation")],
    "default-cta":            [("messaging-house", "default-cta"),
                               ("product-positioning", "cta-choice"),
                               ("launch-campaign", "campaign-cta")],
}


def seed() -> int:
    """Populate the store with the message-house corpus. Idempotent by spec
    name: an existing spec of the same name is left alone rather than
    duplicated."""
    store = get_store()
    existing = {s.name for s in store.list_specs()}

    # tag -> assertion id, per spec, so edges can be resolved after insert
    tags: dict[tuple[str, str], str] = {}
    created = 0

    for item in CORPUS:
        spec = item["spec"]
        if spec.name in existing:
            continue
        store.upsert_spec(spec)
        created += 1

        for priority, (a_type, content, tier, status, tag) in enumerate(item["assertions"], start=1):
            a = Assertion(
                id=uuid4(), spec_id=spec.id, assertion_type=a_type,
                priority=min(priority, 5), content=content,
                status=status, content_tier=tier, dri=spec.dri,
            )
            store.upsert_assertion(a)
            if tag:
                tags[(spec.name, tag)] = str(a.id)

        for name, description, qa in item["audiences"]:
            store.upsert_audience(Audience(
                id=uuid4(), spec_id=spec.id, name=name, description=description,
                qa_pairs=[{"statement": s, "response": r} for s, r in qa],
                status=AssertionStatus.APPROVED,
            ))

    if not created:
        return 0

    for src_spec, src_tag, rel, dst_spec, dst_tag in EDGES:
        src = tags.get((src_spec, src_tag))
        dst = tags.get((dst_spec, dst_tag))
        if src and dst:
            store.add_edge("assertion", src, "assertion", dst, rel,
                           provenance="seed corpus", created_by="seed")

    for entity_name, refs in ENTITIES.items():
        eid = store.resolve_entity(entity_name, entity_type="concept")
        if not eid:
            continue
        for spec_name, tag in refs:
            aid = tags.get((spec_name, tag))
            if aid:
                spec_id = next(
                    (str(c["spec"].id) for c in CORPUS if c["spec"].name == spec_name), None
                )
                if spec_id:
                    store.add_entity_mention(eid, aid, spec_id)

    return created


if __name__ == "__main__":
    from src.store import init_store
    init_store()
    print(f"seeded {seed()} specs")
