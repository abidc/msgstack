"""Continuous Alignment Scoring — evaluate external drafts against approved assertions."""

import os
import logging
import json
from typing import Optional
from uuid import UUID
from openai import OpenAI
from pydantic import BaseModel
from src.store import Store
from src.config import llm_model
from src.models import Assertion

log = logging.getLogger(__name__)

# --- Legacy / Backward Compatibility Models ---

class AlignmentSection(BaseModel):
    name: str
    score: int
    feedback: str

class AlignmentReport(BaseModel):
    overall_score: int
    summary: str
    sections: list[AlignmentSection]
    contradictions: list[str]
    missing_key_messages: list[str]

class AlignmentEngine:
    def __init__(self, store: Store, openai_api_key: Optional[str] = None):
        self.store = store
        self.api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for alignment scoring.")
        from src.config import llm_client
        self.client = llm_client(self.api_key)

    def score(self, spec_id: UUID, content: str) -> AlignmentReport:
        spec = self.store.get_spec(spec_id)
        if not spec:
            raise ValueError("Spec not found.")

        # We only want to score against Approved messages, as per the v0.9 spec
        all_msgs = self.store.get_key_messages(spec_id)
        messages = [m for m in all_msgs if m.status in ("approved", "locked")]
        audiences = self.store.get_audiences(spec_id)

        # Build context
        context = []
        if spec.tagline: context.append(f"TAGLINE: {spec.tagline}")
        if spec.positioning: context.append(f"POSITIONING: {spec.positioning}")
        if spec.differentiation: context.append(f"DIFFERENTIATION: {spec.differentiation}")        
        if spec.audience: context.append(f"TARGET AUDIENCE: {spec.audience}")

        if audiences:
            context.append("APPROVED PERSONAS:")
            for p in audiences:
                context.append(f"- {p.name}: {p.qa_pairs}")

        if messages:
            context.append("APPROVED KEY MESSAGES:")
            for m in messages:
                stype = getattr(m, "assertion_type", "message")
                tier = getattr(m, "content_tier", None)
                tier_tag = " | TIER 1 — VERBATIM ONLY" if tier == "tier_1_locked" else ""
                context.append(f"- [{stype}{tier_tag}] {m.content}")

        # Compute dynamic semantic similarity matches using VectorMetadataModel via GroundingEngine  
        from src.grounding.search import GroundingEngine
        from src.models import SearchFilters

        sentences = [s.strip() for s in content.replace("\n", ". ").split(".") if len(s.strip()) > 15]
        vector_matches = []
        try:
            engine = GroundingEngine(self.store, openai_api_key=self.api_key)
            for sentence in sentences[:10]:  # Evaluate up to 10 sentences
                search_filters = SearchFilters(specs=[str(spec_id)], include_drafts=False) 
                res = engine.search(query=sentence, filters=search_filters, top_k=1)
                for r in res.results:
                    if r.confidence > 0.4:  # Only report relevant matches
                        vector_matches.append({
                            "sentence": sentence,
                            "matched_content": r.content,
                            "confidence": r.confidence,
                            "assertion_type": r.assertion_type
                        })
        except Exception as e:
            # Non-blocking: log vector search warning but proceed with direct comparison
            pass

        vector_alignment_str = "No semantic vector matches found."
        if vector_matches:
            vector_alignment_ctx = []
            for vm in vector_matches:
                vector_alignment_ctx.append(
                    f"- Content fragment: '{vm['sentence']}' matches approved message: '{vm['matched_content']}' "
                    f"({vm['assertion_type']}) with semantic confidence {vm['confidence']:.2f}."       
                )
            vector_alignment_str = "\n".join(vector_alignment_ctx)

        system_prompt = (
            "You are an expert Messaging Governance Evaluator. Your job is to analyze the provided CONTENT "
            "against the official MESSAGE SPEC and its semantic vector alignment matches.\n\n"      
            "MESSAGE SPEC:\n" + "\n".join(context) + "\n\n"
            "MESSAGE VECTOR MATCHES (from Vector database):\n" + vector_alignment_str + "\n\n"
            "You must score the content on a scale of 0-100 based on how well it aligns with the official messaging. "
            "Consider both vector match confidences and direct conceptual alignment. "
            "Look for contradictions (where the content says something contrary to the positioning) and omissions "
            "(where key proof points or required messaging are missing). "
            "Messages marked 'TIER 1 — VERBATIM ONLY' are locked: if the content uses one of these claims "
            "in paraphrased or altered form, report it as a contradiction — Tier 1 claims must appear word-for-word.\n\n"
            "Output MUST be strict JSON matching this schema:\n"
            "{\n"
            '  "overall_score": 85,\n'
            '  "summary": "Brief summary of alignment.",\n'
            '  "sections": [\n'
            '    {"name": "Positioning", "score": 90, "feedback": "Aligns well with the core autonomy message."}\n'
            '  ],\n'
            '  "contradictions": ["Lists unsupported feature X."],\n'
            '  "missing_key_messages": ["Did not mention the ROI proof point."]\n'
            "}"
        )

        response = self.client.chat.completions.create(
            model=llm_model("gpt-4o"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"CONTENT TO SCORE:\n\n{content}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )

        raw = response.choices[0].message.content
        data = json.loads(raw)
        return AlignmentReport(**data)


# --- New Phase 4 Continuous Alignment Scoring ---

def score_alignment(
    text: str,
    domain_id: UUID,
    store: Store,
    openai_client: Optional[OpenAI] = None
) -> dict:
    """
    Score a draft document against approved assertions.
    Splits draft text into sections, runs Turbovec lookups, and classifies matches.
    """
    from src.config import llm_client
    client = openai_client or llm_client()
    
    # 1. Fetch approved entries for reference
    assertions = store.get_assertions(domain_id, include_unapproved=False)
    if not assertions:
        return {
            "score": 100,
            "hard_conflicts": [],
            "soft_conflicts": [],
            "aligned_sections": [],
            "explanation": "No approved assertions found to score against."
        }

    # 2. Extract context summary of active domain
    domain = store.get_spec(domain_id)
    domain_positioning = domain.positioning if domain else ""

    # 3. Split the incoming draft text into paragraphs or bullet sections
    draft_paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    
    score = 100
    hard_conflicts = []
    soft_conflicts = []
    aligned_sections = []

    # Build reference context once — tier labels tell the auditor which
    # claims are locked-verbatim (paraphrase of Tier 1 = hard conflict).
    def _entry_line(e) -> str:
        tier = getattr(e, "content_tier", None)
        tier_tag = " | TIER 1 — VERBATIM ONLY" if tier == "tier_1_locked" else ""
        return f"- [{e.assertion_type}{tier_tag}] {e.content}"

    reference_context = "\n".join(_entry_line(e) for e in assertions)

    # 4. Semantic comparison per paragraph
    for i, para in enumerate(draft_paragraphs):
        prompt = (
            f"You are an expert copy auditor. Compare the Draft Paragraph against the Approved Spec Claims.\n\n"
            f"Approved Spec Claims:\n{reference_context}\n"
            f"Core positioning: {domain_positioning}\n\n"
            f"Draft Paragraph to Audit:\n\"{para}\"\n\n"
            f"Identify if this paragraph is Aligned, has Hard Conflicts, or has Soft Conflicts.\n"
            f"Return a JSON object:\n"
            f'{{\n'
            f'  "status": "aligned" / "hard_conflict" / "soft_conflict",\n'
            f'  "matched_spec": "The assertion text it relates to or contradicts (if any)",\n'
            f'  "explanation": "Auditor notes and justification",\n'
            f'  "deduction": 0-20\n'
            f'}}\n'
            f"Rules:\n"
            f"- 'aligned': claim matches or supports the spec. Deduction: 0\n"
            f"- 'hard_conflict': contradicts a factual claim (e.g., pricing, features, metrics). Deduction: 15-20\n"
            f"- 'hard_conflict' ALSO applies when the paragraph uses a claim marked 'TIER 1 — VERBATIM ONLY' "
            f"in paraphrased or altered form — Tier 1 claims must be reproduced word-for-word. Deduction: 15-20\n"
            f"- 'soft_conflict': uses unapproved words, deviates in brand tone, or has minor misalignment. Deduction: 5-10"
        )
        try:
            response = client.chat.completions.create(
                model=llm_model("gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            status = result.get("status", "aligned")
            deduction = int(result.get("deduction", 0))
            explanation = result.get("explanation", "")
            matched = result.get("matched_spec", "")

            audit_item = {
                "paragraph_index": i,
                "paragraph_text": para,
                "matched_spec": matched,
                "explanation": explanation,
                "deduction": deduction
            }

            if status == "hard_conflict":
                hard_conflicts.append(audit_item)
                score -= deduction
            elif status == "soft_conflict":
                soft_conflicts.append(audit_item)
                score -= deduction
            else:
                aligned_sections.append(audit_item)

        except Exception as e:
            log.error(f"Failed to audit paragraph {i}: {e}")

    # Clamp score
    final_score = max(0, min(100, score))

    return {
        "score": final_score,
        "hard_conflicts": hard_conflicts,
        "soft_conflicts": soft_conflicts,
        "aligned_sections": aligned_sections,
        "summary": f"Alignment score is {final_score}%. Found {len(hard_conflicts)} hard conflicts and {len(soft_conflicts)} soft conflicts."
    }


def export_report_to_markdown(report: dict) -> str:
    """Format the alignment report dictionary as a shareable Markdown report."""
    lines = [
        f"# MsgStack Alignment Score Audit Report",
        f"**Overall Score:** {report['score']}%",
        f"**Summary:** {report['summary']}\n",
        "---",
        "\n## 🚨 Hard Conflicts (Factual Contradictions)",
    ]
    if not report["hard_conflicts"]:
        lines.append("No hard conflicts found.")
    for h in report["hard_conflicts"]:
        lines.append(
            f"### Paragraph {h['paragraph_index'] + 1}\n"
            f"- **Draft:** \"{h['paragraph_text']}\"\n"
            f"- **Contradicts:** \"{h['matched_spec']}\"\n"
            f"- **Reason:** {h['explanation']}\n"
            f"- **Score Deduction:** -{h['deduction']}\n"
        )

    lines.append("\n## ⚠️ Soft Conflicts (Voice & Terminology Misalignments)")
    if not report["soft_conflicts"]:
        lines.append("No soft conflicts found.")
    for s in report["soft_conflicts"]:
        lines.append(
            f"### Paragraph {s['paragraph_index'] + 1}\n"
            f"- **Draft:** \"{s['paragraph_text']}\"\n"
            f"- **Matched reference:** \"{s['matched_spec']}\"\n"
            f"- **Reason:** {s['explanation']}\n"
            f"- **Score Deduction:** -{s['deduction']}\n"
        )

    lines.append("\n## ✅ Aligned Sections")
    if not report["aligned_sections"]:
        lines.append("No aligned sections found.")
    for a in report["aligned_sections"]:
        lines.append(f"- \"{a['paragraph_text']}\" (Grounded in: *\"{a['matched_spec']}\"*)\n")

    return "\n".join(lines)
