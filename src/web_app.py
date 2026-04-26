"""FastAPI web app — admin UX for MsgStack MCP management."""

import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from src.models import Channel, HouseStatus, KeyMessage, MessageHouse, Persona, SectionType
from src.store import Store
from src.pipeline.extract import ExtractionError, extract_text, chunk_text, save_upload
from src.pipeline.structure import HouseStructurer, StructuredHouse
from src.pipeline.skills import SkillManager

load_dotenv()

app = FastAPI(title="MsgStack Admin", version="0.1.0", redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

store = Store("msgstack.db")
store.init()

skills = SkillManager(skills_dir=str(DATA_DIR / "skills"))
structurer = HouseStructurer()


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
def list_houses(query: Optional[str] = None):
    houses = store.list_houses()
    result = []
    for h in houses:
        msgs = store.get_key_messages(h.id)
        personas = store.get_personas(h.id)
        item = {
            "id": str(h.id),
            "name": h.name,
            "source": h.source,
            "status": h.status,
            "summary": h.summary[:150] + ("..." if len(h.summary) > 150 else ""),
            "persona_count": len(personas),
            "message_count": len(msgs),
            "last_synced": h.last_synced.isoformat() if h.last_synced else None,
        }
        if query:
            if query.lower() not in h.name.lower() and query.lower() not in h.summary.lower():
                continue
        result.append(item)
    return result


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
        last_synced=datetime.utcnow(),
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
    return {"ok": True}


@app.delete("/api/houses/{house_id}")
def delete_house(house_id: str):
    if not store.delete_house(UUID(house_id)):
        raise HTTPException(404, "House not found")
    return {"ok": True}


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
    return {"ok": True}


@app.delete("/api/messages/{msg_id}")
def delete_message(msg_id: str):
    if not _delete_message(msg_id):
        raise HTTPException(404, "Message not found")
    return {"ok": True}


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
    return {"ok": True}


@app.delete("/api/personas/{persona_id}")
def delete_persona(persona_id: str):
    if not _delete_persona(persona_id):
        raise HTTPException(404, "Persona not found")
    return {"ok": True}


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
):
    """Upload a file, extract text, and run the LLM structurer to create a MessageHouse."""
    file_path = UPLOAD_DIR / file.filename
    save_upload(file.file, file_path)

    try:
        text = extract_text(file_path)
    except ExtractionError as e:
        raise HTTPException(400, str(e))

    if not source_name:
        source_name = Path(file.filename).stem

    try:
        structured = structurer.structure(text, source_name=source_name)
    except Exception as e:
        raise HTTPException(500, f"LLM structuring failed: {e}")

    house = MessageHouse(
        name=structured.name,
        source="upload",
        source_id=file.filename,
        summary=structured.summary,
        audience=structured.audience,
        brand_personality=structured.brand_personality,
        positioning=structured.positioning,
        tagline=structured.tagline,
        differentiation=structured.differentiation,
        status=HouseStatus.ACTIVE,
        last_synced=datetime.utcnow(),
    )
    store.upsert_house(house)

    for km in structured.key_messages:
        msg = KeyMessage(
            message_house_id=house.id,
            section_type=SectionType(km["section_type"]),
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
    save_path.write_text(markdown)

    from src.grounding.search import GroundingEngine
    engine = GroundingEngine(
        store=store,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        pinecone_api_key=os.environ.get("PINECONE_API_KEY"),
        index_name=os.environ.get("PINECONE_INDEX", "msgstack-chunks"),
    )
    try:
        engine.index_house(house.id)
        indexed = True
    except Exception:
        indexed = False

    return {
        "id": str(house.id),
        "name": house.name,
        "status": "created",
        "message_count": len(structured.key_messages),
        "persona_count": len(structured.personas),
        "indexed": indexed,
        "markdown": markdown,
    }


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
    updated = skills.update_skill(skill_id, data)
    return updated


# --- Stats ---

@app.get("/api/stats")
def get_stats():
    houses = store.list_houses()
    total_messages = sum(len(store.get_key_messages(h.id)) for h in houses)
    total_personas = sum(len(store.get_personas(h.id)) for h in houses)
    skill_list = skills.list_skills()
    return {
        "house_count": len(houses),
        "message_count": total_messages,
        "persona_count": total_personas,
        "skill_count": len(skill_list),
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

    engine = GroundingEngine(
        store=store,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        pinecone_api_key=os.environ.get("PINECONE_API_KEY"),
        index_name=os.environ.get("PINECONE_INDEX", "msgstack-chunks"),
    )

    indexed_count = 0
    for house in houses:
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

    engine = GroundingEngine(
        store=store,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        pinecone_api_key=os.environ.get("PINECONE_API_KEY"),
        index_name=os.environ.get("PINECONE_INDEX", "msgstack-chunks"),
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

    engine = GroundingEngine(
        store=store,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        pinecone_api_key=os.environ.get("PINECONE_API_KEY"),
        index_name=os.environ.get("PINECONE_INDEX", "msgstack-chunks"),
    )

    total_vectors = 0
    for house in houses:
        try:
            vectors = engine.index_house(house.id)
            total_vectors += vectors
        except Exception:
            pass

    return {
        "indexed_houses": len(houses),
        "total_vectors": total_vectors,
    }


# --- Internal helpers ---

def _find_message(msg_id: str) -> Optional[KeyMessage]:
    for h in store.list_houses():
        for m in store.get_key_messages(h.id):
            if str(m.id) == msg_id:
                return m
    return None


def _find_persona(persona_id: str) -> Optional[Persona]:
    for h in store.list_houses():
        for p in store.get_personas(h.id):
            if str(p.id) == persona_id:
                return p
    return None


def _delete_message(msg_id: str) -> bool:
    try:
        store.engine.execute(f"DELETE FROM key_messages WHERE id = '{msg_id}'")
        return True
    except Exception:
        return False


def _delete_persona(persona_id: str) -> bool:
    try:
        store.engine.execute(f"DELETE FROM personas WHERE id = '{persona_id}'")
        return True
    except Exception:
        return False


# --- Artifact Generation & Preview ---

@app.post("/api/generate")
def generate_artifact(
    skill_id: str = Form(...),
    house_id: str = Form(...),
    custom_context: Optional[dict] = Form(None),
):
    """Generate an artifact using a skill and return Prefab HTML for preview."""
    from src.pipeline.generator import ArtifactGenerator
    from src.artifacts.prefab_generator import build_artifact_preview

    generator = ArtifactGenerator(store, skills)

    try:
        artifact = generator.generate(skill_id, house_id, custom_context or {})
        
        prefab_app = build_artifact_preview(skill_id, artifact.sections, artifact.house_name, artifact.house_id)
        
        html = prefab_app.html()
        
        return {
            "skill_id": skill_id,
            "house_name": artifact.house_name,
            "sections": artifact.sections,
            "raw_content": artifact.raw_content,
            "preview_html": html,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/artifact/{artifact_type}/{house_id}", response_class=HTMLResponse)
def serve_artifact(artifact_type: str, house_id: str, stage: str = "awareness", channels: str = "linkedin"):
    """Serve a standalone HTML artifact page for a message house."""
    try:
        hid = UUID(house_id)
    except ValueError:
        raise HTTPException(400, "Invalid house_id UUID")

    valid_types = ["one_pager", "social_posts", "email_template"]
    if artifact_type not in valid_types:
        raise HTTPException(400, f"Unknown artifact_type. Use: {', '.join(valid_types)}")

    house = store.get_house(hid)
    if not house:
        raise HTTPException(404, "House not found")

    messages = store.get_key_messages(hid)
    personas = store.get_personas(hid)

    # Group messages by section type
    grouped: dict[str, list] = {}
    for m in messages:
        key = str(m.section_type).replace("_", " ").title()
        grouped.setdefault(key, []).append(m.content)

    if artifact_type == "one_pager":
        html = _render_one_pager(house, grouped, personas)
    elif artifact_type == "social_posts":
        target = channels.split(",")
        html = _render_social_posts(house, messages, target)
    else:
        html = _render_email_template(house, messages, stage)

    return HTMLResponse(content=html)


def _base_html(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 text-gray-900 min-h-screen">
  <div class="max-w-4xl mx-auto py-10 px-4 space-y-6">
{body}
  </div>
</body>
</html>"""


def _card(content: str, cls: str = "") -> str:
    return f'<div class="bg-white rounded-xl border border-gray-200 shadow-sm p-6 {cls}">{content}</div>'


def _render_one_pager(house, grouped: dict, personas: list) -> str:
    last_synced = house.last_synced.strftime("%Y-%m-%d") if house.last_synced else "—"

    header = f"""
    <div class="flex items-start justify-between flex-wrap gap-2">
      <div>
        <h1 class="text-2xl font-bold">{house.name}</h1>
        <p class="text-gray-500 mt-1">{house.audience or ""}</p>
      </div>
      <span class="text-xs bg-gray-100 text-gray-600 px-3 py-1 rounded-full uppercase tracking-wide">One Pager</span>
    </div>"""

    positioning = f"""
    <h2 class="text-lg font-semibold mb-3">Positioning</h2>
    <p class="text-gray-700 leading-relaxed">{house.positioning or "—"}</p>
    {"<p class='mt-3 inline-block bg-blue-50 text-blue-700 text-sm px-3 py-1 rounded-full'>"+house.tagline+"</p>" if house.tagline else ""}
    {"<p class='mt-3 text-sm text-gray-500'>"+house.differentiation+"</p>" if house.differentiation else ""}"""

    sections_html = ""
    section_order = ["Headline", "Subhead", "Benefit", "Proof Point", "Objection", "Social Proof", "Positioning"]
    for sec in section_order:
        msgs = grouped.get(sec, [])
        if not msgs:
            continue
        items = "".join(
            f'<li class="flex gap-2"><span class="text-gray-400 font-mono text-xs mt-1">{i+1}</span><span class="text-gray-700">{m}</span></li>'
            for i, m in enumerate(msgs[:5])
        )
        sections_html += f"""
      <div>
        <h3 class="text-sm font-semibold uppercase tracking-wide text-gray-500 mb-2">{sec}</h3>
        <ul class="space-y-2">{items}</ul>
      </div>"""

    key_messages = f'<h2 class="text-lg font-semibold mb-4">Key Messages</h2><div class="space-y-5">{sections_html}</div>'

    persona_cards = ""
    for p in personas:
        pain = "".join(f'<li class="text-sm text-gray-600">• {pp}</li>' for pp in (p.pain_points or [])[:3])
        persona_cards += f"""
      <div class="border border-gray-200 rounded-lg p-4">
        <h3 class="font-semibold">{p.name}</h3>
        <p class="text-sm text-gray-500 mt-1">{(p.description or "")[:150]}</p>
        {"<ul class='mt-2 space-y-1'>"+pain+"</ul>" if pain else ""}
      </div>"""

    personas_section = f'<h2 class="text-lg font-semibold mb-3">Personas</h2><div class="grid grid-cols-1 sm:grid-cols-2 gap-4">{persona_cards}</div>'

    footer = f'<p class="text-xs text-gray-400 text-center">Last synced: {last_synced} · {len(house.positioning or "")} chars positioning · msgstack MCP</p>'

    body = (
        _card(header)
        + "\n    " + _card(positioning)
        + "\n    " + _card(key_messages)
        + "\n    " + _card(personas_section)
        + "\n    " + footer
    )
    return _base_html(f"{house.name} — One Pager", body)


def _render_social_posts(house, messages: list, channels: list) -> str:
    posts = []
    for m in messages:
        for ch in channels:
            variant = (m.variants or {}).get(ch)
            if variant:
                posts.append((ch.title(), str(m.section_type).replace("_", " ").title(), variant))

    if not posts:
        posts_html = '<p class="text-gray-500">No channel variants found for these channels.</p>'
    else:
        posts_html = ""
        for ch, sec, content in posts:
            posts_html += f"""
      <div class="border border-gray-200 rounded-lg p-4">
        <div class="flex gap-2 mb-3">
          <span class="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">{ch}</span>
          <span class="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{sec}</span>
        </div>
        <p class="text-gray-700 whitespace-pre-wrap text-sm">{content}</p>
      </div>"""

    header = f'<h1 class="text-2xl font-bold">{house.name}</h1><p class="text-gray-500 mt-1">Social posts for: {", ".join(channels)}</p>'
    body_content = f'<h2 class="text-lg font-semibold mb-3">Posts</h2><div class="space-y-4">{posts_html}</div>'
    body = _card(header) + "\n    " + _card(body_content)
    return _base_html(f"{house.name} — Social Posts", body)


def _render_email_template(house, messages: list, stage: str) -> str:
    headlines = [m for m in messages if str(m.section_type) == "headline"]
    benefits = [m for m in messages if str(m.section_type) == "benefit"]
    proofs = [m for m in messages if str(m.section_type) == "proof_point"]

    stage_map = {
        "awareness": {
            "subject": headlines[0].content[:70] if headlines else house.tagline or "",
            "hook": benefits[0].content if benefits else house.positioning,
            "body": house.differentiation or house.positioning,
            "cta": "See how it works →",
        },
        "consideration": {
            "subject": f"How teams like yours use {house.name}",
            "hook": proofs[0].content if proofs else benefits[0].content if benefits else "",
            "body": house.positioning,
            "cta": "Book a 30-min demo →",
        },
        "decision": {
            "subject": f"Ready to get started with {house.name}?",
            "hook": benefits[0].variants.get("email", benefits[0].content) if benefits and benefits[0].variants else (benefits[0].content if benefits else ""),
            "body": house.differentiation or house.positioning,
            "cta": "Start your free trial →",
        },
    }
    content = stage_map.get(stage, stage_map["awareness"])

    def field(label: str, value: str) -> str:
        return f"""
      <div class="border-b border-gray-100 pb-4 last:border-0 last:pb-0">
        <p class="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-1">{label}</p>
        <p class="text-gray-800">{value}</p>
      </div>"""

    email_content = (
        field("Subject line", content["subject"])
        + field("Opening hook", content["hook"])
        + field("Body copy", content["body"])
        + field("Call to action", content["cta"])
    )
    stage_label = stage.title()
    header = f'<h1 class="text-2xl font-bold">{house.name}</h1><p class="text-gray-500 mt-1">Email template · {stage_label} stage</p>'
    body = _card(header) + "\n    " + _card(f'<h2 class="text-lg font-semibold mb-4">Email Content</h2><div class="space-y-4">{email_content}</div>')
    return _base_html(f"{house.name} — Email ({stage_label})", body)


@app.get("/api/preview/{skill_id}/{house_id}")
def get_artifact_preview(skill_id: str, house_id: str):
    """Get Prefab preview HTML for an artifact."""
    from src.pipeline.generator import ArtifactGenerator
    from src.artifacts.prefab_generator import build_artifact_preview

    generator = ArtifactGenerator(store, skills)

    try:
        artifact = generator.generate(skill_id, house_id, {})
        prefab_app = build_artifact_preview(skill_id, artifact.sections, artifact.house_name, artifact.house_id)
        return {"html": prefab_app.html()}
    except Exception as e:
        raise HTTPException(500, str(e))


# --- Frontend ---

@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(open("src/web/index.html").read())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)