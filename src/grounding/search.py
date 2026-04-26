"""Grounding search — hybrid vector + metadata search with Pinecone reranking."""

import os
from datetime import datetime
from typing import Optional
from uuid import UUID

from openai import OpenAI
from pinecone import Pinecone, PineconeException

from src.models import (
    Channel,
    GroundingChunk,
    GroundingContext,
    GroundingResult,
    GroundingResponse,
    SearchFilters,
    SectionType,
)
from src.store import Store


class GroundingEngine:
    def __init__(
        self,
        store: Store,
        openai_api_key: str | None = None,
        pinecone_api_key: str | None = None,
        index_name: str = "msgstack-chunks",
        namespace: str = "default",
    ):
        self.store = store
        self.openai = OpenAI(api_key=openai_api_key or os.environ.get("OPENAI_API_KEY"))
        self.pc = Pinecone(api_key=pinecone_api_key or os.environ.get("PINECONE_API_KEY"))
        self.index_name = index_name
        self.namespace = namespace

        try:
            self.index = self.pc.Index(index_name)
        except PineconeException:
            self.index = None

    def ensure_index(self) -> None:
        if self.index is not None:
            return
        if "msgstack-chunks" not in [i.name for i in self.pc.list_indexes()]:
            self.pc.create_index(
                name="msgstack-chunks",
                dimension=1536,
                metric="cosine",
                spec={"serverless": {"cloud": "aws", "region": "us-east-1"}},
            )
        self.index = self.pc.Index("msgstack-chunks")

    def _embed(self, text: str) -> list[float]:
        response = self.openai.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding

    def _build_filter(self, filters: SearchFilters) -> dict | None:
        conditions = []
        if filters.section_types:
            conditions.append({"section_type": {"$in": filters.section_types}})
        if filters.personas:
            conditions.append({"persona": {"$in": filters.personas}})
        if filters.channels:
            conditions.append({"channel": {"$in": filters.channels}})
        if filters.message_houses:
            conditions.append({"message_house_id": {"$in": filters.message_houses}})
        if filters.min_priority is not None:
            conditions.append({"priority": {"$lte": filters.min_priority}})
        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def _query_to_filters(self, query: str) -> dict:
        text = query.lower()
        filters: dict = {}
        section_map = {
            "headline": ["headline", "headlines"],
            "subhead": ["subhead", "subheadline", "sub-head"],
            "benefit": ["benefit", "benefits", "value prop", "value proposition", "value pillar", "pillar"],
            "use_case": ["use case", "use cases", "capability", "capabilities", "how it works", "top use"],
            "proof_point": ["proof", "proof point", "social proof", "testimonial", "customer story", "case study", "evidence"],
            "objection": ["objection", "objections", "rebuttal", "concern"],
            "positioning": ["positioning", "position", "frame"],
        }
        for section, keywords in section_map.items():
            if any(kw in text for kw in keywords):
                filters.setdefault("section_types", []).append(section)

        persona_cues = ["smb", "enterprise", "cto", "cmo", "developer", "ops", "finops"]
        for cue in persona_cues:
            if cue in text:
                filters.setdefault("personas", []).append(cue)

        channel_map = {
            "linkedin": ["linkedin"],
            "email": ["email", "subject", "email campaign"],
            "landing": ["landing", "landing page", "web"],
            "twitter": ["twitter", "x.com", "tweet"],
            "paid": ["paid", "ads", "ad copy", "sem"],
        }
        for channel, keywords in channel_map.items():
            if any(kw in text for kw in keywords):
                filters.setdefault("channels", []).append(channel)

        return filters

    def search(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        top_k: int = 8,
        active_house_id: Optional[UUID] = None,
    ) -> GroundingResponse:
        filters = filters or SearchFilters()
        inferred = self._query_to_filters(query)
        for key, val in inferred.items():
            attr = f"{key}_types" if key == "section" else key
            if attr in ["section_types", "personas", "channels"]:
                existing = getattr(filters, attr, None) or []
                merged = list(set(existing + val))
                setattr(filters, attr, merged if merged else None)
            elif attr == "message_houses":
                existing = filters.message_houses or []
                filters.message_houses = list(set(existing + val)) if val else None

        if active_house_id and not filters.message_houses:
            filters.message_houses = [str(active_house_id)]

        pinecone_filter = self._build_filter(filters)
        query_vec = self._embed(query)

        if self.index is None:
            return self._fallback_search(query, filters)

        try:
            results = self.index.query(
                vector=query_vec,
                filter=pinecone_filter,
                top_k=top_k * 2,
                include_metadata=True,
                namespace=self.namespace,
            )
        except PineconeException:
            return self._fallback_search(query, filters)

        matches = results.get("matches", [])
        if len(matches) > top_k:
            matches = self._rerank(query, matches, top_k)

        grounding_results = []
        houses_represented: dict[str, int] = {}
        confidence_scores = []
        coverage: dict[str, str] = {"section_types": "none", "personas": "none", "channels": "none"}

        for match in matches[:top_k]:
            meta = match.get("metadata", {})
            raw_st = meta.get("section_type", "positioning")
            try:
                st = SectionType(raw_st)
            except ValueError:
                st = SectionType.POSITIONING
            chunk = GroundingChunk(
                id=match["id"],
                message_house_id=UUID(meta.get("message_house_id", "00000000-0000-0000-0000-000000000000")),
                key_message_id=UUID(meta.get("key_message_id")) if meta.get("key_message_id") else None,
                content=meta.get("content", ""),
                section_type=st,
                priority=int(meta.get("priority", 3)),
                persona=meta.get("persona"),
                channel=Channel(meta.get("channel", "all")),
                house_name=meta.get("house_name", ""),
                house_summary=meta.get("house_summary", ""),
                last_synced=datetime.fromisoformat(meta["last_synced"]) if meta.get("last_synced") else None,
            )
            house_id_str = str(chunk.message_house_id)
            houses_represented[house_id_str] = houses_represented.get(house_id_str, 0) + 1
            confidence_scores.append(match.get("score", 0))
            grounding_results.append(
                GroundingResult(
                    chunk_id=chunk.id,
                    content=chunk.content,
                    section_type=str(chunk.section_type),
                    priority=chunk.priority,
                    persona=chunk.persona,
                    channel=str(chunk.channel),
                    channel_variants={},
                    source={
                        "house_id": str(chunk.message_house_id),
                        "house_name": chunk.house_name,
                        "last_synced": chunk.last_synced.isoformat() if chunk.last_synced else None,
                    },
                    confidence=match.get("score", 0),
                    rerank_reason=f"score={match.get('score', 0):.3f}",
                )
            )

        if grounding_results:
            top_house_id = max(houses_represented, key=houses_represented.get)
            house = self.store.get_house(UUID(top_house_id))
            house_name = house.name if house else grounding_results[0].source["house_name"]
            house_summary = house.summary if house else ""

            avg_conf = sum(confidence_scores) / len(confidence_scores)
            if avg_conf > 0.8:
                confidence = "high"
            elif avg_conf > 0.5:
                confidence = "medium"
            else:
                confidence = "low"

            section_types = set(r.section_type for r in grounding_results)
            coverage["section_types"] = "full" if len(section_types) > 1 else "partial"
            coverage["personas"] = "full" if grounding_results[0].persona else "none"
            coverage["channels"] = "partial"
        else:
            confidence = "low"
            house_name = ""
            house_summary = ""

        active_personas = list({r.persona for r in grounding_results if r.persona})

        ctx = GroundingContext(
            active_house_id=UUID(top_house_id) if grounding_results else active_house_id,
            house_name=house_name,
            house_summary=house_summary,
            active_personas=active_personas,
            used_chunks=len(grounding_results),
            confidence=confidence,
            coverage=coverage,
            gaps=[],
            warnings=[],
        )

        return GroundingResponse(results=grounding_results, grounding_context=ctx)

    def _rerank(self, query: str, matches: list[dict], top_k: int) -> list[dict]:
        return matches[:top_k]

    def _fallback_search(self, query: str, filters: SearchFilters) -> GroundingResponse:
        all_houses = self.store.list_houses()
        results: list[GroundingResult] = []

        for house in all_houses:
            messages = self.store.get_key_messages(house.id)
            for msg in messages:
                if filters.section_types and str(msg.section_type) not in filters.section_types:
                    continue
                if filters.personas:
                    matched = any(p.lower() in filters.personas for p in msg.personas)
                    if not matched:
                        continue

                query_lower = query.lower()
                score = (
                    0.9
                    if any(kw in msg.content.lower() for kw in query_lower.split()[:3])
                    else 0.5
                )
                results.append(
                    GroundingResult(
                        chunk_id=str(msg.id),
                        content=msg.content,
                        section_type=str(msg.section_type),
                        priority=msg.priority,
                        persona=msg.personas[0] if msg.personas else None,
                        channel="all",
                        channel_variants=msg.variants,
                        source={
                            "house_id": str(house.id),
                            "house_name": house.name,
                            "last_synced": house.last_synced.isoformat() if house.last_synced else None,
                        },
                        confidence=score,
                        rerank_reason="fallback: matched by keyword proximity",
                    )
                )

        results.sort(key=lambda r: (r.confidence, -r.priority), reverse=True)
        return GroundingResponse(
            results=results[:8],
            grounding_context=GroundingContext(
                active_house_id=all_houses[0].id if all_houses else None,
                house_name=all_houses[0].name if all_houses else "",
                house_summary=all_houses[0].summary if all_houses else "",
                confidence="medium" if results else "low",
            ),
        )

    def index_house(self, house_id: UUID) -> int:
        self.ensure_index()
        house = self.store.get_house(house_id)
        if not house:
            raise ValueError(f"House {house_id} not found")

        base_meta = {
            "message_house_id": str(house_id),
            "house_name": house.name,
            "house_summary": house.summary,
            "last_synced": house.last_synced.isoformat() if house.last_synced else None,
        }

        messages = self.store.get_key_messages(house_id)
        vectors = []
        for msg in messages:
            content = msg.content
            vec = self._embed(content)
            vectors.append(
                {
                    "id": f"chunk-{msg.id}",
                    "values": vec,
                    "metadata": {
                        **base_meta,
                        "content": content,
                        "section_type": str(msg.section_type),
                        "priority": msg.priority,
                        "persona": msg.personas[0] if msg.personas else "general",
                        "channel": str(msg.channels[0]) if msg.channels else "all",
                        "key_message_id": str(msg.id),
                    },
                }
            )

        # Index summary, audience, positioning, differentiation as searchable chunks
        for field, st, priority in [
            ("summary", "positioning", 1),
            ("audience", "positioning", 1),
            ("positioning", "positioning", 1),
            ("differentiation", "positioning", 2),
            ("tagline", "headline", 1),
        ]:
            text = getattr(house, field, "") or ""
            if text and text != "[Not found in source]":
                vec = self._embed(text)
                vectors.append({
                    "id": f"field-{house_id}-{field}",
                    "values": vec,
                    "metadata": {
                        **base_meta,
                        "content": text,
                        "section_type": st,
                        "priority": priority,
                        "persona": "general",
                        "channel": "all",
                    },
                })

        # Index know_your_market from saved markdown file
        kym_path = __import__("pathlib").Path("data/frames") / f"{house_id}.md"
        if kym_path.exists():
            md = kym_path.read_text(encoding="utf-8")
            # Extract the Know Your Market block
            if "## Know Your Market" in md:
                kym_start = md.index("## Know Your Market") + len("## Know Your Market")
                next_section = md.find("\n## ", kym_start)
                kym_text = md[kym_start: next_section if next_section != -1 else kym_start + 2000].strip()
                if kym_text:
                    vec = self._embed(kym_text[:1500])
                    vectors.append({
                        "id": f"kym-{house_id}",
                        "values": vec,
                        "metadata": {
                            **base_meta,
                            "content": kym_text[:1500],
                            "section_type": "positioning",
                            "priority": 1,
                            "persona": "general",
                            "channel": "all",
                        },
                    })

        if vectors:
            self.index.upsert(vectors=vectors, namespace=self.namespace)
        return len(vectors)