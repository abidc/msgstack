"""Seeds MsgStack's own real canon domain — dogfooding, not a fictional demo.

This is MsgStack's actual positioning, written using the product itself.
Additive only: does not touch seed_data/seed.py or its 10 fictional demo
companies. Run with:

    python -c "from seed_data.seed_msgstack_dogfood import seed; seed()"
"""

from datetime import datetime
from uuid import uuid4

from src.models import (
    Channel,
    CanonDomain,
    CanonEntry,
    ContentTier,
    DomainStatus,
    GroundingType,
    Persona,
    SectionType,
)
from src.store import init_store


def seed():
    """Seed MsgStack's own Message House canon domain. Returns the domain id."""
    store = init_store()
    now = datetime.utcnow()

    domain = CanonDomain(
        id=uuid4(),
        name="MsgStack",
        source="manual",
        grounding_type=GroundingType.MESSAGE_HOUSE,
        summary=(
            "Self-hosted knowledge graph that locks an organization's approved claims "
            "so AI-generated content quotes them exactly instead of guessing. Message "
            "House is the flagship grounding type; Engineering Spec and Policy Shield "
            "extend the same graph to Engineering and Legal."
        ),
        audience="PMM leads, engineering leads, and legal/compliance owners at companies whose AI-generated content keeps drifting from approved truth",
        brand_personality="Precise, unglamorous, trustworthy. Shows its work instead of promising magic.",
        positioning=(
            "Your AI assistants keep getting your product claims, your pricing, your "
            "legal language slightly wrong — not because the model is bad, but because "
            "it has nothing authoritative to check against. MsgStack is that authority: "
            "a real knowledge graph of your approved claims, with a lock on the ones that "
            "must never be paraphrased, reachable from the tools your team already uses."
        ),
        tagline="Say it once. Say it right, everywhere.",
        differentiation=(
            "Prevention-by-construction, not after-the-fact drift scoring: claims are "
            "locked and reproduced verbatim at generation time, not checked against a "
            "baseline after the fact. A real typed graph (not vector-only search) spans "
            "Marketing, Engineering, and Legal in one place. Self-hosted, Apache 2.0, "
            "MCP-native — your canon never leaves your infrastructure."
        ),
        status=DomainStatus.ACTIVE,
        department="Product Marketing",
        last_synced=now,
        last_reviewed=now,
        dri="Abid Chaudhry",
    )
    store.upsert_canon_domain(domain)

    entries = [
        CanonEntry(
            canon_domain_id=domain.id, section_type=SectionType.HEADLINE, priority=1,
            content="Your AI keeps almost getting it right. MsgStack closes the gap.",
            variants={
                "linkedin": "Your AI keeps almost getting your product right. Here's the fix.",
                "email": "Stop fixing AI-generated claims after the fact.",
            },
            personas=["PMM Lead", "Engineering Lead"], channels=[Channel.ALL],
            content_tier=ContentTier.TIER_2_STRUCTURED, dri="Abid Chaudhry",
        ),
        CanonEntry(
            canon_domain_id=domain.id, section_type=SectionType.POSITIONING, priority=1,
            content="MsgStack is a self-hosted knowledge graph that locks your organization's approved claims so AI-generated content quotes them exactly — not a dashboard you have to remember to check, a graph your tools can query directly.",
            personas=["PMM Lead", "Engineering Lead", "Legal/Compliance Owner"], channels=[Channel.ALL],
            content_tier=ContentTier.TIER_1_LOCKED, dri="Abid Chaudhry",
        ),
        CanonEntry(
            canon_domain_id=domain.id, section_type=SectionType.BENEFIT, priority=1,
            content="Locked claims are reproduced verbatim at generation time — prevention-by-construction, not a drift score you review after the content already shipped.",
            variants={"linkedin": "We lock claims before generation, not flag drift after."},
            personas=["PMM Lead", "Legal/Compliance Owner"], channels=[Channel.ALL],
            content_tier=ContentTier.TIER_1_LOCKED, dri="Abid Chaudhry",
        ),
        CanonEntry(
            canon_domain_id=domain.id, section_type=SectionType.BENEFIT, priority=2,
            content="One real graph spans Marketing, Engineering, and Legal — a legal disclaimer can depend on a product capability claim, and both update together.",
            personas=["Engineering Lead", "Legal/Compliance Owner"], channels=[Channel.ALL],
            content_tier=ContentTier.TIER_2_STRUCTURED, dri="Abid Chaudhry",
        ),
        CanonEntry(
            canon_domain_id=domain.id, section_type=SectionType.BENEFIT, priority=3,
            content="Ask it from Slack or Teams and get a cited, grounded draft back in the channel — no context switch to a separate dashboard.",
            variants={"linkedin": "Ask it from Slack or Teams. Get a grounded, cited draft back in the channel."},
            personas=["PMM Lead", "Engineering Lead"], channels=[Channel.ALL],
            content_tier=ContentTier.TIER_2_STRUCTURED, dri="Abid Chaudhry",
        ),
        CanonEntry(
            canon_domain_id=domain.id, section_type=SectionType.USE_CASE, priority=1,
            content="In active development: a Slack and Microsoft Teams agent that is itself an MCP client against this server — ask a question in a channel, it calls MsgStack's grounding tools and returns a cited, tier-aware draft with Approve/Edit/Regenerate actions. Not yet shipped — see ROADMAP.md.",
            personas=["PMM Lead", "Engineering Lead"], channels=[Channel.ALL],
            content_tier=ContentTier.TIER_1_LOCKED, dri="Abid Chaudhry",
        ),
        CanonEntry(
            canon_domain_id=domain.id, section_type=SectionType.COMPETITOR_WEAKNESS, priority=1,
            content="Highspot/Seismic ships an MCP server and a GTM agent, but it's grounded in CRM/buyer-engagement analytics, not a typed claims graph — no per-entry verbatim lock, no cross-department dependency graph.",
            personas=["PMM Lead"], channels=[Channel.ALL],
            content_tier=ContentTier.TIER_2_STRUCTURED, dri="Abid Chaudhry",
        ),
        CanonEntry(
            canon_domain_id=domain.id, section_type=SectionType.COMPETITOR_WEAKNESS, priority=2,
            content="Writer.com is the closest structural analog — real knowledge-graph retrieval plus governance — but has no per-claim verbatim-vs-paraphrase tiering, and isn't vertically a message-house tool.",
            personas=["PMM Lead"], channels=[Channel.ALL],
            content_tier=ContentTier.TIER_2_STRUCTURED, dri="Abid Chaudhry",
        ),
        CanonEntry(
            canon_domain_id=domain.id, section_type=SectionType.OBJECTION, priority=1,
            content="\"We already have a brand/content tool.\" Most content tools ground on vector search over documents, not a typed graph with a verbatim lock — they can retrieve something similar to your approved claim, not reproduce it exactly, and they can't trace a legal disclaimer's dependency on a product capability the way a real graph can.",
            variants={"linkedin": "Vector search finds something similar. A locked claim IS the claim."},
            personas=["PMM Lead"], channels=[Channel.ALL],
            content_tier=ContentTier.TIER_2_STRUCTURED, dri="Abid Chaudhry",
        ),
        CanonEntry(
            canon_domain_id=domain.id, section_type=SectionType.OBJECTION, priority=2,
            content="\"Is our data safe?\" MsgStack is Apache 2.0 and fully self-hostable — your canon never leaves your infrastructure. There is no hosted-only tier requirement.",
            personas=["Legal/Compliance Owner", "Engineering Lead"], channels=[Channel.ALL],
            content_tier=ContentTier.TIER_1_LOCKED, dri="Abid Chaudhry",
        ),
        CanonEntry(
            canon_domain_id=domain.id, section_type=SectionType.PROOF_POINT, priority=1,
            content="Real cross-domain graph: entities, typed edges (DEPENDS_ON, INFORMS, SUPERSEDES, CONTRADICTS, OWNS, IMPLEMENTS), k-hop traversal with RRF fusion against vector retrieval, and transitive change propagation — not a per-document containment tree.",
            personas=["Engineering Lead"], channels=[Channel.ALL],
            content_tier=ContentTier.TIER_1_LOCKED, dri="Abid Chaudhry",
        ),
        CanonEntry(
            canon_domain_id=domain.id, section_type=SectionType.FOUNDING_STORY, priority=1,
            content="Built after watching AI-generated marketing, sales, and engineering content drift from approved truth in disconnected docs nobody kept current — then pivoted away from that problem entirely for two months chasing a narrower engineering-only framing before reverting back to the original, broader canon-layer thesis with the real infrastructure built along the way kept intact.",
            personas=["PMM Lead", "Engineering Lead"], channels=[Channel.ALL],
            content_tier=ContentTier.TIER_3_GROUNDED, dri="Abid Chaudhry",
        ),
    ]
    for entry in entries:
        store.upsert_canon_entry(entry)

    personas = [
        Persona(
            canon_domain_id=domain.id, name="PMM Lead",
            description="Owns product positioning and messaging; needs every channel saying the same approved thing.",
            pain_points=["Content drifts from approved messaging across channels", "No single source of truth for claims", "Re-explaining positioning to every new AI tool"],
            buying_triggers=["Inconsistent claims caught by a customer or exec", "Rolling out a new AI content workflow", "Rebrand or repositioning"],
            objections=["We already have a brand/content tool", "Will the team actually keep it updated"],
        ),
        Persona(
            canon_domain_id=domain.id, name="Engineering Lead",
            description="Wants AI copilots and internal tools grounded in real API contracts and SLAs, not hallucinated specs.",
            pain_points=["Copilots hallucinate rate limits and deprecated endpoints", "Docs drift from the real API", "No graph connecting specs to downstream claims"],
            buying_triggers=["An AI tool shipped a wrong API claim publicly", "Standing up an internal dev-facing assistant"],
            objections=["Is our data safe self-hosting this", "Another tool to maintain"],
        ),
        Persona(
            canon_domain_id=domain.id, name="Legal/Compliance Owner",
            description="Needs legal and compliance language reproduced verbatim, never paraphrased by an LLM.",
            pain_points=["AI tools paraphrase legal disclaimers into something wrong", "No audit trail for who approved what language"],
            buying_triggers=["A paraphrased disclaimer caused a real compliance question", "SOC2/GDPR language needs to be provably consistent across every surface"],
            objections=["Verbatim lock sounds rigid — can it still adapt tone", "Who's the DRI when it breaks"],
        ),
    ]
    for persona in personas:
        store.upsert_persona(persona)

    return domain.id


if __name__ == "__main__":
    print("seeded MsgStack dogfood domain:", seed())
