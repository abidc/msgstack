"""Seed demo content for the engineering_spec and policy_shield grounding types.

Separate from seed.py's 10 message houses (Message House grounding type) —
called from the end of seed() so a normal reseed picks this up too, but kept
in its own file/function so it can be run or inspected independently.
Fictional company, matching the register of the existing demo corpus.
"""

from datetime import datetime
from uuid import uuid4

from src.models import CanonDomain, CanonEntry, ContentTier, DomainStatus, EntryStatus, GroundingType, SectionType
from src.store import Store


def seed_grounding_types(store: Store) -> int:
    """Seed one Engineering Spec domain and one Policy Shield domain. Returns domain count."""
    now = datetime.utcnow()

    eng = _acme_api_engineering_spec(now)
    legal = _acme_legal_policy_shield(now)

    for domain_data in (eng, legal):
        domain = domain_data["domain"]
        store.upsert_canon_domain(domain)
        for entry in domain_data["entries"]:
            store.upsert_canon_entry(entry)

    return 2


def _acme_api_engineering_spec(now):
    domain_id = uuid4()
    domain = CanonDomain(
        id=domain_id,
        name="Acme Cloud Security — Public API v2",
        source="seed",
        grounding_type=GroundingType.ENGINEERING_SPEC,
        summary="REST/gRPC API for Acme's threat detection platform: rate limits, versioning, and deprecation policy.",
        audience="Integrating engineers, partner developers",
        positioning="The API contract integrators build against — verbatim, not paraphrased.",
        status=DomainStatus.ACTIVE,
        department="Engineering",
        last_synced=now,
        last_reviewed=now,
        dri="platform-eng@acme.example",
    )
    entries = [
        CanonEntry(canon_domain_id=domain_id, section_type=SectionType.API_CONTRACT, priority=1,
                   content="POST /v2/threats/scan accepts up to 50 MB per request and returns a scan_id within 200ms (p99).",
                   status=EntryStatus.LOCKED, content_tier=ContentTier.TIER_1_LOCKED, dri="platform-eng@acme.example"),
        CanonEntry(canon_domain_id=domain_id, section_type=SectionType.API_CONTRACT, priority=2,
                   content="All v2 endpoints require an `X-Acme-Key` header; the legacy `api_key` query parameter is not accepted on v2.",
                   status=EntryStatus.LOCKED, content_tier=ContentTier.TIER_1_LOCKED, dri="platform-eng@acme.example"),
        CanonEntry(canon_domain_id=domain_id, section_type=SectionType.SLA_COMMITMENT, priority=1,
                   content="Rate limit: 1,000 requests/minute per API key, burst to 1,200 for 10 seconds. 429 responses include a Retry-After header.",
                   status=EntryStatus.LOCKED, content_tier=ContentTier.TIER_1_LOCKED, dri="platform-eng@acme.example"),
        CanonEntry(canon_domain_id=domain_id, section_type=SectionType.VERSIONING_POLICY, priority=1,
                   content="A new major API version ships at most once per 12 months. Minor versions are additive-only — no field removals or type changes.",
                   status=EntryStatus.APPROVED, content_tier=ContentTier.TIER_2_STRUCTURED, dri="platform-eng@acme.example"),
        CanonEntry(canon_domain_id=domain_id, section_type=SectionType.DEPRECATION_NOTICE, priority=1,
                   content="API v1 is deprecated as of 2026-06-01 and will return 410 Gone starting 2027-06-01. v1 → v2 migration guide: see /docs/migrate-v1-v2.",
                   status=EntryStatus.LOCKED, content_tier=ContentTier.TIER_1_LOCKED, dri="platform-eng@acme.example"),
        CanonEntry(canon_domain_id=domain_id, section_type=SectionType.SECURITY_REQUIREMENT, priority=1,
                   content="All API traffic must use TLS 1.2+. Webhook callback URLs must be HTTPS; HTTP callback URLs are rejected at registration time.",
                   status=EntryStatus.LOCKED, content_tier=ContentTier.TIER_1_LOCKED, dri="platform-eng@acme.example"),
    ]
    return {"domain": domain, "entries": entries}


def _acme_legal_policy_shield(now):
    domain_id = uuid4()
    domain = CanonDomain(
        id=domain_id,
        name="Acme Cloud Security — Legal & Compliance",
        source="seed",
        grounding_type=GroundingType.POLICY_SHIELD,
        summary="Pre-approved legal disclaimers, privacy rules, and compliance language for Acme's platform.",
        audience="Sales, support, marketing — anyone quoting legal/compliance language externally",
        positioning="Legal language retrieved verbatim. No paraphrasing, ever.",
        status=DomainStatus.ACTIVE,
        department="Legal",
        last_synced=now,
        last_reviewed=now,
        dri="legal@acme.example",
    )
    entries = [
        CanonEntry(canon_domain_id=domain_id, section_type=SectionType.LEGAL_DISCLAIMER, priority=1,
                   content="Acme Cloud Security's threat predictions are probabilistic risk assessments, not guarantees of breach prevention.",
                   status=EntryStatus.LOCKED, content_tier=ContentTier.TIER_1_LOCKED, dri="legal@acme.example"),
        CanonEntry(canon_domain_id=domain_id, section_type=SectionType.PRIVACY_RULE, priority=1,
                   content="Customer scan data is retained for 90 days and deleted automatically thereafter; customers may request earlier deletion via support@acme.example.",
                   status=EntryStatus.LOCKED, content_tier=ContentTier.TIER_1_LOCKED, dri="legal@acme.example"),
        CanonEntry(canon_domain_id=domain_id, section_type=SectionType.COMPLIANCE_ASSERTION, priority=1,
                   content="Acme Cloud Security is SOC 2 Type II certified (annual audit, most recent report dated 2026-03-15).",
                   status=EntryStatus.LOCKED, content_tier=ContentTier.TIER_1_LOCKED, dri="legal@acme.example"),
        CanonEntry(canon_domain_id=domain_id, section_type=SectionType.COMPLIANCE_RESPONSE, priority=1,
                   content="When asked about GDPR: Acme acts as a data processor under GDPR Art. 28; a signed DPA is available on request from legal@acme.example.",
                   status=EntryStatus.LOCKED, content_tier=ContentTier.TIER_1_LOCKED, dri="legal@acme.example"),
    ]
    return {"domain": domain, "entries": entries}
