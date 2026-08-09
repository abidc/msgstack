"""Seed MsgStack with a synthetic engineering corpus.

This models a small platform team's actual documentation surface: five services
whose specs genuinely depend on one another. It exists to demonstrate the two
things that distinguish MsgStack from vector RAG over a wiki —

  1. assertions carry a *type* (a rate limit is a constraint, not prose), and
  2. facts in different specs are connected, so changing one flags the rest.

The dependency edges below are the point. `payments-api` declares a rate limit;
`gateway-config` sets the shedding threshold that limit assumes; `checkout-web`
quotes the limit back to users. Edit the gateway threshold and both downstream
assertions are marked outdated automatically.
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


def _spec(name, summary, schema_type, dri, positioning="", tagline=""):
    return Spec(
        id=uuid4(), name=name, summary=summary, schema_type=schema_type,
        status=SpecStatus.ACTIVE, department="Platform", dri=dri,
        positioning=positioning, tagline=tagline, source="seed",
    )


CORPUS: list[dict] = [
    {
        "spec": _spec(
            "payments-api",
            "Card and wallet payment capture for checkout. Owns the charge "
            "lifecycle and the public /v2/charges contract.",
            SchemaType.ENGINEERING_SPEC, "@jdoe",
            positioning="The only service authorised to move money. Everything "
                        "else proposes a charge; payments-api decides.",
        ),
        "assertions": [
            (AssertionType.CONSTRAINT,
             "Rate limit is 1000 requests/minute per API key, with a burst "
             "allowance of 1500 over any 10-second window.", _T1, _L, "rate-limit"),
            (AssertionType.SLA,
             "p99 latency under 250ms and 99.95% monthly availability, measured "
             "at the gateway, excluding client-side network time.", _T1, _L, "latency-slo"),
            (AssertionType.INTERFACE_CONTRACT,
             "POST /v2/charges is idempotent on the Idempotency-Key header. "
             "Replaying a key within 24h returns the original charge, not a new one.", _T1, _L, "idempotency"),
            (AssertionType.DEPENDENCY,
             "Requires auth-service >= 4.2 for token introspection. Versions "
             "below 4.2 do not return the scope claim and every request 403s.", _T2, _A, "auth-dep"),
            (AssertionType.DEPRECATION,
             "The v1 checkout endpoint is removed on 2027-01-31. v1 has been "
             "read-only since 2026-06-01; migrate to /v2/charges.", _T1, _L, "v1-sunset"),
            (AssertionType.CONFIG_DEFAULT,
             "PAYMENTS_TIMEOUT_MS defaults to 8000. Raising it above 10000 "
             "exceeds the gateway's own timeout and produces 504s.", _T2, _A, "timeout-default"),
            (AssertionType.LIMITATION,
             "Partial refunds are not supported for wallet charges — only "
             "full reversal. Card charges support partial refunds.", _T2, _A, None),
            (AssertionType.SECURITY_POSTURE,
             "PAN data never reaches application logs; the tokenisation proxy "
             "strips it before the request enters the service boundary.", _T1, _L, None),
        ],
        "audiences": [
            ("Integrating engineer",
             "Building a checkout flow against the public API.",
             [("Can I retry a failed charge safely?",
               "Yes — reuse the same Idempotency-Key. A replay within 24h returns "
               "the original charge rather than double-charging."),
              ("Why am I getting 403s after upgrading?",
               "auth-service below 4.2 omits the scope claim. Check its version first.")]),
            ("On-call SRE",
             "Paged against the payments error budget.",
             [("Charges are 504ing in bulk — where do I look?",
               "Compare PAYMENTS_TIMEOUT_MS against the gateway timeout. If it was "
               "raised above 10000 the gateway gives up first.")]),
        ],
    },
    {
        "spec": _spec(
            "gateway-config",
            "Edge routing, TLS termination and load shedding for all public "
            "traffic. Sets the limits every downstream service inherits.",
            SchemaType.ENGINEERING_SPEC, "@mchen",
        ),
        "assertions": [
            (AssertionType.CONSTRAINT,
             "The gateway sheds load above 1200 requests/minute aggregate per "
             "upstream, returning 503 with Retry-After.", _T1, _L, "rate-limit"),
            (AssertionType.CONFIG_DEFAULT,
             "Upstream request timeout is 10000ms. This is the ceiling for every "
             "service behind the gateway; per-service timeouts must sit below it.", _T1, _L, "timeout-default"),
            (AssertionType.SLA,
             "Gateway adds no more than 15ms p99 overhead to any upstream call.", _T2, _A, "latency-slo"),
            (AssertionType.SECURITY_POSTURE,
             "TLS 1.2 is refused as of 2026-07-01. Clients must negotiate TLS 1.3.", _T1, _L, None),
            (AssertionType.RUNBOOK_STEP,
             "To raise an upstream's shed threshold: edit tier config, apply to "
             "canary, watch 503 rate for 10 minutes, then roll to fleet.", _T3, _A, None),
        ],
        "audiences": [
            ("Platform engineer",
             "Owns gateway configuration and tier assignment.",
             [("A service wants a higher rate limit — what has to change?",
               "The shed threshold here, not just the service's own limit. The "
               "gateway sheds first, so raising the service limit alone does nothing.")]),
        ],
    },
    {
        "spec": _spec(
            "auth-service",
            "Token issuance and introspection. Every authenticated request in "
            "the platform resolves through it.",
            SchemaType.ENGINEERING_SPEC, "@rpatel",
        ),
        "assertions": [
            (AssertionType.VERSION_POLICY,
             "Minor versions are backward compatible within a major. The scope "
             "claim was added in 4.2 and is required by downstream services.", _T1, _L, "auth-dep"),
            (AssertionType.INTERFACE_CONTRACT,
             "POST /introspect returns active=false rather than 401 for an "
             "expired token. Callers must check the body, not just the status.", _T1, _L, None),
            (AssertionType.SLA,
             "Introspection responds in under 40ms p99. It sits in the request "
             "path of every other service, so its budget is the tightest.", _T1, _L, "latency-slo"),
            (AssertionType.CONFIG_DEFAULT,
             "Access tokens live 3600s, refresh tokens 30 days.", _T2, _A, None),
            (AssertionType.SECURITY_POSTURE,
             "Signing keys rotate every 90 days with a 7-day overlap window "
             "during which both the old and new key validate.", _T1, _L, None),
        ],
        "audiences": [
            ("Integrating engineer",
             "Consuming tokens from another service.",
             [("Why does an expired token return 200?",
               "By design — check active=false in the body. A 401 means the "
               "introspection call itself was unauthorised, not the token.")]),
        ],
    },
    {
        "spec": _spec(
            "checkout-web",
            "Customer-facing checkout UI. Consumes payments-api and surfaces "
            "its limits and errors to end users.",
            SchemaType.ENGINEERING_SPEC, "@slue",
        ),
        "assertions": [
            (AssertionType.DEPENDENCY,
             "Calls POST /v2/charges directly. Still contains a v1 fallback "
             "path that must be removed before the 2027-01-31 sunset.", _T2, _A, "v1-sunset"),
            (AssertionType.CAPABILITY,
             "Displays a rate-limit notice to the user when payments-api returns "
             "429, quoting the 1000 req/min figure verbatim.", _T2, _A, "rate-limit"),
            (AssertionType.LIMITATION,
             "The refund UI offers partial refunds for every payment method, "
             "including wallet — which payments-api rejects.", _T3, _A, None),
            (AssertionType.DECISION,
             "We render errors client-side rather than server-side so the "
             "checkout shell stays cacheable at the edge. Revisit if SEO matters.", _T3, _A, None),
        ],
        "audiences": [
            ("Frontend engineer",
             "Maintains the checkout flow.",
             [("What should a 429 show the user?",
               "The rate-limit notice quoting the current documented limit. Do not "
               "hardcode the number — it is a locked assertion in payments-api.")]),
        ],
    },
    {
        "spec": _spec(
            "incident-2026-07-14",
            "Postmortem: checkout outage caused by a per-service timeout raised "
            "above the gateway ceiling.",
            SchemaType.INCIDENT_RECORD, "@mchen",
        ),
        "assertions": [
            (AssertionType.DECISION,
             "Root cause: PAYMENTS_TIMEOUT_MS was raised to 12000 to absorb a "
             "slow downstream, exceeding the gateway's 10000ms ceiling. The "
             "gateway timed out first and returned 504 while the charge succeeded.", _T1, _L, "timeout-default"),
            (AssertionType.RUNBOOK_STEP,
             "Detection gap: charge-succeeded-but-504 was invisible because we "
             "alert on gateway status, not on charge-state divergence. Added a "
             "reconciliation check between gateway 5xx and settled charges.", _T3, _A, None),
            (AssertionType.LIMITATION,
             "During the window, 1,340 charges settled while the customer saw a "
             "failure. All were reconciled within 48h; none were double-charged, "
             "because /v2/charges is idempotent.", _T2, _A, "idempotency"),
        ],
        "audiences": [],
    },
]


#: Cross-spec relationships. (src_spec, src_tag, rel, dst_spec, dst_tag)
#: DEPENDS_ON and INFORMS propagate: editing the destination marks the source
#: outdated. This is the wiring that makes the corpus a graph rather than five
#: unrelated documents.
EDGES = [
    ("payments-api", "rate-limit",      "DEPENDS_ON", "gateway-config", "rate-limit"),
    ("payments-api", "timeout-default", "DEPENDS_ON", "gateway-config", "timeout-default"),
    ("payments-api", "latency-slo",     "DEPENDS_ON", "auth-service",   "latency-slo"),
    ("payments-api", "auth-dep",        "DEPENDS_ON", "auth-service",   "auth-dep"),
    ("checkout-web", "rate-limit",      "DEPENDS_ON", "payments-api",   "rate-limit"),
    ("checkout-web", "v1-sunset",       "DEPENDS_ON", "payments-api",   "v1-sunset"),
    ("gateway-config", "latency-slo",   "INFORMS",    "payments-api",   "latency-slo"),
    ("incident-2026-07-14", "timeout-default", "INFORMS", "payments-api", "timeout-default"),
    ("incident-2026-07-14", "idempotency",     "INFORMS", "payments-api", "idempotency"),
]

#: Entities shared across specs. These are the bridges that let a traversal
#: leave one spec without an explicitly authored edge.
ENTITIES = {
    "checkout-endpoint": [("payments-api", "idempotency"), ("checkout-web", "rate-limit"),
                          ("payments-api", "v1-sunset")],
    "rate-limiting":     [("payments-api", "rate-limit"), ("gateway-config", "rate-limit"),
                          ("checkout-web", "rate-limit")],
    "request-timeout":   [("payments-api", "timeout-default"), ("gateway-config", "timeout-default"),
                          ("incident-2026-07-14", "timeout-default")],
    "token-introspection": [("auth-service", "auth-dep"), ("payments-api", "auth-dep")],
}


def seed() -> int:
    """Populate the store with the engineering corpus. Idempotent by spec name:
    an existing spec of the same name is left alone rather than duplicated."""
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
        eid = store.resolve_entity(entity_name, entity_type="component")
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
