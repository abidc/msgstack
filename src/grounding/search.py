"""Grounding search — local quantized vector search with Turbovec and SQLite pre-filtering."""

import hashlib
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

import numpy as np
from openai import OpenAI
from turbovec import IdMapIndex

log = logging.getLogger(__name__)

from src.models import (
    Channel,
    GroundingChunk,
    GroundingContext,
    GroundingResult,
    GroundingResponse,
    SearchFilters,
    SectionType,
)
from src.store import Store, VectorMetadataModel


def string_to_uint64(s: str) -> int:
    """Deterministically map any string identifier to a uint64 value."""
    sha = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return int(sha[:16], 16)


class GroundingEngine:
    def __init__(
        self,
        store: Store,
        openai_api_key: str | None = None,
        turbovec_index_path: str | None = None,
        namespace: str = "default",  # Kept for backward compatibility
        **kwargs,
    ):
        self.store = store
        self.openai = OpenAI(api_key=openai_api_key or os.environ.get("OPENAI_API_KEY"))
        from src.config import settings
        self.index_path = Path(turbovec_index_path or settings.turbovec_index_path)
        self.namespace = namespace
        self.index = None
        self._lock = threading.Lock()
        self._load_or_create_index()

    def _load_or_create_index(self) -> None:
        """Load the Turbovec IdMapIndex from disk or initialize a new one."""
        with self._lock:
            if self.index_path.exists():
                try:
                    self.index = IdMapIndex.load(str(self.index_path))
                    log.info("Loaded Turbovec index from %s", self.index_path)
                    return
                except Exception as e:
                    log.error("Failed to load Turbovec index: %s. Recreating...", e)
            
            # Create a brand new index
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            self.index = IdMapIndex(dim=1536, bit_width=4)
            self.index.write(str(self.index_path))
            log.info("Initialized new Turbovec index at %s", self.index_path)

    def save_index(self) -> None:
        """Save the current index state to disk."""
        if self.index is not None:
            self.index.write(str(self.index_path))

    def ensure_index(self) -> None:
        """No-op kept for backward compatibility with caller APIs."""
        pass

    def _embed(self, text: str) -> list[float]:
        response = self.openai.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding

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
            "know_your_market": ["know your market", "know your customer", "kym", "kyc", "market research", "market context", "competitive context"],
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
        retrieval_mode: str = "hybrid",
    ) -> GroundingResponse:
        filters = filters or SearchFilters()

        if retrieval_mode == "graph" and active_house_id:
            return self._graph_search(active_house_id, filters)
        if retrieval_mode == "keyword":
            return self._fallback_search(query, filters)

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

        # SQLite pre-filtering
        matching_records = self.store.list_vector_metadata_matching_filters(
            message_houses=filters.message_houses,
            section_types=filters.section_types,
            personas=filters.personas,
            channels=filters.channels,
            min_priority=filters.min_priority,
        )

        if not matching_records:
            return GroundingResponse(
                results=[],
                grounding_context=GroundingContext(
                    active_house_id=active_house_id,
                    house_name="",
                    house_summary="",
                    confidence="low",
                )
            )

        # Map candidate UUIDs/string IDs deterministically to uint64 allowlist
        id_map = {string_to_uint64(r.id): r for r in matching_records}
        allowlist = np.array(list(id_map.keys()), dtype=np.uint64)

        query_vec = self._embed(query)

        if self.index is None:
            return self._fallback_search(query, filters)

        try:
            query_arr = np.array([query_vec], dtype=np.float32)
            scores_2d, ids_2d = self.index.search(query_arr, k=top_k * 2, allowlist=allowlist)
            scores = scores_2d[0]
            ids = ids_2d[0]
        except Exception as e:
            log.error("Turbovec local search failed: %s", e)
            return self._fallback_search(query, filters)

        matches = []
        for score, uint_id in zip(scores, ids):
            record = id_map.get(uint_id)
            if record:
                matches.append({
                    "id": record.id,
                    "score": float(score),
                    "metadata": {
                        "message_house_id": record.message_house_id,
                        "house_name": record.house_name,
                        "house_summary": record.house_summary,
                        "content": record.content,
                        "section_type": record.section_type,
                        "priority": record.priority,
                        "persona": record.persona,
                        "channel": record.channel,
                        "key_message_id": record.key_message_id,
                        "last_synced": record.last_synced.isoformat() if record.last_synced else None,
                    }
                })

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
            top_house_id = str(active_house_id) if active_house_id else None

        active_personas = list({r.persona for r in grounding_results if r.persona})

        warnings: list[str] = []
        if filters.min_confidence is not None and grounding_results:
            avg_conf = sum(r.confidence for r in grounding_results) / len(grounding_results)
            if avg_conf < filters.min_confidence:
                warnings.append(
                    f"Average result confidence ({avg_conf:.2f}) is below requested threshold ({filters.min_confidence:.2f}). "
                    "Results may not be strongly relevant — consider rephrasing the query."
                )

        ctx = GroundingContext(
            active_house_id=UUID(top_house_id) if top_house_id else active_house_id,
            house_name=house_name,
            house_summary=house_summary,
            active_personas=active_personas,
            used_chunks=len(grounding_results),
            confidence=confidence,
            coverage=coverage,
            gaps=[],
            warnings=warnings,
        )

        return GroundingResponse(results=grounding_results, grounding_context=ctx)

    def _rerank(self, query: str, matches: list[dict], top_k: int) -> list[dict]:
        """Rerank by blending vector score with keyword-overlap score and boost factors."""
        _STOPWORDS = {"a", "an", "the", "and", "or", "in", "of", "to", "for", "is", "are",
                      "be", "with", "that", "this", "on", "at", "by", "from", "as", "it"}
        query_tokens = {w for w in query.lower().split() if len(w) > 2 and w not in _STOPWORDS}

        boost_map = self._get_boost_factors()

        def _score(match: dict) -> float:
            vec_score = match.get("score", 0.0)
            if not query_tokens:
                return vec_score
            content = (match.get("metadata", {}).get("content", "")).lower()
            content_tokens = set(content.split())
            overlap = len(query_tokens & content_tokens) / len(query_tokens)
            base_score = 0.7 * vec_score + 0.3 * overlap

            chunk_id = match.get("id", "")
            boost = boost_map.get(chunk_id, 1.0)
            return base_score * boost

        return sorted(matches, key=_score, reverse=True)[:top_k]

    def _get_boost_factors(self) -> dict[str, float]:
        """Fetch chunk_id -> boost_factor map from DB via store."""
        try:
            with self.store.session() as s:
                from src.store import ChunkUsageStatModel
                rows = s.query(ChunkUsageStatModel).all()
                return {r.chunk_id: r.boost_factor for r in rows}
        except Exception:
            return {}

    def _graph_search(self, house_id: UUID, filters: SearchFilters) -> GroundingResponse:
        """Deterministic graph retrieval — bypasses vector approximation."""
        from src.grounding.graph import get_graph_engine
        engine = get_graph_engine()
        persona = (filters.personas or [None])[0] if filters.personas else None
        channel = (filters.channels or [None])[0] if filters.channels else None
        chunks = engine.get_connections(str(house_id), persona=persona, channel=channel)

        results = []
        for chunk in chunks:
            if filters.section_types and chunk.get("section_type") not in filters.section_types:
                continue
            results.append(GroundingResult(
                chunk_id=chunk.get("id", ""),
                content=chunk.get("content", ""),
                section_type=chunk.get("section_type", "positioning"),
                priority=chunk.get("priority", 3),
                persona=persona,
                channel=channel or "all",
                channel_variants={},
                source={"house_id": str(house_id), "house_name": ""},
                confidence=1.0,
                rerank_reason="graph:deterministic",
            ))

        house = self.store.get_house(house_id)
        return GroundingResponse(
            results=results[:8],
            grounding_context=GroundingContext(
                active_house_id=house_id,
                house_name=house.name if house else "",
                house_summary=house.summary if house else "",
                confidence="high" if results else "low",
            ),
        )

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
        house = self.store.get_house(house_id)
        if not house:
            raise ValueError(f"House {house_id} not found")

        # Clear existing vectors to prevent duplicates
        self.delete_house_vectors(house_id)

        messages = self.store.get_key_messages(house_id)
        vectors_to_add = []
        ids_to_add = []

        with self._lock:
            # 1. Embed and index key messages
            for msg in messages:
                content = msg.content
                vec = self._embed(content)
                str_id = f"chunk-{msg.id}"
                uint_id = string_to_uint64(str_id)

                vectors_to_add.append(vec)
                ids_to_add.append(uint_id)

                self.store.upsert_vector_metadata(
                    id=str_id,
                    message_house_id=house_id,
                    house_name=house.name,
                    house_summary=house.summary or "",
                    content=content,
                    section_type=str(msg.section_type),
                    priority=msg.priority,
                    persona=msg.personas[0] if msg.personas else "general",
                    channel=str(msg.channels[0]) if msg.channels else "all",
                    key_message_id=msg.id,
                    last_synced=house.last_synced,
                )

            # 2. Embed and index message house positioning fields
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
                    str_id = f"field-{house_id}-{field}"
                    uint_id = string_to_uint64(str_id)

                    vectors_to_add.append(vec)
                    ids_to_add.append(uint_id)

                    self.store.upsert_vector_metadata(
                        id=str_id,
                        message_house_id=house_id,
                        house_name=house.name,
                        house_summary=house.summary or "",
                        content=text,
                        section_type=st,
                        priority=priority,
                        persona="general",
                        channel="all",
                        last_synced=house.last_synced,
                    )

            # 3. Embed and index Know Your Market frame section
            kym_path = Path("data/frames") / f"{house_id}.md"
            if kym_path.exists():
                md = kym_path.read_text(encoding="utf-8")
                if "## Know Your Market" in md:
                    kym_start = md.index("## Know Your Market") + len("## Know Your Market")
                    next_section = md.find("\n## ", kym_start)
                    kym_text = md[kym_start: next_section if next_section != -1 else kym_start + 2000].strip()
                    if kym_text:
                        content_slice = kym_text[:1500]
                        vec = self._embed(content_slice)
                        str_id = f"kym-{house_id}"
                        uint_id = string_to_uint64(str_id)

                        vectors_to_add.append(vec)
                        ids_to_add.append(uint_id)

                        self.store.upsert_vector_metadata(
                            id=str_id,
                            message_house_id=house_id,
                            house_name=house.name,
                            house_summary=house.summary or "",
                            content=content_slice,
                            section_type="know_your_market",
                            priority=1,
                            persona="general",
                            channel="all",
                            last_synced=house.last_synced,
                        )

            # 4. Upsert to Turbovec IdMapIndex
            if vectors_to_add:
                vec_arr = np.array(vectors_to_add, dtype=np.float32)
                ids_arr = np.array(ids_to_add, dtype=np.uint64)
                
                # Check for and remove existing keys before adding to avoid duplicated keys in IdMapIndex
                for uid in ids_to_add:
                    try:
                        self.index.remove(uid)
                    except Exception:
                        pass
                
                self.index.add_with_ids(vec_arr, ids_arr)
                self.save_index()

        return len(vectors_to_add)

    def delete_house_vectors(self, house_id: UUID) -> int:
        """Delete all vectors and metadata for a house by ID."""
        with self._lock:
            with self.store.session() as s:
                records = s.query(VectorMetadataModel).filter(
                    VectorMetadataModel.message_house_id == str(house_id)
                ).all()
                str_ids = [r.id for r in records]

            if not str_ids:
                return 0

            deleted = 0
            for sid in str_ids:
                uint_id = string_to_uint64(sid)
                try:
                    self.index.remove(uint_id)
                    deleted += 1
                except Exception as e:
                    log.debug("Vector %s not present or failed to remove: %s", sid, e)

            # Delete metadata from DB
            self.store.delete_vector_metadata_for_house(house_id)

            if deleted > 0:
                self.save_index()

            return deleted