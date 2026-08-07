"""Multi-Agent Layer — specialized functional agents and the Spec Navigator."""

import json
import logging
from typing import Optional, Generator
from uuid import UUID
from openai import OpenAI
from src.store import Store
from src.grounding.graph import get_graph_engine

log = logging.getLogger(__name__)

class BaseAgent:
    def __init__(self, client: OpenAI, store: Store):
        self.client = client
        self.store = store


class GovernanceAgent(BaseAgent):
    """Specialized agent for enforcing approvals, review logs, and conflict checks."""

    def analyze_change(self, entry_id: str, new_content: str) -> dict:
        entry = self.store.get_assertion(UUID(entry_id))
        if not entry:
            return {"status": "error", "error": "Entry not found"}

        prompt = (
            f"Compare this proposed change to the current entry:\n"
            f"Current Content: {entry.content}\n"
            f"Proposed Content: {new_content}\n\n"
            f"Review the change for logical impact. Return JSON:\n"
            f'{{"impact": "high" / "medium" / "low", '
            f'"notes": "Brief impact description", '
            f'"requires_escalation": true/false}}'
        )
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {"status": "error", "error": str(e)}


class VoiceAgent(BaseAgent):
    """Specialized agent for analyzing brand register parameters (tonal slider fits) and vocabulary."""

    def analyze_tone(self, text: str, domain_id: UUID) -> dict:
        domain = self.store.get_spec(domain_id)
        personality = domain.brand_personality if domain else "General"

        prompt = (
            f"Evaluate the text against the brand personality: '{personality}'\n\n"
            f"Text: \"{text}\"\n\n"
            f"Assess the tone fit. Return JSON:\n"
            f'{{"tone_score": 0-100, "alignment_gaps": ["list of tone gaps", "..."], '
            f'"suggestions": "How to adjust wording to match personality"}}'
        )
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {"status": "error", "error": str(e)}


class StructureAgent(BaseAgent):
    """Specialized agent for validating spec completeness specs."""

    def analyze_domain(self, domain_id: UUID) -> dict:
        report = self.store.check_spec_completeness(domain_id)
        score = report.get("score", 0)
        missing = report.get("missing_sections", [])

        prompt = (
            f"A messaging spec has a completeness score of {score}%.\n"
            f"It is missing these sections: {missing}\n\n"
            f"Suggest specific actions to improve the framework score. Return JSON:\n"
            f'{{"improvement_plan": "Brief text instructions", '
            f'"recommended_next_ingest": "What documentation is needed next"}}'
        )
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            res = json.loads(response.choices[0].message.content)
            res.update({"score": score, "missing": missing})
            return res
        except Exception as e:
            return {"status": "error", "error": str(e)}


class SpecNavigator(BaseAgent):
    """Orchestrator super-agent. Natural language interface for users to query spec graph state."""

    def __init__(self, client: OpenAI, store: Store):
        super().__init__(client, store)
        self.governance = GovernanceAgent(client, store)
        self.voice = VoiceAgent(client, store)
        self.structure = StructureAgent(client, store)

    def chat_stream(self, query: str, workspace_id: str = "default") -> Generator[str, None, None]:
        """
        Chat loop returning streamed narrative answers, tracing graph connections,
        and analyzing updates.
        """
        graph = get_graph_engine()
        stats = graph.get_stats()

        prompt = (
            f"You are the Spec Navigator — the conversational assistant for the MsgStack Spec Grounding Layer.\n"
            f"Current Workspace: {workspace_id}\n"
            f"Graph stats: {stats.get('nodes', 0)} nodes, {stats.get('edges', 0)} edges.\n\n"
            f"Ground your answers in the approved spec. If users ask about drift, edits, "
            f"or the status of specific messaging specs, use your training. Do not invent details.\n\n"
            f"User Query: {query}"
        )

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are the friendly, professional Spec Navigator super-agent. Stream your answer in Markdown format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                stream=True
            )
            for chunk in response:
                delta = chunk.choices[0].delta.content if chunk.choices and chunk.choices[0].delta else ""
                if delta:
                    yield delta
        except Exception as e:
            yield f"Error: Chat connection failed: {e}"
