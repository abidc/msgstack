"""Ingestion Conflict Detection — scan files for contradictions against stored spec graph."""

import logging
from typing import Optional
from uuid import UUID
from openai import OpenAI
from src.store import Store
from src.config import llm_model
from src.models import Assertion

log = logging.getLogger(__name__)

def check_ingest_conflicts(
    domain_id: UUID,
    new_entries: list[Assertion],
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

    # 1. Fetch existing approved assertions
    existing_entries = store.get_assertions(domain_id, include_unapproved=False)
    if not existing_entries:
        return []

    # 2. Build mapping of entries
    for new_entry in new_entries:
        for old_entry in existing_entries:
            # Only compare entries of matching section types to avoid noise
            if new_entry.assertion_type != old_entry.assertion_type:
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
