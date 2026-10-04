"""Competitive intel: competitor document import, gap analysis, battlecard auto-sharpen.

Every extracted claim is anchored to the exact source span it came from (the
character range in the source document), not just a document-level reference —
same evidence-grounding posture as Tier 1 verbatim-lock elsewhere in this
product. A claim the LLM can't locate verbatim in the source is discarded,
not kept with a fuzzy citation.
"""

import json
import logging
import re
from typing import Optional
from uuid import UUID, uuid4

from openai import OpenAI

from src.config import llm_model
from src.models import CanonEntry, EntryStatus, GroundingType, NodeType, RelType, SectionType
from src.store import Store

log = logging.getLogger(__name__)


def _normalize_ws(text: str) -> str:
    """Collapse whitespace so formatting differences don't fail a verbatim check."""
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _locate_span(excerpt: str, document_text: str) -> Optional[tuple[int, int]]:
    """Find excerpt's exact character range in document_text, matching on
    normalized whitespace but returning offsets into the *original* text.
    Returns None if the excerpt isn't a genuine verbatim substring — the
    caller must discard the claim rather than keep it with a fabricated span.
    """
    norm_doc = _normalize_ws(document_text)
    norm_excerpt = _normalize_ws(excerpt)
    if not norm_excerpt or norm_excerpt not in norm_doc:
        return None
    # Map the normalized-text match back to original offsets by walking the
    # original string with the same whitespace-collapsing rule.
    pattern = re.escape(norm_excerpt).replace(r"\ ", r"\s+")
    m = re.search(pattern, document_text, re.IGNORECASE)
    if not m:
        return None
    return m.start(), m.end()


def extract_competitor_claims(
    document_text: str,
    competitor_name: str,
    domain_id: UUID,
    store: Store,
    client: Optional[OpenAI] = None,
    dri: str = "",
) -> list[CanonEntry]:
    """Extract competitor strength/weakness claims from a competitor document,
    each anchored to its exact source span. domain_id must be an existing
    competitive_brief CanonDomain (create it first via the normal domain flow).
    """
    domain = store.get_canon_domain(domain_id)
    if domain is None:
        raise ValueError(f"domain not found: {domain_id}")
    if GroundingType(domain.grounding_type) != GroundingType.COMPETITIVE_BRIEF:
        raise ValueError(f"domain {domain_id} is not a competitive_brief domain")

    if client is None:
        from src.config import llm_client  # local import: re-resolves per call, so tests can patch src.config.llm_client
        client = llm_client()
    prompt = (
        f"You are extracting competitor claims from a document about {competitor_name}, "
        f"verbatim — quote exact sentences, never paraphrase.\n\n"
        f"Document:\n{document_text}\n\n"
        f'Return a JSON object: {{"claims": [{{"quote": "<exact sentence from the document, '
        f'copy-pasted, not reworded>", "type": "strength" or "weakness"}}]}}\n'
        f"Only include claims that are clear capability/positioning statements. "
        f"'quote' MUST be an exact substring of the document — if you can't quote exactly, omit the claim."
    )
    try:
        response = client.chat.completions.create(
            model=llm_model("gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.choices[0].message.content)
    except Exception as e:
        log.error("Competitor claim extraction LLM call failed: %s", e)
        return []

    entries: list[CanonEntry] = []
    for claim in parsed.get("claims", []):
        quote = claim.get("quote", "")
        span = _locate_span(quote, document_text)
        if span is None:
            log.warning("Discarding non-verbatim competitor claim (not found in source): %r", quote[:80])
            continue
        start, end = span
        section_type = SectionType.COMPETITOR_WEAKNESS if claim.get("type") == "weakness" else SectionType.COMPETITOR_STRENGTH
        entry = CanonEntry(
            id=uuid4(),
            canon_domain_id=domain_id,
            section_type=section_type,
            priority=3,
            content=document_text[start:end],  # the verbatim span itself, not the LLM's copy of it
            status=EntryStatus.DRAFT,
            dri=dri,
            source_chunk_id=f"chars:{start}-{end}",
        )
        store.upsert_canon_entry(entry)
        entries.append(entry)
    return entries


def analyze_competitive_gap(our_domain_id: UUID, competitor_domain_id: UUID, store: Store) -> dict:
    """Compare our canon entries against a competitor's extracted claims.
    Creates a CONTRADICTS edge (graph-native, not a side table) wherever a
    competitor claim and one of our entries address the same ground, with
    provenance set to the competitor's exact quoted span. Returns a summary.
    """
    our_entries = store.get_canon_entries(our_domain_id, include_unapproved=True)
    their_entries = store.get_canon_entries(competitor_domain_id, include_unapproved=True)

    differentiated, challenged, edges_created = [], [], 0
    for their_entry in their_entries:
        their_words = set(_normalize_ws(their_entry.content).split())
        best_match, best_overlap = None, 0.0
        for our_entry in our_entries:
            our_words = set(_normalize_ws(our_entry.content).split())
            if not our_words:
                continue
            overlap = len(their_words & our_words) / max(len(their_words), 1)
            if overlap > best_overlap:
                best_match, best_overlap = our_entry, overlap

        if best_match is None or best_overlap < 0.15:
            # Nothing of ours addresses this claim at all — a real gap, not a graph edge.
            differentiated.append({"their_claim": their_entry.content, "note": "no matching canon entry — uncovered gap"})
            continue

        if their_entry.section_type == SectionType.COMPETITOR_WEAKNESS.value or their_entry.section_type == SectionType.COMPETITOR_WEAKNESS:
            # Their own stated weakness, matched to our strength — differentiation, not a contradiction.
            differentiated.append({"their_claim": their_entry.content, "our_entry_id": str(best_match.id), "our_claim": best_match.content})
            continue

        store.add_edge(
            src_type=NodeType.CANON_ENTRY.value, src_id=str(their_entry.id),
            dst_type=NodeType.CANON_ENTRY.value, dst_id=str(best_match.id),
            rel_type=RelType.CONTRADICTS.value,
            provenance=their_entry.content,  # the competitor's exact verbatim claim — the evidence span
            created_by="competitive_gap_analysis",
        )
        edges_created += 1
        challenged.append({"their_claim": their_entry.content, "our_entry_id": str(best_match.id), "our_claim": best_match.content})

    return {"differentiated": differentiated, "challenged": challenged, "edges_created": edges_created}


def sharpen_battlecard(competitor_name: str, competitor_domain_id: UUID, our_domain_id: UUID, store: Store) -> dict:
    """Assemble battlecard.json-shaped content (competitor, our_strengths,
    their_weaknesses, counter_messaging, proof_points) by walking the
    CONTRADICTS edges analyze_competitive_gap already created — reuses the
    graph rather than re-deriving the comparison.
    """
    their_entries = store.get_canon_entries(competitor_domain_id, include_unapproved=True)
    our_strengths, their_weaknesses, counter_messaging, proof_points = [], [], [], []

    for their_entry in their_entries:
        if their_entry.section_type in (SectionType.COMPETITOR_WEAKNESS.value, SectionType.COMPETITOR_WEAKNESS):
            their_weaknesses.append(their_entry.content)
            continue
        edges = store.list_edges(rel_type=RelType.CONTRADICTS.value, src_id=str(their_entry.id))
        for edge in edges:
            our_entry = store.get_canon_entry(UUID(edge["dst_id"]))
            if our_entry:
                our_strengths.append(our_entry.content)
                counter_messaging.append(
                    f"They claim: \"{their_entry.content}\" — counter with: \"{our_entry.content}\""
                )
                if our_entry.content_tier == "tier_1_locked":
                    proof_points.append(our_entry.content)

    return {
        "competitor": competitor_name,
        "our_strengths": our_strengths,
        "their_weaknesses": their_weaknesses,
        "counter_messaging": counter_messaging,
        "proof_points": proof_points,
    }
