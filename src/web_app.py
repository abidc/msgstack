"""FastAPI web app — admin UX for MsgStack MCP management."""

import logging
import os
import time
import uuid as _uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

load_dotenv()

from src.config import settings, estimate_cost_usd
from src.logging_config import configure_logging
configure_logging()

log = logging.getLogger(__name__)

from src.auth import get_auth_context, require_read, require_write, generate_api_key, AuthContext
from src.models import Channel, HouseStatus, KeyMessage, MessageHouse, Persona, SectionType
from src.store import init_store
from src.pipeline.extract import ExtractionError, extract_text, chunk_text, save_upload
from src.pipeline.structure import HouseStructurer, StructuredHouse
from src.pipeline.skills import SkillManager
from src.rate_limit import extract_limiter, generate_limiter

app = FastAPI(title="MsgStack Admin", version="0.5.0", redirect_slashes=False)
templates = Jinja2Templates(directory="src/web")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

store = init_store()

skills = SkillManager(skills_dir=str(DATA_DIR / "skills"))
structurer = HouseStructurer()

import openai as _oai_mod
_oai_client = _oai_mod.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


@app.on_event("startup")
async def startup_event():
    """Ensure Pinecone index exists on startup, seed if no houses."""
    from src.grounding.search import GroundingEngine
    try:
        engine = GroundingEngine(
            store=store,
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            pinecone_api_key=os.environ.get("PINECONE_API_KEY"),
            index_name=os.environ.get("PINECONE_INDEX", "msgstack-chunks"),
            namespace="default",
        )
        engine.ensure_index()
        log.info("Pinecone index ensured on startup")
    except Exception as e:
        log.warning("Pinecone index creation skipped: %s", e)

    # Auto-seed if no houses exist
    if not store.list_houses():
        log.info("No houses found, running seed...")
        from seed_data.seed import seed as run_seed
        try:
            run_seed()
            log.info("Auto-seed complete")
        except Exception as e:
            log.warning("Auto-seed skipped: %s", e)

def _check_token_budget(workspace_id: str) -> None:
    """Raise HTTP 402 if workspace token budget is exhausted."""
    ws = store.get_workspace(workspace_id)
    if not ws or ws.get("max_token_budget", 0) == 0:
        return
    usage = store.get_token_usage_summary(workspace_id=workspace_id)
    used = usage.get("total_input_tokens", 0) + usage.get("total_output_tokens", 0)
    if used >= ws["max_token_budget"]:
        raise HTTPException(
            status_code=402,
            detail=f"Token budget exhausted ({used:,} / {ws['max_token_budget']:,} tokens used). "
                   "Increase max_token_budget via PATCH /api/workspaces/{id}.",
        )


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

# In-memory cache for preview-structure → confirm-structure flow (token → (structured, name, path, ts))
_preview_cache: dict[str, tuple] = {}
_PREVIEW_TTL = 3600  # 1 hour

def _evict_preview_cache() -> None:
    cutoff = time.time() - _PREVIEW_TTL
    stale = [k for k, v in _preview_cache.items() if len(v) > 3 and v[3] < cutoff]
    for k in stale:
        del _preview_cache[k]

# In-memory metrics accumulator
_metrics: dict = defaultdict(lambda: {"requests": 0, "errors": 0, "total_ms": 0.0})
_start_time = time.time()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    path = request.url.path
    try:
        log.info(
            "%s %s -> %d  (%.1fms)",
            request.method, path, response.status_code, elapsed_ms,
            extra={"endpoint": path, "latency_ms": round(elapsed_ms, 1), "status": response.status_code},
        )
    except Exception:
        pass  # Avoid logging failures
    # Accumulate metrics
    key = f"{request.method} {path}"
    _metrics[key]["requests"] += 1
    _metrics[key]["total_ms"] += elapsed_ms
    if response.status_code >= 400:
        _metrics[key]["errors"] += 1
    return response


# --- Helpers ---

def _house_response(house: MessageHouse) -> dict:
    messages = store.get_key_messages(house.id)
    personas = store.get_personas(house.id)
    return {
        "id": str(house.id),
        "name": house.name,
        "source": house.source,
        "source_id": house.source_id,
        "status": house.status,
        "summary": house.summary,
        "audience": house.audience,
        "brand_personality": house.brand_personality,
        "positioning": house.positioning,
        "tagline": house.tagline,
        "differentiation": house.differentiation,
        "last_synced": house.last_synced.isoformat() if house.last_synced else None,
        "key_messages": [
            {
                "id": str(m.id),
                "section_type": m.section_type.value if hasattr(m.section_type, "value") else m.section_type,
                "priority": m.priority,
                "content": m.content,
                "variants": m.variants,
                "personas": m.personas,
                "channels": [c.value if hasattr(c, "value") else c for c in m.channels],
            }
            for m in messages
        ],
        "personas": [
            {
                "id": str(p.id),
                "name": p.name,
                "description": p.description,
                "pain_points": p.pain_points,
                "buying_triggers": p.buying_triggers,
                "objections": p.objections,
            }
            for p in personas
        ],
    }


# --- Houses ---

@app.get("/api/houses")
def list_houses(query: Optional[str] = None, auth: AuthContext = Depends(get_auth_context)):
    workspace_filter = auth.workspace_id if settings.auth_enabled else None
    rows = store.list_houses_with_counts(workspace_id=workspace_filter)
    result = []
    for row in rows:
        h = row["house"]
        summary = h.summary or ""
        if query and query.lower() not in h.name.lower() and query.lower() not in summary.lower():
            continue
        mc, pc = row["message_count"], row["persona_count"]
        completeness = _completeness_score_fast(h, mc, pc)
        result.append({
            "id": str(h.id),
            "name": h.name,
            "source": h.source,
            "status": h.status,
            "summary": summary[:150] + ("..." if len(summary) > 150 else ""),
            "persona_count": pc,
            "message_count": mc,
            "last_synced": h.last_synced.isoformat() if h.last_synced else None,
            "completeness_score": completeness,
        })
    return result


def _completeness_score_fast(house, message_count, persona_count) -> int:
    score = 0
    if house.name: score += 10
    if house.summary: score += 10
    if house.audience: score += 10
    if house.brand_personality: score += 10
    if house.positioning: score += 15
    if house.tagline: score += 10
    if house.differentiation: score += 10
    if message_count >= 3: score += 10
    if message_count >= 6: score += 10
    if persona_count >= 1: score += 5
    return min(score, 100)


@app.get("/api/houses/{house_id}")
def get_house(house_id: str):
    try:
        house = store.get_house(UUID(house_id))
    except Exception:
        raise HTTPException(404, "Invalid house ID")
    if not house:
        raise HTTPException(404, "House not found")
    return _house_response(house)


class HouseCreate(BaseModel):
    name: str
    summary: str = ""
    audience: str = ""
    brand_personality: str = ""
    positioning: str = ""
    tagline: str = ""
    differentiation: str = ""
    source: str = "manual"
    status: str = "active"


@app.post("/api/houses")
def create_house(data: HouseCreate):
    house = MessageHouse(
        name=data.name,
        source=data.source,
        summary=data.summary,
        audience=data.audience,
        brand_personality=data.brand_personality,
        positioning=data.positioning,
        tagline=data.tagline,
        differentiation=data.differentiation,
        status=HouseStatus(data.status),
        last_synced=_now(),
    )
    store.upsert_house(house)
    return {"id": str(house.id), "name": house.name}


class HouseUpdate(BaseModel):
    name: Optional[str] = None
    summary: Optional[str] = None
    audience: Optional[str] = None
    brand_personality: Optional[str] = None
    positioning: Optional[str] = None
    tagline: Optional[str] = None
    differentiation: Optional[str] = None
    status: Optional[str] = None


@app.patch("/api/houses/{house_id}")
def update_house(house_id: str, data: HouseUpdate):
    house = store.get_house(UUID(house_id))
    if not house:
        raise HTTPException(404, "House not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(house, k, v)
    store.upsert_house(house)
    return {"ok": True, "updated_id": house_id}


@app.delete("/api/houses/{house_id}")
def delete_house(house_id: str):
    if not store.delete_house(UUID(house_id)):
        raise HTTPException(404, "House not found")
    return {"ok": True, "deleted_id": house_id}


# --- Key Messages ---

class MessageCreate(BaseModel):
    message_house_id: str
    section_type: str
    priority: int = 3
    content: str
    variants: dict = {}
    personas: list = []
    channels: list = ["all"]


@app.post("/api/messages")
def create_message(data: MessageCreate):
    try:
        msg = KeyMessage(
            message_house_id=UUID(data.message_house_id),
            section_type=SectionType(data.section_type),
            priority=data.priority,
            content=data.content,
            variants=data.variants,
            personas=data.personas,
            channels=[Channel(c) for c in data.channels],
        )
        store.upsert_key_message(msg)
        return {"id": str(msg.id)}
    except Exception as e:
        raise HTTPException(400, str(e))


class MessageUpdate(BaseModel):
    section_type: Optional[str] = None
    priority: Optional[int] = None
    content: Optional[str] = None
    variants: Optional[dict] = None
    personas: Optional[list] = None
    channels: Optional[list] = None


@app.patch("/api/messages/{msg_id}")
def update_message(msg_id: str, data: MessageUpdate):
    msg = _find_message(msg_id)
    if not msg:
        raise HTTPException(404, "Message not found")
    for k, v in data.model_dump(exclude_none=True).items():
        if k == "section_type":
            msg.section_type = SectionType(v)
        elif k == "channels":
            msg.channels = [Channel(c) for c in v]
        else:
            setattr(msg, k, v)
    store.upsert_key_message(msg)
    return {"ok": True, "updated_id": msg_id}


@app.delete("/api/messages/{msg_id}")
def delete_message(msg_id: str):
    if not store.delete_key_message(UUID(msg_id)):
        raise HTTPException(404, "Message not found")
    return {"ok": True, "deleted_id": msg_id}


class MessageReorder(BaseModel):
    ordered_ids: list[str]


@app.patch("/api/houses/{house_id}/messages/reorder")
def reorder_messages(house_id: str, data: MessageReorder):
    """Update priority values so messages appear in the given order."""
    count = 0
    for priority, msg_id in enumerate(data.ordered_ids, start=1):
        msg = _find_message(msg_id)
        if msg and str(msg.message_house_id) == house_id:
            msg.priority = priority
            store.upsert_key_message(msg)
            count += 1
    return {"ok": True, "reordered_count": count}


class BulkMessageImport(BaseModel):
    rows: list[dict]


@app.post("/api/houses/{house_id}/messages/bulk-import")
def bulk_import_messages(house_id: str, data: BulkMessageImport):
    """Import multiple key messages at once."""
    try:
        house_uuid = UUID(house_id)
    except Exception:
        raise HTTPException(400, "Invalid house ID")
    if not store.get_house(house_uuid):
        raise HTTPException(404, "House not found")

    if not data.rows:
        raise HTTPException(400, "No rows provided")

    created = []
    errors = []
    existing = store.get_key_messages(house_uuid)
    next_priority = (max((m.priority for m in existing), default=0) + 1)

    for i, row in enumerate(data.rows):
        try:
            content = row.get("content")
            if not content:
                errors.append({"row": i, "error": "Missing required field: content"})
                continue
            if not isinstance(content, str) or not content.strip():
                errors.append({"row": i, "error": "Invalid content: must be non-empty string"})
                continue

            section_type = row.get("section_type", "headline")
            try:
                st = SectionType(section_type)
            except ValueError:
                st = SectionType.HEADLINE

            msg = KeyMessage(
                message_house_id=house_uuid,
                section_type=st,
                priority=row.get("priority", next_priority + i),
                content=content.strip(),
            )
            store.upsert_key_message(msg)
            created.append(str(msg.id))
        except Exception as e:
            errors.append({"row": i, "error": str(e)})

    return {"created": len(created), "errors": errors, "ids": created}


# --- Personas ---

class PersonaCreate(BaseModel):
    message_house_id: str
    name: str
    description: str = ""
    pain_points: list = []
    buying_triggers: list = []
    objections: list = []


@app.post("/api/personas")
def create_persona(data: PersonaCreate):
    persona = Persona(
        message_house_id=UUID(data.message_house_id),
        name=data.name,
        description=data.description,
        pain_points=data.pain_points,
        buying_triggers=data.buying_triggers,
        objections=data.objections,
    )
    store.upsert_persona(persona)
    return {"id": str(persona.id)}


class PersonaUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    pain_points: Optional[list] = None
    buying_triggers: Optional[list] = None
    objections: Optional[list] = None


@app.patch("/api/personas/{persona_id}")
def update_persona(persona_id: str, data: PersonaUpdate):
    persona = _find_persona(persona_id)
    if not persona:
        raise HTTPException(404, "Persona not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(persona, k, v)
    store.upsert_persona(persona)
    return {"ok": True, "updated_id": persona_id}


@app.delete("/api/personas/{persona_id}")
def delete_persona(persona_id: str):
    if not store.delete_persona(UUID(persona_id)):
        raise HTTPException(404, "Persona not found")
    return {"ok": True, "deleted_id": persona_id}


# --- Source Upload & Processing ---

@app.post("/api/upload")
async def upload_source(file: UploadFile = File(...)):
    """Upload a source file (PDF, DOCX, TXT) and extract its text."""
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    file_path = UPLOAD_DIR / file.filename
    save_upload(file.file, file_path)

    try:
        text = extract_text(file_path)
        chunks = chunk_text(text)
    except ExtractionError as e:
        raise HTTPException(400, str(e))

    return {
        "filename": file.filename,
        "char_count": len(text),
        "word_count": len(text.split()),
        "chunk_count": len(chunks),
        "preview": text[:500],
        "extracted_text": text,
    }


@app.post("/api/extract")
async def extract_upload(
    file: UploadFile = File(...),
    source_name: str = Form(""),
    _rl: None = Depends(extract_limiter),
    auth: AuthContext = Depends(require_write),
):
    """Upload a file, extract text, structure it, and save as a MessageHouse.

    Returns structured error JSON on failure with which stage failed.
    """
    _check_token_budget(auth.workspace_id if settings.auth_enabled else "default")

    file_path = UPLOAD_DIR / file.filename
    save_upload(file.file, file_path)

    try:
        text = extract_text(file_path)
    except ExtractionError as e:
        return JSONResponse(status_code=400, content={
            "status": "failed",
            "error": {"stage": "text_extraction", "message": str(e), "detail": str(e)},
        })

    if not source_name:
        source_name = Path(file.filename).stem

    try:
        structured, llm_usage = structurer.structure(text, source_name=source_name)
    except Exception as e:
        log.error("LLM structuring failed for %s: %s", file.filename, e)
        return JSONResponse(status_code=500, content={
            "status": "failed",
            "error": {"stage": "llm_structuring", "message": "LLM structuring failed", "detail": str(e)},
        })

    try:
        store.record_token_usage(
            workspace_id=auth.workspace_id if settings.auth_enabled else "default",
            endpoint="extract",
            model="gpt-4o-mini",
            input_tokens=llm_usage["input_tokens"],
            output_tokens=llm_usage["output_tokens"],
            cost_usd=estimate_cost_usd("gpt-4o-mini", llm_usage["input_tokens"], llm_usage["output_tokens"]),
        )
    except Exception:
        pass

    try:
        house, indexed, markdown = _commit_structured_house(structured, file.filename)
    except Exception as e:
        log.error("DB commit failed for %s: %s", file.filename, e)
        return JSONResponse(status_code=500, content={
            "status": "failed",
            "error": {"stage": "database_save", "message": "Failed to save to database", "detail": str(e)},
        })

    return {
        "id": str(house.id),
        "name": house.name,
        "status": "created",
        "message_count": len(structured.key_messages),
        "persona_count": len(structured.personas),
        "indexed": indexed,
        "markdown": markdown,
        "know_your_market": structured.know_your_market,
        "missing_sections": structured.missing_sections,
        "completeness_score": max(0, 100 - len(structured.missing_sections) * 10),
    }


@app.post("/api/preview-structure")
async def preview_structure(
    file: UploadFile = File(...),
    source_name: str = Form(""),
    _rl: None = Depends(extract_limiter),
    auth: AuthContext = Depends(require_write),
):
    """Extract and structure a file but do NOT save to DB.

    Returns the structured sections for user review. Call /api/confirm-structure
    with the returned preview_token to persist.
    """
    file_path = UPLOAD_DIR / file.filename
    save_upload(file.file, file_path)

    try:
        text = extract_text(file_path)
    except ExtractionError as e:
        return JSONResponse(status_code=400, content={
            "status": "failed",
            "error": {"stage": "text_extraction", "message": str(e), "detail": str(e)},
        })

    if not source_name:
        source_name = Path(file.filename).stem

    try:
        structured, llm_usage = structurer.structure(text, source_name=source_name)
    except Exception as e:
        log.error("LLM structuring failed for %s: %s", file.filename, e)
        return JSONResponse(status_code=500, content={
            "status": "failed",
            "error": {"stage": "llm_structuring", "message": "LLM structuring failed", "detail": str(e)},
        })

    try:
        store.record_token_usage(
            workspace_id=auth.workspace_id if settings.auth_enabled else "default",
            endpoint="preview-structure",
            model="gpt-4o-mini",
            input_tokens=llm_usage["input_tokens"],
            output_tokens=llm_usage["output_tokens"],
            cost_usd=estimate_cost_usd("gpt-4o-mini", llm_usage["input_tokens"], llm_usage["output_tokens"]),
        )
    except Exception:
        pass

    _evict_preview_cache()
    token = str(_uuid.uuid4())
    _preview_cache[token] = (structured, source_name, str(file_path), time.time())

    return {
        "status": "preview",
        "preview_token": token,
        "name": structured.name,
        "char_count": len(text),
        "word_count": len(text.split()),
        "summary": structured.summary,
        "audience": structured.audience,
        "brand_personality": structured.brand_personality,
        "positioning": structured.positioning,
        "tagline": structured.tagline,
        "differentiation": structured.differentiation,
        "know_your_market": structured.know_your_market,
        "key_messages": structured.key_messages,
        "personas": structured.personas,
        "missing_sections": structured.missing_sections,
        "completeness_score": max(0, 100 - len(structured.missing_sections) * 10),
    }


@app.post("/api/confirm-structure")
async def confirm_structure(data: dict):
    """Persist a previewed structure to DB and index to Pinecone.

    Body: {"preview_token": "...", "edits": {optional field overrides}}
    """
    token = data.get("preview_token")
    if not token or token not in _preview_cache:
        raise HTTPException(400, "Invalid or expired preview_token")

    structured, source_name, file_path_str, *_ = _preview_cache.pop(token)

    # Apply any user edits to top-level fields
    edits = data.get("edits", {})
    for field in ("name", "summary", "audience", "brand_personality", "positioning", "tagline", "differentiation"):
        if field in edits and edits[field]:
            setattr(structured, field, edits[field])

    try:
        filename = Path(file_path_str).name
        house, indexed, markdown = _commit_structured_house(structured, filename)
    except Exception as e:
        log.error("DB commit failed during confirm-structure: %s", e)
        return JSONResponse(status_code=500, content={
            "status": "failed",
            "error": {"stage": "database_save", "message": "Failed to save to database", "detail": str(e)},
        })

    return {
        "id": str(house.id),
        "name": house.name,
        "status": "created",
        "message_count": len(structured.key_messages),
        "persona_count": len(structured.personas),
        "indexed": indexed,
        "markdown": markdown,
        "know_your_market": structured.know_your_market,
        "missing_sections": structured.missing_sections,
        "completeness_score": max(0, 100 - len(structured.missing_sections) * 10),
    }


def _commit_structured_house(structured: StructuredHouse, filename: str) -> tuple:
    """Save a StructuredHouse to DB, write markdown, and index to Pinecone.

    Returns (house, indexed_bool, markdown_str).
    """
    house = MessageHouse(
        name=structured.name,
        source="upload",
        source_id=filename,
        summary=structured.summary,
        audience=structured.audience,
        brand_personality=structured.brand_personality,
        positioning=structured.positioning,
        tagline=structured.tagline,
        differentiation=structured.differentiation,
        status=HouseStatus.ACTIVE,
        last_synced=_now(),
    )
    store.upsert_house(house)

    for km in structured.key_messages:
        try:
            section_type = SectionType(km["section_type"])
        except ValueError:
            section_type = SectionType.POSITIONING
        msg = KeyMessage(
            message_house_id=house.id,
            section_type=section_type,
            priority=km.get("priority", 3),
            content=km["content"],
            variants=km.get("variants", {}),
            personas=km.get("personas", []),
            channels=[Channel(c) for c in km.get("channels", ["all"])],
        )
        store.upsert_key_message(msg)

    for p in structured.personas:
        persona = Persona(
            message_house_id=house.id,
            name=p["name"],
            description=p.get("description", ""),
            pain_points=p.get("pain_points", []),
            buying_triggers=p.get("buying_triggers", []),
            objections=p.get("objections", []),
        )
        store.upsert_persona(persona)

    markdown = structurer.to_markdown(structured)
    save_path = DATA_DIR / "frames" / f"{house.id}.md"
    save_path.parent.mkdir(exist_ok=True)
    save_path.write_text(markdown, encoding="utf-8")

    from src.grounding.search import GroundingEngine
    house_row_ws = store.get_house_workspace_id(house.id)
    engine = GroundingEngine(
        store=store,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        pinecone_api_key=os.environ.get("PINECONE_API_KEY"),
        index_name=os.environ.get("PINECONE_INDEX", "msgstack-chunks"),
        namespace=house_row_ws or "default",
    )
    try:
        engine.index_house(house.id)
        indexed = True
    except Exception as exc:
        log.warning("Pinecone indexing skipped for %s: %s", house.id, exc)
        indexed = False

    return house, indexed, markdown


@app.get("/api/frames/{house_id}/markdown")
def get_frame_markdown(house_id: str):
    """Get the saved markdown file for a framework."""
    path = DATA_DIR / "frames" / f"{house_id}.md"
    if not path.exists():
        raise HTTPException(404, "Markdown file not found")
    return {"markdown": path.read_text()}


# --- Skill Files ---

@app.get("/api/skills")
def list_skills():
    return skills.list_skills()


@app.get("/api/skills/{skill_id}")
def get_skill(skill_id: str):
    skill = skills.get_skill(skill_id)
    if not skill:
        raise HTTPException(404, f"Skill {skill_id} not found")
    return skill


@app.put("/api/skills/{skill_id}")
def update_skill(skill_id: str, data: dict):
    return skills.update_skill(skill_id, data)


@app.post("/api/skills")
def create_skill(data: dict):
    if not data.get("id"):
        raise HTTPException(400, "id is required")
    return skills.update_skill(data["id"], data)


@app.delete("/api/skills/{skill_id}")
def delete_skill(skill_id: str):
    if not skills.delete_skill(skill_id):
        raise HTTPException(404, f"Skill {skill_id} not found")
    return {"ok": True}


# --- Stats ---

@app.get("/api/stats")
def get_stats():
    houses = store.list_houses()
    total_messages = sum(len(store.get_key_messages(h.id)) for h in houses)
    total_personas = sum(len(store.get_personas(h.id)) for h in houses)
    total_artifacts = sum(len(store.list_artifacts(h.id)) for h in houses)
    usage = store.get_token_usage_summary()

    return {
        "house_count": len(houses),
        "message_count": total_messages,
        "persona_count": total_personas,
        "artifact_count": total_artifacts,
        "token_count": usage.get("total_input_tokens", 0) + usage.get("total_output_tokens", 0),
        "skill_count": len(skills.list_skills()),
    }


# --- Seed & Index ---

@app.post("/api/seed")
def run_seed():
    """Run the seed script and index all houses to Pinecone."""
    from seed_data.seed import seed as run_seed_script
    from src.grounding.search import GroundingEngine

    run_seed_script()

    houses = store.list_houses()
    total_messages = sum(len(store.get_key_messages(h.id)) for h in houses)
    total_personas = sum(len(store.get_personas(h.id)) for h in houses)

    indexed_count = 0
    for house in houses:
        ws_id = store.get_house_workspace_id(house.id) or "default"
        engine = GroundingEngine(
            store=store,
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            pinecone_api_key=os.environ.get("PINECONE_API_KEY"),
            index_name=os.environ.get("PINECONE_INDEX", "msgstack-chunks"),
            namespace=ws_id,
        )
        try:
            engine.index_house(house.id)
            indexed_count += 1
        except Exception:
            pass

    return {
        "seeded": len(houses),
        "indexed": indexed_count,
        "total_messages": total_messages,
        "total_personas": total_personas,
    }


@app.post("/api/houses/{house_id}/index")
def index_house(house_id: str):
    """Index a single house to Pinecone."""
    from src.grounding.search import GroundingEngine

    try:
        house_uuid = UUID(house_id)
    except Exception:
        raise HTTPException(400, "Invalid house ID")

    house = store.get_house(house_uuid)
    if not house:
        raise HTTPException(404, "House not found")

    ws_id = store.get_house_workspace_id(house_uuid) or "default"
    engine = GroundingEngine(
        store=store,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        pinecone_api_key=os.environ.get("PINECONE_API_KEY"),
        index_name=os.environ.get("PINECONE_INDEX", "msgstack-chunks"),
        namespace=ws_id,
    )

    vectors_indexed = engine.index_house(house_uuid)

    return {
        "house_id": str(house.id),
        "house_name": house.name,
        "vectors_indexed": vectors_indexed,
    }


@app.post("/api/index-all")
def index_all_houses():
    """Index all houses to Pinecone."""
    from src.grounding.search import GroundingEngine

    houses = store.list_houses()

    total_vectors = 0
    for house in houses:
        ws_id = store.get_house_workspace_id(house.id) or "default"
        engine = GroundingEngine(
            store=store,
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            pinecone_api_key=os.environ.get("PINECONE_API_KEY"),
            index_name=os.environ.get("PINECONE_INDEX", "msgstack-chunks"),
            namespace=ws_id,
        )
        try:
            vectors = engine.index_house(house.id)
            total_vectors += vectors
        except Exception as exc:
            log.warning("Pinecone index failed for %s: %s", house.id, exc)

    return {
        "indexed_houses": len(houses),
        "total_vectors": total_vectors,
    }


@app.get("/api/houses/{house_id}/index-status")
def get_house_index_status(house_id: str):
    """Check Pinecone index status for a house: indexed / not_indexed / stale."""
    from src.grounding.search import GroundingEngine
    from pinecone import PineconeException

    try:
        house_uuid = UUID(house_id)
    except Exception:
        raise HTTPException(400, "Invalid house ID")

    house = store.get_house(house_uuid)
    if not house:
        raise HTTPException(404, "House not found")

    ws_id = store.get_house_workspace_id(house_uuid) or "default"
    engine = GroundingEngine(
        store=store,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        pinecone_api_key=os.environ.get("PINECONE_API_KEY"),
        index_name=os.environ.get("PINECONE_INDEX", "msgstack-chunks"),
        namespace=ws_id,
    )

    if engine.index is None:
        return {"status": "unavailable", "message": "Pinecone index not reachable"}

    try:
        # Query with a zero vector + house filter to check if any vectors exist
        dummy = [0.0] * 1536
        results = engine.index.query(
            vector=dummy,
            filter={"message_house_id": {"$eq": str(house_uuid)}},
            top_k=1,
            include_metadata=True,
            namespace=engine.namespace,
        )
        matches = results.get("matches", [])
        if not matches:
            return {"status": "not_indexed", "house_id": house_id}

        # Check staleness: compare last_synced in vector metadata vs house.last_synced
        meta_synced_str = matches[0].get("metadata", {}).get("last_synced")
        if meta_synced_str and house.last_synced:
            meta_dt = datetime.fromisoformat(meta_synced_str)
            house_dt = house.last_synced
            # Make both offset-naive for comparison
            if meta_dt.tzinfo is not None:
                meta_dt = meta_dt.replace(tzinfo=None)
            stale = meta_dt < house_dt
            return {
                "status": "stale" if stale else "indexed",
                "house_id": house_id,
                "indexed_at": meta_synced_str,
                "house_synced": house.last_synced.isoformat(),
            }

        return {"status": "indexed", "house_id": house_id}

    except PineconeException as e:
        log.error("Pinecone index-status query failed for %s: %s", house_id, e)
        return {"status": "error", "message": str(e)}


# --- Internal helpers ---

def _find_message(msg_id: str) -> Optional[KeyMessage]:
    try:
        return store.get_key_message(UUID(msg_id))
    except (ValueError, Exception):
        return None


def _find_persona(persona_id: str) -> Optional[Persona]:
    try:
        return store.get_persona(UUID(persona_id))
    except (ValueError, Exception):
        return None


# --- Artifact Generation & Preview ---

@app.post("/api/generate")
def generate_artifact(
    skill_id: str = Form(...),
    house_id: str = Form(...),
    custom_context: Optional[dict] = Form(None),
    _rl: None = Depends(generate_limiter),
    auth: AuthContext = Depends(require_read),
):
    """Generate an artifact using a skill and return content for preview."""
    from src.pipeline.generator import ArtifactGenerator

    generator = ArtifactGenerator(store, skills)

    try:
        artifact = generator.generate(skill_id, house_id, custom_context or {})
        visual_types = {"one_pager", "social_posts", "email_template", "battlecard", "email_sequence"}
        artifact_type = skill_id if skill_id in visual_types else None
        visual_url = f"{settings.base_url}/artifact/{artifact_type}/{house_id}" if artifact_type else None

        # Record token usage
        if artifact.input_tokens or artifact.output_tokens:
            try:
                store.record_token_usage(
                    workspace_id=auth.workspace_id if settings.auth_enabled else "default",
                    endpoint="generate",
                    model="gpt-4o-mini",
                    input_tokens=artifact.input_tokens,
                    output_tokens=artifact.output_tokens,
                    cost_usd=estimate_cost_usd("gpt-4o-mini", artifact.input_tokens, artifact.output_tokens),
                )
            except Exception:
                pass

        # Auto-save to artifact history
        try:
            saved = store.save_artifact(
                house_id=UUID(house_id),
                skill_id=skill_id,
                house_name=artifact.house_name,
                sections=artifact.sections,
                raw_content=artifact.raw_content,
            )
            artifact_history_id = saved["id"]
        except Exception:
            artifact_history_id = None

        return {
            "skill_id": skill_id,
            "house_name": artifact.house_name,
            "house_id": house_id,
            "sections": artifact.sections,
            "raw_content": artifact.raw_content,
            "visual_url": visual_url,
            "artifact_id": artifact_history_id,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


_SECTION_PROMPTS = {
    "summary": "Write a 2-3 sentence product summary for {name}. Positioning: {positioning}",
    "audience": "Describe the target audience for {name} in one focused paragraph. Use: {positioning}",
    "brand_personality": "Define the brand personality/voice for {name} in 2-3 sentences. Positioning: {positioning}",
    "tagline": "Write a punchy tagline (7 words or fewer) for {name}. Positioning: {positioning}",
    "differentiation": "List 2-3 key differentiators for {name} vs competitors. Positioning: {positioning}",
    "messages:headline": "Write 3 compelling benefit-led headlines for {name}. Positioning: {positioning}. Return as a bulleted list.",
    "messages:benefit": "Write 3 outcome-focused benefit statements for {name}. Positioning: {positioning}. Return as a bulleted list.",
    "messages:proof_point": "Write 3 credible proof points / stats for {name}. If no real stats exist in context, create plausible placeholders clearly marked [PLACEHOLDER]. Positioning: {positioning}. Return as a bulleted list.",
    "messages:objection": "Write 3 common objection handlers for {name}. Positioning: {positioning}. Return as a bulleted list.",
    "personas": "Define 2 key buyer personas for {name}. For each include: name, role/description, 3 pain points, 2 buying triggers, 2 objections. Positioning: {positioning}",
}


@app.post("/api/generate-section")
def generate_section(house_id: str = Form(...), section: str = Form(...)):
    """Generate content for a specific missing section using the LLM."""
    try:
        h = store.get_house(UUID(house_id))
    except Exception:
        raise HTTPException(400, "Invalid house_id")
    if not h:
        raise HTTPException(404, "House not found")

    template = _SECTION_PROMPTS.get(section)
    if not template:
        raise HTTPException(400, f"Unknown section: {section}")

    prompt = template.format(
        name=h.name,
        positioning=h.positioning or h.summary or "",
    )

    client = _oai_client
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a B2B messaging strategist. Be specific, benefit-led, and concise."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
        max_tokens=600,
    )
    store.record_token_usage(
        workspace_id="default",
        endpoint="generate-section",
        model="gpt-4o-mini",
        input_tokens=resp.usage.prompt_tokens,
        output_tokens=resp.usage.completion_tokens,
        cost_usd=estimate_cost_usd("gpt-4o-mini", resp.usage.prompt_tokens, resp.usage.completion_tokens),
    )
    return {"section": section, "content": resp.choices[0].message.content.strip()}


_SECTION_REGEN_PROMPTS = {
    "summary": "Rewrite the summary for {name}. Positioning: {positioning}. Keep it 2-3 sentences, compelling and specific.",
    "audience": "Rewrite the target audience description for {name}. Positioning: {positioning}. Be specific about role, company size, industry.",
    "tagline": "Create a new tagline for {name}. Positioning: {positioning}. Must be 7 words or fewer, memorable and ownable.",
    "differentiation": "Rewrite the differentiation for {name}. Positioning: {positioning}. List 2-3 specific ways this is better than alternatives.",
    "headline": "Write 3 new compelling headlines for {name}. Positioning: {positioning}. Benefit-led, specific, punchy. Return as bulleted list.",
    "subhead": "Write 3 new subheadlines for {name}. Positioning: {positioning}. Expand on headlines. Return as bulleted list.",
    "benefit": "Write 3 new benefit statements for {name}. Positioning: {positioning}. Outcome-focused with evidence. Return as bulleted list.",
    "proof_point": "Write 3 new proof points for {name}. Positioning: {positioning}. Quantified stats or customer evidence. Return as bulleted list.",
    "objection": "Write 3 new objection handlers for {name}. Positioning: {positioning}. Concise rebuttals. Return as bulleted list.",
    "social_proof": "Write 3 new social proof items for {name}. Positioning: {positioning}. Customer quotes, awards, G2 recognition. Return as bulleted list.",
}


@app.post("/api/generate-section-single")
def generate_section_single(house_id: str = Query(...), section: str = Query(...)):
    """Regenerate a single section of an artifact using LLM."""
    try:
        h = store.get_house(UUID(house_id))
    except Exception:
        raise HTTPException(400, "Invalid house_id")
    if not h:
        raise HTTPException(404, "House not found")

    messages = store.get_key_messages(h.id)
    messages_by_section = {}
    for m in messages:
        st = str(m.section_type)
        messages_by_section.setdefault(st, []).append(m.content)
    existing_msgs = "\n".join(f"- {st}: {msg}" for st, msgs in messages_by_section.items() for msg in msgs[:2])

    template = _SECTION_REGEN_PROMPTS.get(section.lower())
    if not template:
        template = _SECTION_PROMPTS.get(section, "Generate content for {name}. Positioning: {positioning}")

    prompt = template.format(
        name=h.name,
        positioning=h.positioning or h.summary or "",
    ) + f"\n\nExisting key messages:\n{existing_msgs}"

    client = _oai_client
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a B2B messaging strategist. Be specific, benefit-led, and concise."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.6,
        max_tokens=600,
    )
    store.record_token_usage(
        workspace_id="default",
        endpoint="generate-section-single",
        model="gpt-4o-mini",
        input_tokens=resp.usage.prompt_tokens,
        output_tokens=resp.usage.completion_tokens,
        cost_usd=estimate_cost_usd("gpt-4o-mini", resp.usage.prompt_tokens, resp.usage.completion_tokens),
    )
    return {"section": section, "content": resp.choices[0].message.content.strip()}


# --- Message Improve / Variant Generation ---

@app.post("/api/messages/{msg_id}/improve")
def improve_message(msg_id: str):
    """Suggest a stronger version of a key message via LLM."""
    msg = _find_message(msg_id)
    if not msg:
        raise HTTPException(404, "Message not found")
    house = store.get_house(msg.message_house_id)
    positioning = house.positioning if house else ""

    client = _oai_client
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a B2B messaging expert. Rewrite the message to be more specific, benefit-led, and compelling. Return only the improved message text — no preamble."},
            {"role": "user", "content": f"Section type: {msg.section_type}\nPositioning context: {positioning}\n\nOriginal message:\n{msg.content}\n\nImproved version:"},
        ],
        temperature=0.6,
        max_tokens=300,
    )
    store.record_token_usage(
        workspace_id="default",
        endpoint="improve-message",
        model="gpt-4o-mini",
        input_tokens=resp.usage.prompt_tokens,
        output_tokens=resp.usage.completion_tokens,
        cost_usd=estimate_cost_usd("gpt-4o-mini", resp.usage.prompt_tokens, resp.usage.completion_tokens),
    )
    return {"original": msg.content, "improved": resp.choices[0].message.content.strip()}


@app.post("/api/messages/{msg_id}/generate-variant")
def generate_variant(msg_id: str, channel: str = Form(...)):
    """Generate a channel-specific variant of a message."""
    msg = _find_message(msg_id)
    if not msg:
        raise HTTPException(404, "Message not found")

    channel_guidance = {
        "linkedin": "LinkedIn post hook (under 150 chars, stops the scroll)",
        "email": "email subject line + opening hook (subject max 60 chars)",
        "twitter": "Twitter/X post (under 280 chars, punchy)",
        "paid": "paid ad headline + description (headline max 30 chars, description max 90 chars)",
        "landing": "landing page headline (benefit-led, max 10 words)",
        "blog": "blog post title and meta description",
    }
    guidance = channel_guidance.get(channel, f"{channel} version")

    client = _oai_client
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"You are a B2B copywriter. Adapt the message for {channel}: {guidance}. Return only the adapted text."},
            {"role": "user", "content": f"Original message:\n{msg.content}"},
        ],
        temperature=0.6,
        max_tokens=200,
    )
    variant_text = resp.choices[0].message.content.strip()
    store.record_token_usage(
        workspace_id="default",
        endpoint="generate-variant",
        model="gpt-4o-mini",
        input_tokens=resp.usage.prompt_tokens,
        output_tokens=resp.usage.completion_tokens,
        cost_usd=estimate_cost_usd("gpt-4o-mini", resp.usage.prompt_tokens, resp.usage.completion_tokens),
    )

    # Save the variant back to the message
    variants = dict(msg.variants or {})
    variants[channel] = variant_text
    msg.variants = variants
    store.upsert_key_message(msg)

    return {"channel": channel, "variant": variant_text, "msg_id": msg_id}


# --- Persona Generation ---

class GeneratePersonaRequest(BaseModel):
    house_id: str
    job_title: str


@app.post("/api/generate-persona")
def generate_persona(data: GeneratePersonaRequest):
    """Generate a full persona from a job title using LLM."""
    house = store.get_house(UUID(data.house_id))
    if not house:
        raise HTTPException(404, "House not found")

    client = _oai_client
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a B2B buyer persona expert. Return JSON only."},
            {"role": "user", "content": f"""Generate a buyer persona for a '{data.job_title}' who might buy {house.name}.

Context: {house.positioning or house.summary or 'B2B SaaS product'}

Return JSON:
{{
  "name": "<descriptive persona name like 'SMB CTO'>",
  "description": "<1-2 sentence role description>",
  "pain_points": ["<pain 1>", "<pain 2>", "<pain 3>"],
  "buying_triggers": ["<trigger 1>", "<trigger 2>"],
  "objections": ["<objection 1>", "<objection 2>"]
}}"""},
        ],
        response_format={"type": "json_object"},
        temperature=0.5,
        max_tokens=400,
    )
    store.record_token_usage(
        workspace_id="default",
        endpoint="generate-persona",
        model="gpt-4o-mini",
        input_tokens=resp.usage.prompt_tokens,
        output_tokens=resp.usage.completion_tokens,
        cost_usd=estimate_cost_usd("gpt-4o-mini", resp.usage.prompt_tokens, resp.usage.completion_tokens),
    )
    try:
        import json as _json
        persona_data = _json.loads(resp.choices[0].message.content)
    except Exception:
        raise HTTPException(500, "Failed to parse LLM persona response")

    persona = Persona(
        message_house_id=house.id,
        name=persona_data.get("name", data.job_title),
        description=persona_data.get("description", ""),
        pain_points=persona_data.get("pain_points", []),
        buying_triggers=persona_data.get("buying_triggers", []),
        objections=persona_data.get("objections", []),
    )
    store.upsert_persona(persona)
    return {
        "id": str(persona.id),
        "name": persona.name,
        "description": persona.description,
        "pain_points": persona.pain_points,
        "buying_triggers": persona.buying_triggers,
        "objections": persona.objections,
    }


# --- Tone Check ---

@app.post("/api/houses/{house_id}/check-tone")
def check_tone(house_id: str):
    """Analyze key messages against brand_personality and flag mismatches."""
    house = store.get_house(UUID(house_id))
    if not house:
        raise HTTPException(404, "House not found")
    messages = store.get_key_messages(UUID(house_id))
    if not messages:
        return {"warnings": [], "score": 100, "summary": "No messages to check"}
    if not house.brand_personality:
        return {"warnings": [], "score": 100, "summary": "No brand personality defined — add one in Overview to enable tone checking"}

    samples = [m.content for m in messages[:12]]

    import json as _json
    client = _oai_client
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a brand voice analyst. Return JSON only."},
            {"role": "user", "content": f"""Brand personality: {house.brand_personality}

Key messages:
{chr(10).join(f'- {m}' for m in samples)}

Identify which messages (if any) are inconsistent with the brand personality. Return JSON:
{{
  "score": <0-100 tone alignment score>,
  "summary": "<1 sentence overall assessment>",
  "warnings": [
    {{"message": "<message text>", "issue": "<what's inconsistent>", "suggestion": "<how to fix>"}}
  ]
}}"""},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=600,
    )
    store.record_token_usage(
        workspace_id="default",
        endpoint="check-tone",
        model="gpt-4o-mini",
        input_tokens=resp.usage.prompt_tokens,
        output_tokens=resp.usage.completion_tokens,
        cost_usd=estimate_cost_usd("gpt-4o-mini", resp.usage.prompt_tokens, resp.usage.completion_tokens),
    )
    try:
        result = _json.loads(resp.choices[0].message.content)
    except Exception:
        raise HTTPException(500, "Failed to parse tone check response")
    return result


# --- Snapshots ---

@app.post("/api/houses/{house_id}/snapshots")
def create_snapshot(house_id: str, data: dict = {}):
    """Save a snapshot of the current framework state."""
    label = (data or {}).get("label", "")
    try:
        snap = store.create_snapshot(UUID(house_id), label)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return snap


@app.get("/api/houses/{house_id}/snapshots")
def list_snapshots(house_id: str):
    return store.list_snapshots(UUID(house_id))


@app.get("/api/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: str):
    snap = store.get_snapshot(UUID(snapshot_id))
    if not snap:
        raise HTTPException(404, "Snapshot not found")
    return snap


@app.get("/api/snapshots/{snapshot_id}/diff")
def get_snapshot_diff(snapshot_id: str):
    """Return a diff between a snapshot and the current framework state."""
    try:
        result = store.diff_snapshot(UUID(snapshot_id))
    except ValueError as e:
        raise HTTPException(404, str(e))
    return result


@app.delete("/api/snapshots/{snapshot_id}")
def delete_snapshot(snapshot_id: str):
    if not store.delete_snapshot(UUID(snapshot_id)):
        raise HTTPException(404, "Snapshot not found")
    return {"ok": True}


@app.post("/api/snapshots/{snapshot_id}/restore")
def restore_snapshot(snapshot_id: str):
    """Restore a framework to a snapshot state (replaces messages and personas)."""
    snap = store.get_snapshot(UUID(snapshot_id))
    if not snap:
        raise HTTPException(404, "Snapshot not found")

    data = snap["snapshot_json"]
    house_data = data.get("house", {})
    house_id = UUID(house_data["id"])

    house = store.get_house(house_id)
    if not house:
        raise HTTPException(404, "Framework no longer exists")

    # Restore house fields
    for field in ("name", "summary", "audience", "brand_personality", "positioning", "tagline", "differentiation"):
        if field in house_data:
            setattr(house, field, house_data[field])
    store.upsert_house(house)

    # Replace messages
    for m in store.get_key_messages(house_id):
        store.delete_key_message(m.id)
    for md in data.get("messages", []):
        try:
            msg = KeyMessage(
                message_house_id=house_id,
                section_type=SectionType(md["section_type"].split(".")[-1] if "." in md["section_type"] else md["section_type"]),
                priority=md.get("priority", 3),
                content=md["content"],
                variants=md.get("variants", {}),
                personas=md.get("personas", []),
                channels=[Channel(c.split(".")[-1] if "." in c else c) for c in md.get("channels", ["all"])],
            )
            store.upsert_key_message(msg)
        except Exception:
            pass

    # Replace personas
    for p in store.get_personas(house_id):
        store.delete_persona(p.id)
    for pd in data.get("personas", []):
        persona = Persona(
            message_house_id=house_id,
            name=pd["name"],
            description=pd.get("description", ""),
            pain_points=pd.get("pain_points", []),
            buying_triggers=pd.get("buying_triggers", []),
            objections=pd.get("objections", []),
        )
        store.upsert_persona(persona)

    return {"ok": True, "house_id": str(house_id), "restored_from": snapshot_id}


# --- Artifact History ---

@app.post("/api/artifacts/save")
def save_artifact(data: dict):
    """Save a generated artifact to history."""
    try:
        house_id = UUID(data["house_id"])
    except Exception:
        raise HTTPException(400, "Invalid house_id")
    record = store.save_artifact(
        house_id=house_id,
        skill_id=data.get("skill_id", ""),
        house_name=data.get("house_name", ""),
        sections=data.get("sections", {}),
        raw_content=data.get("raw_content", ""),
    )
    return record


@app.get("/api/houses/{house_id}/artifacts")
def list_house_artifacts(house_id: str):
    return store.list_artifacts(UUID(house_id))


@app.get("/api/artifacts/{artifact_id}")
def get_artifact(artifact_id: str):
    record = store.get_artifact(UUID(artifact_id))
    if not record:
        raise HTTPException(404, "Artifact not found")
    return record


@app.patch("/api/artifacts/{artifact_id}")
def update_artifact(artifact_id: str, data: dict):
    """Update sections or raw_content of an existing artifact."""
    record = store.get_artifact(UUID(artifact_id))
    if not record:
        raise HTTPException(404, "Artifact not found")

    sections = record.get("sections", {})
    if "sections" in data and isinstance(data["sections"], dict):
        sections.update(data["sections"])

    from src.store import ArtifactHistoryModel
    from uuid import UUID as UUID_
    with store.session() as s:
        row = s.get(ArtifactHistoryModel, artifact_id)
        if row:
            row.sections_json = sections
            if "raw_content" in data:
                row.raw_content = data["raw_content"]
            s.commit()

    return {"ok": True, "updated_id": artifact_id}


# --- DOCX Download ---

@app.get("/api/artifacts/{artifact_id}/docx")
def download_artifact_docx(artifact_id: str):
    """Download a saved artifact as a DOCX file."""
    record = store.get_artifact(UUID(artifact_id))
    if not record:
        raise HTTPException(404, "Artifact not found")

    try:
        from docx import Document as DocxDocument
        from docx.shared import Pt, RGBColor
        from io import BytesIO
        from fastapi.responses import StreamingResponse
    except ImportError:
        raise HTTPException(500, "python-docx not installed")

    doc = DocxDocument()
    doc.add_heading(f"{record['house_name']} — {record['skill_id'].replace('_', ' ').title()}", 0)

    for section_key, section_value in record["sections"].items():
        doc.add_heading(section_key.replace("_", " ").title(), 2)
        doc.add_paragraph(str(section_value))

    if record.get("raw_content"):
        doc.add_heading("Full Content", 2)
        doc.add_paragraph(record["raw_content"])

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)

    filename = f"{record['house_name'].replace(' ', '_')}_{record['skill_id']}.docx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/artifacts/{artifact_id}/pdf", response_class=HTMLResponse)
def download_artifact_pdf(artifact_id: str):
    """Return a print-ready HTML page that auto-triggers browser print dialog."""
    record = store.get_artifact(UUID(artifact_id))
    if not record:
        raise HTTPException(404, "Artifact not found")

    sections_html = ""
    for key, value in record["sections"].items():
        sections_html += f"""
        <div class="section">
            <h2>{key.replace('_', ' ').title()}</h2>
            <div class="section-body">{str(value).replace(chr(10), '<br>')}</div>
        </div>"""

    if record.get("raw_content"):
        sections_html += f"""
        <div class="section">
            <h2>Full Content</h2>
            <div class="section-body">{record['raw_content'].replace(chr(10), '<br>')}</div>
        </div>"""

    html = f"""<!doctype html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{record['house_name']} — {record['skill_id'].replace('_', ' ').title()}</title>
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Inter', sans-serif; color: #0f172a; padding: 40px; max-width: 800px; margin: 0 auto; }}
        h1 {{ font-size: 28px; font-weight: 700; margin-bottom: 4px; }}
        .subtitle {{ color: #64748b; font-size: 14px; margin-bottom: 32px; padding-bottom: 16px; border-bottom: 2px solid #e2e8f0; }}
        .section {{ margin-bottom: 28px; page-break-inside: avoid; }}
        h2 {{ font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #6366f1; margin-bottom: 10px; }}
        .section-body {{ font-size: 15px; line-height: 1.7; color: #334155; }}
        @media print {{ body {{ padding: 0; }} }}
        </style>
    </head>
    <body>
        <h1>{record['house_name']}</h1>
        <div class="subtitle">{record['skill_id'].replace('_', ' ').title()} · Generated {record['created_at'][:10]}</div>
        {sections_html}
        <script>window.onload = () => window.print();</script>
    </body>
    </html>"""
    return HTMLResponse(content=html)


# --- Completeness in houses list ---

def _completeness_score(house: MessageHouse) -> int:
    """Return 0-100 completeness score for a house."""
    messages = store.get_key_messages(house.id)
    personas = store.get_personas(house.id)
    score = 0
    if house.name: score += 10
    if house.summary: score += 10
    if house.audience: score += 10
    if house.brand_personality: score += 10
    if house.positioning: score += 15
    if house.tagline: score += 10
    if house.differentiation: score += 10
    headlines = [m for m in messages if str(m.section_type).endswith("headline")]
    if headlines: score += 10
    benefits = [m for m in messages if str(m.section_type).endswith("benefit")]
    if benefits: score += 10
    if personas: score += 5
    return min(score, 100)


# --- Health + Metrics ---

@app.get("/health")
def health():
    """Production health check — returns 200 when the DB is reachable."""
    try:
        store.list_workspaces()
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "error",
        "uptime_seconds": round(time.time() - _start_time),
        "version": "0.5.0",
        "auth_enabled": settings.auth_enabled,
    }


@app.get("/api/metrics")
def get_metrics(auth: AuthContext = Depends(require_read)):
    """Request metrics + token usage summary."""
    top = sorted(_metrics.items(), key=lambda x: x[1]["requests"], reverse=True)[:20]
    return {
        "uptime_seconds": round(time.time() - _start_time),
        "endpoints": [
            {
                "path": k,
                "requests": v["requests"],
                "errors": v["errors"],
                "avg_latency_ms": round(v["total_ms"] / max(v["requests"], 1), 1),
            }
            for k, v in top
        ],
        "token_usage": store.get_token_usage_summary(
            workspace_id=auth.workspace_id if settings.auth_enabled else None
        ),
    }


# --- Workspaces ---

class WorkspaceCreate(BaseModel):
    slug: str
    name: str
    max_token_budget: int = 0


@app.get("/api/workspaces")
def list_workspaces(auth: AuthContext = Depends(require_read)):
    workspaces = store.list_workspaces()
    for ws in workspaces:
        ws["token_usage"] = store.get_token_usage_summary(workspace_id=ws["id"])
        houses = store.list_houses(workspace_id=ws["id"])
        ws["house_count"] = len(houses)
    return workspaces


@app.post("/api/workspaces")
def create_workspace(data: WorkspaceCreate, auth: AuthContext = Depends(require_write)):
    if not data.slug.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(400, "Slug must be alphanumeric with hyphens/underscores only")
    existing = store.get_workspace(data.slug)
    if existing:
        raise HTTPException(409, f"Workspace slug '{data.slug}' already exists")
    return store.create_workspace(data.slug, data.name, data.max_token_budget)


@app.get("/api/workspaces/{workspace_id}")
def get_workspace(workspace_id: str, auth: AuthContext = Depends(require_read)):
    ws = store.get_workspace(workspace_id)
    if not ws:
        raise HTTPException(404, "Workspace not found")
    ws["token_usage"] = store.get_token_usage_summary(workspace_id=ws["id"])
    ws["house_count"] = len(store.list_houses(workspace_id=ws["id"]))
    return ws


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    max_token_budget: Optional[int] = None


@app.patch("/api/workspaces/{workspace_id}")
def update_workspace(workspace_id: str, data: WorkspaceUpdate, auth: AuthContext = Depends(require_write)):
    updates = data.model_dump(exclude_none=True)
    result = store.update_workspace(workspace_id, **updates)
    if not result:
        raise HTTPException(404, "Workspace not found")
    return result


# --- API Key Management ---

class ApiKeyCreate(BaseModel):
    name: str
    workspace_id: str = "default"
    scopes: list[str] = ["read", "write"]


@app.post("/api/api-keys")
def create_api_key(data: ApiKeyCreate, auth: AuthContext = Depends(require_write)):
    valid_scopes = {"read", "write", "admin"}
    bad = set(data.scopes) - valid_scopes
    if bad:
        raise HTTPException(400, f"Invalid scopes: {bad}. Use: {valid_scopes}")
    plaintext, key_hash = generate_api_key()
    record = store.create_api_key(
        key_hash=key_hash,
        name=data.name,
        workspace_id=data.workspace_id,
        scopes=data.scopes,
    )
    # Return plaintext key ONCE — it won't be shown again
    record["key"] = plaintext
    record["warning"] = "Save this key now — it will not be shown again."
    return record


@app.get("/api/api-keys")
def list_api_keys(workspace_id: Optional[str] = None, auth: AuthContext = Depends(require_read)):
    wid = workspace_id or (auth.workspace_id if settings.auth_enabled else None)
    return store.list_api_keys(workspace_id=wid)


@app.delete("/api/api-keys/{key_id}")
def revoke_api_key(key_id: str, auth: AuthContext = Depends(require_write)):
    if not store.revoke_api_key(key_id):
        raise HTTPException(404, "API key not found")
    return {"ok": True, "revoked": key_id}


# --- Token Usage ---

@app.get("/api/token-usage")
def get_token_usage(workspace_id: Optional[str] = None, auth: AuthContext = Depends(require_read)):
    wid = workspace_id or (auth.workspace_id if settings.auth_enabled else None)
    return store.get_token_usage_summary(workspace_id=wid)


@app.get("/api/cost-estimate")
def cost_estimate(model: str = "gpt-4o-mini", input_tokens: int = 0, output_tokens: int = 0):
    """Return a cost estimate for a given token count before running LLM."""
    cost = estimate_cost_usd(model, input_tokens, output_tokens)
    rates = settings.pricing.get(model, {})
    return {
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": round(cost, 6),
        "rates_per_1m": rates,
    }


@app.get("/artifact/{artifact_type}/{house_id}", response_class=HTMLResponse)
def serve_artifact(
    artifact_type: str,
    house_id: str,
    stage: str = "awareness",
    channels: str = "linkedin",
    competitor: str = "",
    auth: AuthContext = Depends(get_auth_context),
):
    """Serve a standalone HTML artifact page for a message house."""
    if settings.auth_enabled and "read" not in auth.scopes:
        raise HTTPException(403, "Read scope required to view artifacts.")
    try:
        hid = UUID(house_id)
    except ValueError:
        raise HTTPException(400, "Invalid house_id UUID")

    valid_types = ["one_pager", "social_posts", "email_template", "battlecard", "email_sequence"]
    if artifact_type not in valid_types:
        raise HTTPException(400, f"Unknown artifact_type. Use: {', '.join(valid_types)}")

    house = store.get_house(hid)
    if not house:
        raise HTTPException(404, "House not found")

    messages = store.get_key_messages(hid)
    personas = store.get_personas(hid)

    grouped: dict[str, list] = {}
    for m in messages:
        key = str(m.section_type).replace("_", " ").title()
        grouped.setdefault(key, []).append(m.content)

    if artifact_type == "one_pager":
        html = _render_one_pager(house, grouped, personas)
    elif artifact_type == "social_posts":
        target = channels.split(",")
        html = _render_social_posts(house, messages, target)
    elif artifact_type == "battlecard":
        html = _render_battlecard(house, messages, competitor or "Competitor")
    elif artifact_type == "email_sequence":
        html = _render_email_sequence(house, messages)
    else:
        html = _render_email_template(house, messages, stage)

    return HTMLResponse(content=html)


_SECTION_META = {
    "Headline":    {"icon": "✦", "color": "#6366f1", "bg": "#eef2ff"},
    "Subhead":     {"icon": "◈", "color": "#8b5cf6", "bg": "#f5f3ff"},
    "Benefit":     {"icon": "◉", "color": "#059669", "bg": "#ecfdf5"},
    "Use Case":    {"icon": "⬡", "color": "#0891b2", "bg": "#ecfeff"},
    "Proof Point": {"icon": "◆", "color": "#0284c7", "bg": "#e0f2fe"},
    "Objection":   {"icon": "◇", "color": "#dc2626", "bg": "#fef2f2"},
    "Social Proof":{"icon": "★", "color": "#d97706", "bg": "#fffbeb"},
    "Positioning": {"icon": "◎", "color": "#475569", "bg": "#f8fafc"},
}

_BASE_STYLES = """
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root { --bg: #f1f5f9; --fg: #0f172a; --card-bg: #fff; --card-border: #e2e8f0; --muted: #64748b; --muted-2: #94a3b8; }
  body.dark { --bg: #0f172a; --fg: #f1f5f9; --card-bg: #1e293b; --card-border: #334155; --muted: #94a3b8; --muted-2: #64748b; }
  body { font-family: 'Inter', system-ui, sans-serif; background: var(--bg); color: var(--fg); -webkit-font-smoothing: antialiased; transition: background 0.2s, color 0.2s; }
  .theme-toggle { position: fixed; top: 16px; right: 16px; background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 8px; padding: 6px 12px; font-size: 12px; cursor: pointer; color: var(--muted); z-index: 50; }
  @media print { .theme-toggle { display: none; } .page { padding: 0; } .hero { background: #0f172a !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; } .card { box-shadow: none; border: 1px solid #ddd; break-inside: avoid; } }

  .page { max-width: 900px; margin: 0 auto; padding: 40px 24px 80px; }
  .hero { background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%); border-radius: 20px; padding: 52px 48px; margin-bottom: 24px; position: relative; overflow: hidden; }
  .hero::before { content: ''; position: absolute; inset: 0; background: radial-gradient(ellipse at 70% 50%, rgba(99,102,241,0.25) 0%, transparent 60%); }
  .hero-label { display: inline-flex; align-items: center; gap: 6px; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.15); color: rgba(255,255,255,0.7); font-size: 11px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; padding: 5px 12px; border-radius: 100px; margin-bottom: 20px; }
  .hero h1 { font-size: 42px; font-weight: 800; color: #fff; line-height: 1.1; letter-spacing: -0.02em; margin-bottom: 12px; position: relative; }
  .hero-tagline { font-size: 18px; color: rgba(255,255,255,0.65); font-weight: 400; line-height: 1.5; margin-bottom: 24px; position: relative; max-width: 580px; }
  .hero-audience { display: inline-block; background: rgba(99,102,241,0.25); border: 1px solid rgba(99,102,241,0.4); color: #a5b4fc; font-size: 13px; font-weight: 500; padding: 6px 14px; border-radius: 100px; position: relative; }
  .card { background: #fff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 32px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04); }
  .card-label { font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #94a3b8; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
  .card-label::after { content: ''; flex: 1; height: 1px; background: #f1f5f9; }
  .positioning-text { font-size: 17px; color: #334155; line-height: 1.7; font-weight: 400; }
  .diff-text { margin-top: 16px; font-size: 14px; color: #64748b; line-height: 1.6; padding-left: 16px; border-left: 3px solid #e2e8f0; }
  .messages-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  @media (max-width: 640px) { .messages-grid { grid-template-columns: 1fr; } }
  .section-block { border-radius: 12px; padding: 20px; }
  .section-icon { font-size: 14px; margin-right: 6px; }
  .section-title { font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 12px; display: flex; align-items: center; }
  .msg-item { display: flex; gap: 10px; align-items: flex-start; padding: 8px 0; border-bottom: 1px solid rgba(0,0,0,0.05); }
  .msg-item:last-child { border-bottom: none; padding-bottom: 0; }
  .msg-num { min-width: 20px; height: 20px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; margin-top: 1px; flex-shrink: 0; }
  .msg-text { font-size: 13.5px; color: #334155; line-height: 1.5; }
  .personas-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; }
  .persona-card { border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; background: #fafafa; }
  .persona-avatar { width: 40px; height: 40px; border-radius: 12px; background: linear-gradient(135deg, #6366f1, #8b5cf6); display: flex; align-items: center; justify-content: center; color: #fff; font-weight: 700; font-size: 15px; margin-bottom: 12px; }
  .persona-name { font-size: 15px; font-weight: 600; color: #0f172a; margin-bottom: 4px; }
  .persona-desc { font-size: 12.5px; color: #64748b; line-height: 1.5; margin-bottom: 12px; }
  .pain-tag { display: inline-block; background: #fef2f2; color: #dc2626; font-size: 11px; font-weight: 500; padding: 3px 8px; border-radius: 6px; margin: 2px 2px 0 0; }
  .footer { text-align: center; margin-top: 32px; }
  .footer-badge { display: inline-flex; align-items: center; gap: 6px; background: #fff; border: 1px solid #e2e8f0; color: #94a3b8; font-size: 11px; font-weight: 500; padding: 6px 14px; border-radius: 100px; }
  .post-card { border: 1px solid #e2e8f0; border-radius: 14px; padding: 24px; margin-bottom: 16px; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
  .post-badge { display: inline-flex; align-items: center; gap-4px; font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 100px; margin-right: 6px; margin-bottom: 14px; }
  .post-text { font-size: 15px; color: #1e293b; line-height: 1.7; white-space: pre-wrap; }
  .email-field { padding: 20px 0; border-bottom: 1px solid #f1f5f9; }
  .email-field:last-child { border-bottom: none; }
  .email-label { font-size: 10px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: #94a3b8; margin-bottom: 8px; }
  .email-value { font-size: 15px; color: #1e293b; line-height: 1.6; }
  .email-value.subject { font-size: 18px; font-weight: 600; }
  .email-value.cta { font-size: 16px; font-weight: 600; color: #6366f1; }
  .stage-tabs { display: flex; gap: 8px; margin-bottom: 24px; flex-wrap: wrap; }
  .stage-tab { padding: 6px 16px; border-radius: 100px; font-size: 12px; font-weight: 600; border: 1.5px solid #e2e8f0; color: #64748b; text-decoration: none; }
  .stage-tab.active { background: #0f172a; color: #fff; border-color: #0f172a; }
"""


def _base_html(title: str, body: str, extra_styles: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>{_BASE_STYLES}{extra_styles}</style>
</head>
<body>
  <button class="theme-toggle" onclick="document.body.classList.toggle('dark')">&#9680; Toggle theme</button>
  <div class="page">
{body}
  </div>
  <script>
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {{
      document.body.classList.add('dark');
    }}
  </script>
</body>
</html>"""


def _render_one_pager(house, grouped: dict, personas: list) -> str:
    last_synced = house.last_synced.strftime("%Y-%m-%d") if house.last_synced else "—"
    msg_count = sum(len(v) for v in grouped.values())

    # Hero
    hero = f"""<div class="hero">
      <div class="hero-label">⬡ MsgStack &nbsp;·&nbsp; Message House</div>
      <h1>{house.name}</h1>
      <p class="hero-tagline">{house.tagline or house.positioning[:100] if house.positioning else ""}</p>
      {"<span class='hero-audience'>"+house.audience+"</span>" if house.audience else ""}
    </div>"""

    # Positioning card
    pos_card = f"""<div class="card">
      <div class="card-label">Positioning</div>
      <p class="positioning-text">{house.positioning or "—"}</p>
      {"<p class='diff-text'>"+house.differentiation+"</p>" if house.differentiation else ""}
    </div>"""

    # Key messages grid
    section_order = ["Headline", "Subhead", "Benefit", "Use Case", "Proof Point", "Objection", "Social Proof", "Positioning"]
    blocks = ""
    for sec in section_order:
        msgs = grouped.get(sec, [])
        if not msgs:
            continue
        meta = _SECTION_META.get(sec, {"icon": "◉", "color": "#475569", "bg": "#f8fafc"})
        items = "".join(
            f'<div class="msg-item"><span class="msg-num" style="background:{meta["bg"]};color:{meta["color"]}">{i+1}</span><span class="msg-text">{m}</span></div>'
            for i, m in enumerate(msgs[:4])
        )
        blocks += f"""<div class="section-block" style="background:{meta["bg"]}">
        <div class="section-title" style="color:{meta["color"]}"><span class="section-icon">{meta["icon"]}</span>{sec}</div>
        {items}
      </div>"""

    msgs_card = f"""<div class="card">
      <div class="card-label">Key Messages &nbsp;·&nbsp; {msg_count} total</div>
      <div class="messages-grid">{blocks}</div>
    </div>"""

    # Personas
    persona_items = ""
    for p in personas:
        initials = "".join(w[0].upper() for w in p.name.split()[:2])
        pain_tags = "".join(f'<span class="pain-tag">{pp[:40]}</span>' for pp in (p.pain_points or [])[:3])
        persona_items += f"""<div class="persona-card">
        <div class="persona-avatar">{initials}</div>
        <div class="persona-name">{p.name}</div>
        <div class="persona-desc">{(p.description or "")[:160]}</div>
        {pain_tags}
      </div>"""

    personas_card = f"""<div class="card">
      <div class="card-label">Target Personas &nbsp;·&nbsp; {len(personas)} defined</div>
      <div class="personas-grid">{persona_items}</div>
    </div>"""

    footer = f"""<div class="footer">
      <span class="footer-badge">⬡ msgstack MCP &nbsp;·&nbsp; {last_synced} &nbsp;·&nbsp; {msg_count} messages &nbsp;·&nbsp; {len(personas)} personas</span>
    </div>"""

    body = hero + pos_card + msgs_card + personas_card + footer
    return _base_html(f"{house.name} — Messaging One Pager", body)


def _render_social_posts(house, messages: list, channels: list) -> str:
    posts = []
    for m in messages:
        for ch in channels:
            variant = (m.variants or {}).get(ch)
            if variant:
                posts.append({
                    "channel": ch.title(),
                    "section": str(m.section_type).replace("_", " ").title(),
                    "content": variant,
                    "priority": m.priority,
                })

    ch_label = ", ".join(c.title() for c in channels)
    hero = f"""<div class="hero">
      <div class="hero-label">⬡ MsgStack &nbsp;·&nbsp; Social Posts</div>
      <h1>{house.name}</h1>
      <p class="hero-tagline">{len(posts)} posts ready for {ch_label}</p>
      {"<span class='hero-audience'>"+house.audience+"</span>" if house.audience else ""}
    </div>"""

    if not posts:
        posts_html = '<div class="card"><p style="color:#64748b">No channel variants found. Add LinkedIn variants to your messages.</p></div>'
    else:
        posts_html = ""
        ch_colors = {"linkedin": ("#0a66c2", "#e8f0fe"), "twitter": ("#000", "#f0f0f0"), "email": ("#6366f1", "#eef2ff")}
        for post in posts:
            meta = _SECTION_META.get(post["section"], {"icon": "◉", "color": "#475569", "bg": "#f8fafc"})
            ch = post["channel"].lower()
            ch_color, ch_bg = ch_colors.get(ch, ("#475569", "#f8fafc"))
            posts_html += f"""<div class="post-card">
        <div>
          <span class="post-badge" style="background:{ch_bg};color:{ch_color}">{post['channel']}</span>
          <span class="post-badge" style="background:{meta['bg']};color:{meta['color']}">{meta['icon']} {post['section']}</span>
        </div>
        <p class="post-text">{post['content']}</p>
      </div>"""

    footer = '<div class="footer"><span class="footer-badge">⬡ msgstack MCP</span></div>'
    return _base_html(f"{house.name} — Social Posts", hero + posts_html + footer)


def _render_email_template(house, messages: list, stage: str) -> str:
    headlines = [m for m in messages if str(m.section_type) == "headline"]
    benefits  = [m for m in messages if str(m.section_type) == "benefit"]
    proofs    = [m for m in messages if str(m.section_type) == "proof_point"]

    stage_map = {
        "awareness": {
            "subject": headlines[0].content[:70] if headlines else (house.tagline or ""),
            "hook": benefits[0].content if benefits else house.positioning,
            "body": house.differentiation or house.positioning,
            "cta": f"See how {house.name} works →",
        },
        "consideration": {
            "subject": f"How teams like yours use {house.name}",
            "hook": proofs[0].content if proofs else (benefits[0].content if benefits else house.positioning),
            "body": house.positioning,
            "cta": "Book a 30-min demo →",
        },
        "decision": {
            "subject": f"Ready to get started with {house.name}?",
            "hook": (benefits[0].variants or {}).get("email", benefits[0].content) if benefits else house.positioning,
            "body": house.differentiation or house.positioning,
            "cta": "Start your free trial →",
        },
    }
    content = stage_map.get(stage, stage_map["awareness"])
    stages = ["awareness", "consideration", "decision"]
    tabs = "".join(
        f'<span class="stage-tab {"active" if s == stage else ""}">{s.title()}</span>'
        for s in stages
    )

    hero = f"""<div class="hero">
      <div class="hero-label">⬡ MsgStack &nbsp;·&nbsp; Email Template</div>
      <h1>{house.name}</h1>
      <p class="hero-tagline">{stage.title()} stage · outbound email</p>
    </div>"""

    email_card = f"""<div class="card">
      <div class="card-label">Funnel Stage</div>
      <div class="stage-tabs">{tabs}</div>
      <div class="card-label" style="margin-top:8px">Email Content</div>
      <div class="email-field"><div class="email-label">Subject Line</div><div class="email-value subject">{content['subject']}</div></div>
      <div class="email-field"><div class="email-label">Opening Hook</div><div class="email-value">{content['hook']}</div></div>
      <div class="email-field"><div class="email-label">Body Copy</div><div class="email-value">{content['body']}</div></div>
      <div class="email-field"><div class="email-label">Call to Action</div><div class="email-value cta">{content['cta']}</div></div>
    </div>"""

    footer = '<div class="footer"><span class="footer-badge">⬡ msgstack MCP</span></div>'
    return _base_html(f"{house.name} — Email ({stage.title()})", hero + email_card + footer)


def _render_battlecard(house, messages: list, competitor: str) -> str:
    objections = [m for m in messages if str(m.section_type).endswith("objection")]
    proofs = [m for m in messages if str(m.section_type).endswith("proof_point")]
    benefits = [m for m in messages if str(m.section_type).endswith("benefit")]

    extra = """
  .bc-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  @media (max-width: 640px) { .bc-grid { grid-template-columns: 1fr; } }
  .bc-col { border-radius: 12px; padding: 20px; }
  .bc-col.ours { background: #ecfdf5; border: 1.5px solid #34d399; }
  .bc-col.theirs { background: #fef2f2; border: 1.5px solid #f87171; }
  .bc-col-title { font-size: 12px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; margin-bottom: 12px; }
  .bc-col.ours .bc-col-title { color: #059669; }
  .bc-col.theirs .bc-col-title { color: #dc2626; }
  .bc-row { font-size: 13.5px; color: #334155; padding: 6px 0; border-bottom: 1px solid rgba(0,0,0,0.06); line-height: 1.5; }
  .bc-row:last-child { border-bottom: none; }
  .objection-row { padding: 10px 12px; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 8px; }
  .objection-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; color: #94a3b8; margin-bottom: 4px; }
  .objection-text { font-size: 13.5px; color: #1e293b; line-height: 1.5; }
"""
    hero = f"""<div class="hero">
      <div class="hero-label">⬡ MsgStack &nbsp;·&nbsp; Battlecard</div>
      <h1>{house.name} vs {competitor}</h1>
      <p class="hero-tagline">{house.tagline or house.positioning[:80] if house.positioning else ""}</p>
    </div>"""

    our_items = "".join(f'<div class="bc-row">✓ {b.content}</div>' for b in benefits[:5])
    their_items = "".join(f'<div class="bc-row">✗ {o.content}</div>' for o in objections[:4]) or \
        '<div class="bc-row" style="color:#94a3b8;">Add competitor weaknesses via objection messages</div>'

    compare_card = f"""<div class="card">
      <div class="card-label">Head-to-Head Comparison</div>
      <div class="bc-grid">
        <div class="bc-col ours">
          <div class="bc-col-title">✦ {house.name}</div>
          {our_items or '<div class="bc-row" style="color:#94a3b8;">Add benefit messages</div>'}
        </div>
        <div class="bc-col theirs">
          <div class="bc-col-title">✗ {competitor}</div>
          {their_items}
        </div>
      </div>
    </div>"""

    pos_card = f"""<div class="card">
      <div class="card-label">Positioning Against {competitor}</div>
      <p class="positioning-text">{house.positioning or "—"}</p>
      {"<p class='diff-text'>" + house.differentiation + "</p>" if house.differentiation else ""}
    </div>"""

    proof_items = "".join(f'<div class="bc-row">◆ {p.content}</div>' for p in proofs[:5])
    proof_card = f"""<div class="card">
      <div class="card-label">Proof Points</div>
      {proof_items or '<p style="color:#94a3b8;font-size:13px;">Add proof_point messages to populate this section</p>'}
    </div>""" if proofs else ""

    obj_items = "".join(f'''<div class="objection-row">
        <div class="objection-label">Objection {i+1}</div>
        <div class="objection-text">{o.content}</div>
      </div>''' for i, o in enumerate(objections[:6]))
    obj_card = f"""<div class="card">
      <div class="card-label">Objection Responses</div>
      {obj_items or '<p style="color:#94a3b8;font-size:13px;">Add objection messages to populate this section</p>'}
    </div>"""

    footer = '<div class="footer"><span class="footer-badge">⬡ msgstack MCP · Battlecard</span></div>'
    return _base_html(f"{house.name} vs {competitor} — Battlecard", hero + compare_card + pos_card + proof_card + obj_card + footer, extra)


def _render_email_sequence(house, messages: list) -> str:
    headlines = [m for m in messages if str(m.section_type).endswith("headline")]
    benefits = [m for m in messages if str(m.section_type).endswith("benefit")]
    proofs = [m for m in messages if str(m.section_type).endswith("proof_point")]

    extra = """
  .seq-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
  @media (max-width: 700px) { .seq-grid { grid-template-columns: 1fr; } }
  .seq-card { border-radius: 14px; padding: 24px; border: 1.5px solid #e2e8f0; background: #fff; position: relative; }
  .seq-number { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 13px; color: #fff; margin-bottom: 14px; }
  .seq-stage { font-size: 10px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; margin-bottom: 8px; }
  .seq-subject { font-size: 15px; font-weight: 600; color: #0f172a; line-height: 1.4; margin-bottom: 10px; }
  .seq-body { font-size: 13px; color: #475569; line-height: 1.6; margin-bottom: 12px; }
  .seq-cta { display: inline-block; font-size: 13px; font-weight: 600; color: #6366f1; text-decoration: none; border-bottom: 1px solid #6366f1; }
  .seq-connector { display: none; }
  @media (min-width: 700px) { .seq-connector { display: flex; align-items: center; justify-content: center; font-size: 18px; color: #cbd5e1; } }
"""
    stages = [
        {
            "num": "1", "color": "#6366f1", "stage": "Awareness",
            "subject": headlines[0].content[:70] if headlines else (house.tagline or house.name),
            "body": benefits[0].content if benefits else house.positioning or "",
            "cta": f"Learn how {house.name} works →",
        },
        {
            "num": "2", "color": "#0891b2", "stage": "Consideration",
            "subject": f"How teams like yours use {house.name}",
            "body": proofs[0].content if proofs else (benefits[1].content if len(benefits) > 1 else house.differentiation or house.positioning or ""),
            "cta": "See the case study →",
        },
        {
            "num": "3", "color": "#059669", "stage": "Decision",
            "subject": f"Ready to get started with {house.name}?",
            "body": house.differentiation or house.positioning or "",
            "cta": "Start your free trial →",
        },
    ]

    hero = f"""<div class="hero">
      <div class="hero-label">⬡ MsgStack &nbsp;·&nbsp; Email Sequence</div>
      <h1>{house.name}</h1>
      <p class="hero-tagline">3-stage nurture sequence · Awareness → Consideration → Decision</p>
    </div>"""

    cards = ""
    for i, s in enumerate(stages):
        cards += f"""<div class="seq-card">
        <div class="seq-number" style="background:{s['color']}">{s['num']}</div>
        <div class="seq-stage" style="color:{s['color']}">{s['stage']}</div>
        <div class="seq-subject">{s['subject']}</div>
        <div class="seq-body">{s['body'][:300]}</div>
        <span class="seq-cta">{s['cta']}</span>
      </div>"""

    seq_card = f"""<div class="card">
      <div class="card-label">3-Email Nurture Sequence</div>
      <div class="seq-grid">{cards}</div>
    </div>"""

    footer = '<div class="footer"><span class="footer-badge">⬡ msgstack MCP · Email Sequence</span></div>'
    return _base_html(f"{house.name} — Email Sequence", hero + seq_card + footer, extra)


@app.get("/api/preview/{skill_id}/{house_id}")
def get_artifact_preview(skill_id: str, house_id: str, request: Request):
    """Get Prefab preview HTML for an artifact."""
    from src.pipeline.generator import ArtifactGenerator
    from src.artifacts.prefab_generator import build_artifact_preview

    generator = ArtifactGenerator(store, skills)

    try:
        artifact = generator.generate(skill_id, house_id, {})
        prefab_app = build_artifact_preview(skill_id, artifact.sections, artifact.house_name, artifact.house_id)
        
        # Check if it's an HTMX request
        if request.headers.get("HX-Request"):
            return HTMLResponse(content=prefab_app.html())
            
        return {"html": prefab_app.html()}
    except Exception as e:
        log.error("Preview generation failed: %s", e)
        raise HTTPException(500, str(e))


@app.get("/api/artifacts/{artifact_id}/image")
def get_artifact_image(artifact_id: str):
    """Generate a high-fidelity PNG image using Satori + resvg-python."""
    import subprocess
    from resvg_py import render_svg
    from src.pipeline.generator import ArtifactGenerator
    
    record = store.get_artifact(UUID(artifact_id))
    if not record:
        raise HTTPException(404, "Artifact not found")

    # Minimal Tailwind HTML for Satori
    # We'll use a simple card layout for now
    html_content = f"""
    <div style="display: flex; flex-direction: column; width: 100%; height: 100%; background-color: white; padding: 40px; font-family: 'WorkSans';">
        <div style="display: flex; align-items: center; margin-bottom: 20px;">
            <div style="width: 40px; height: 40px; background-color: #6366f1; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-weight: 800; font-size: 20px; margin-right: 15px;">M</div>
            <div style="font-size: 24px; font-weight: 700; color: #1e293b;">{record['house_name']}</div>
        </div>
        <div style="font-size: 48px; font-weight: 800; color: #0f172a; margin-bottom: 10px; line-height: 1.1;">{record['skill_id'].replace('_', ' ').title()}</div>
        <div style="font-size: 20px; color: #64748b; margin-bottom: 30px;">Generated via MsgStack MCP</div>
        <div style="flex: 1; display: flex; flex-direction: column; background-color: #f8fafc; border-radius: 12px; padding: 30px; border: 1px solid #e2e8f0;">
            <div style="font-size: 18px; color: #475569; line-height: 1.6;">{record['raw_content'][:500]}...</div>
        </div>
    </div>
    """

    try:
        # 1. Run Node.js bridge to get SVG
        cmd = ["node", "src/artifacts/render.js", html_content]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        svg_data = result.stdout

        # 2. Rasterize SVG to PNG
        png_data = render_svg(svg_data)
        
        return HTMLResponse(content=png_data, media_type="image/png")
    except Exception as e:
        log.error("Image generation failed: %s", e)
        raise HTTPException(500, f"Failed to generate image: {str(e)}")
@app.get("/artifact/{artifact_type}/{house_id}", response_class=HTMLResponse)
def view_artifact(artifact_type: str, house_id: str, request: Request):
    """Visual view of an artifact with Paged.js support."""
    from src.pipeline.generator import ArtifactGenerator
    generator = ArtifactGenerator(store, skills)
    
    try:
        artifact = generator.generate(artifact_type, house_id, {})
        return templates.TemplateResponse(request, "artifact_visual.html", {
            "artifact": artifact,
            "type": artifact_type,
            "house_name": artifact.house_name
        })
    except Exception as e:
        log.error("Visual generation failed: %s", e)
        raise HTTPException(500, str(e))


# --- Frontend ---

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
@app.get("/frameworks", response_class=HTMLResponse)
@app.get("/upload", response_class=HTMLResponse)
@app.get("/artifacts", response_class=HTMLResponse)
@app.get("/skills", response_class=HTMLResponse)
@app.get("/settings", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)