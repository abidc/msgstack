import os
import json
from uuid import UUID
from pydantic import BaseModel
from typing import Optional
from openai import OpenAI

from src.store import Store

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
        self.client = OpenAI(api_key=self.api_key)

    def score(self, house_id: UUID, content: str) -> AlignmentReport:
        house = self.store.get_house(house_id)
        if not house:
            raise ValueError("House not found.")

        # We only want to score against Approved messages, as per the v0.9 spec
        all_msgs = self.store.get_key_messages(house_id)
        messages = [m for m in all_msgs if m.status in ("approved", "locked")]
        personas = self.store.get_personas(house_id)

        # Build context
        context = []
        if house.tagline: context.append(f"TAGLINE: {house.tagline}")
        if house.positioning: context.append(f"POSITIONING: {house.positioning}")
        if house.differentiation: context.append(f"DIFFERENTIATION: {house.differentiation}")
        if house.audience: context.append(f"TARGET AUDIENCE: {house.audience}")
        
        if personas:
            context.append("APPROVED PERSONAS:")
            for p in personas:
                context.append(f"- {p.name}: {p.pain_points}")
            
        if messages:
            context.append("APPROVED KEY MESSAGES:")
            for m in messages:
                stype = getattr(m, "section_type", "message")
                context.append(f"- [{stype}] {m.content}")

        # Compute dynamic semantic similarity matches using VectorMetadataModel via GroundingEngine
        from src.grounding.search import GroundingEngine
        from src.models import SearchFilters
        
        sentences = [s.strip() for s in content.replace("\n", ". ").split(".") if len(s.strip()) > 15]
        vector_matches = []
        try:
            engine = GroundingEngine(self.store, openai_api_key=self.api_key)
            for sentence in sentences[:10]:  # Evaluate up to 10 sentences
                search_filters = SearchFilters(message_houses=[str(house_id)], include_drafts=False)
                res = engine.search(query=sentence, filters=search_filters, top_k=1)
                for r in res.results:
                    if r.confidence > 0.4:  # Only report relevant matches
                        vector_matches.append({
                            "sentence": sentence,
                            "matched_content": r.content,
                            "confidence": r.confidence,
                            "section_type": r.section_type
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
                    f"({vm['section_type']}) with semantic confidence {vm['confidence']:.2f}."
                )
            vector_alignment_str = "\n".join(vector_alignment_ctx)

        system_prompt = (
            "You are an expert Messaging Governance Evaluator. Your job is to analyze the provided CONTENT "
            "against the official MESSAGE HOUSE and its semantic vector alignment matches.\n\n"
            "MESSAGE HOUSE:\n" + "\n".join(context) + "\n\n"
            "SEMANTIC VECTOR ALIGNMENT MATCHES (from Vector database):\n" + vector_alignment_str + "\n\n"
            "You must score the content on a scale of 0-100 based on how well it aligns with the official messaging. "
            "Consider both vector match confidences and direct conceptual alignment. "
            "Look for contradictions (where the content says something contrary to the positioning) and omissions "
            "(where key proof points or required messaging are missing).\n\n"
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
            model="gpt-4o",
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
