"""Ingestion Conflict Detection — scan files for contradictions against stored canon_domain graph."""

import logging
from typing import Optional
from uuid import UUID
from openai import OpenAI
from src.store import Store
from src.config import llm_model
from src.models import CanonEntry, GroundingType, GROUNDING_TYPE_SECTION_TYPES

log = logging.getLogger(__name__)


def check_grounding_type_mismatch(entry: CanonEntry, domain_grounding_type: GroundingType) -> dict | None:
    """Flag a section_type that doesn't fit the domain's grounding_type (e.g. a
    'headline' on an engineering_spec domain). Soft severity only, same as an
    ingest conflict — surfaced for human review, never blocks the write.
    GroundingTypes with no dedicated vocabulary yet (brand_guide, corp_narrative,
    persona_library) accept any section_type, so this always returns None for them.
    """
    allowed = GROUNDING_TYPE_SECTION_TYPES.get(domain_grounding_type)
    if allowed is None:
        return None
    section_type = entry.section_type
    if section_type in allowed or getattr(section_type, "value", section_type) in {getattr(a, "value", a) for a in allowed}:
        return None
    return {
        "entry_id": str(entry.id),
        "section_type": getattr(section_type, "value", section_type),
        "grounding_type": getattr(domain_grounding_type, "value", domain_grounding_type),
        "explanation": f"'{getattr(section_type, 'value', section_type)}' isn't one of the section types expected for a "
                       f"{getattr(domain_grounding_type, 'value', domain_grounding_type)} domain.",
        "severity": "soft",
    }

def check_ingest_conflicts(
    domain_id: UUID,
    new_entries: list[CanonEntry],
    store: Store,
    openai_client: Optional[OpenAI] = None
) -> list[dict]:
    """
    Compare newly parsed entries against existing active entries in the domain.
    Flags entries with high semantic similarity and parses them using the LLM for contradictions.
    """
    from src.config import llm_client
    client = openai_client or llm_client()
    conflicts = []

    # 0. Grounding-type mismatch check (soft, no LLM call needed)
    domain = store.get_canon_domain(domain_id)
    if domain is not None:
        for new_entry in new_entries:
            mismatch = check_grounding_type_mismatch(new_entry, domain.grounding_type)
            if mismatch:
                conflicts.append(mismatch)

    # 1. Fetch existing approved canon_entries
    existing_entries = store.get_canon_entries(domain_id, include_unapproved=False)
    if not existing_entries:
        return conflicts

    # 2. Build mapping of entries
    for new_entry in new_entries:
        for old_entry in existing_entries:
            # Only compare entries of matching section types to avoid noise
            if new_entry.section_type != old_entry.section_type:
                continue

            # Compare contents using simple keyword intersection or LLM verification
            # If there's an overlap/similarity, trigger conflict prompt checks
            is_candidate = False
            words_new = set(new_entry.content.lower().split())
            words_old = set(old_entry.content.lower().split())
            intersection = words_new & words_old
            
            # Simple threshold: if >35% word overlap, trigger verification
            if len(intersection) / max(len(words_new), 1) > 0.35:
                is_candidate = True

            if is_candidate:
                # Prompt LLM to verify if there is an actual logical contradiction
                prompt = (
                    f"You are a factual check auditor.\n"
                    f"Determine if the new proposed claim contradicts or opposes the existing live claim.\n\n"
                    f"Live Claim (Statement A): {old_entry.content}\n"
                    f"New Claim (Statement B): {new_entry.content}\n\n"
                    f"Return a JSON object:\n"
                    f'{{"is_conflict": true/false, "explanation": "Why they contradict or differ", '
                    f'"severity": "hard" / "soft"}}\n'
                    f"Rules:\n"
                    f"- 'hard' conflict: explicit contradictions (e.g. Statement A says '24/7 support', Statement B says 'no weekend support')\n"
                    f"- 'soft' conflict: updates/upgrades (e.g., A says 'SLA 99%', B says 'SLA 99.9%')"
                )
                try:
                    import json
                    response = client.chat.completions.create(
                        model=llm_model("gpt-4o-mini"),
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.0,
                        response_format={"type": "json_object"}
                    )
                    res = json.loads(response.choices[0].message.content)
                    if res.get("is_conflict"):
                        conflicts.append({
                            "new_entry_content": new_entry.content,
                            "existing_entry_id": str(old_entry.id),
                            "existing_entry_content": old_entry.content,
                            "explanation": res.get("explanation", ""),
                            "severity": res.get("severity", "soft")
                        })
                except Exception as e:
                    log.error(f"Conflict check LLM call failed: {e}")

    return conflicts
