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
                context.append(f"- {p.name} ({p.role}): {p.pain_points}")
            
        if messages:
            context.append("APPROVED KEY MESSAGES:")
            for m in messages:
                # Assuming the message object has section_type and content
                stype = getattr(m, "section_type", "message")
                context.append(f"- [{stype}] {m.content}")

        system_prompt = (
            "You are an expert Messaging Governance Evaluator. Your job is to analyze the provided CONTENT "
            "against the official MESSAGE HOUSE below.\n\n"
            "MESSAGE HOUSE:\n" + "\n".join(context) + "\n\n"
            "You must score the content on a scale of 0-100 based on how well it aligns with the official messaging. "
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
