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
    save_path.write_text(markdown, encoding="utf-8")

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
        "know_your_market": structured.know_your_market,
        "missing_sections": structured.missing_sections,
        "completeness_score": max(0, 100 - len(structured.missing_sections) * 10),
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
    """Generate an artifact using a skill and return content for preview."""
    from src.pipeline.generator import ArtifactGenerator

    generator = ArtifactGenerator(store, skills)

    try:
        artifact = generator.generate(skill_id, house_id, custom_context or {})
        visual_types = {"one_pager", "social_posts", "email_template"}
        artifact_type = skill_id if skill_id in visual_types else None
        visual_url = f"{os.environ.get('MSGSTACK_BASE_URL', 'http://localhost:8001')}/artifact/{artifact_type}/{house_id}" if artifact_type else None
        return {
            "skill_id": skill_id,
            "house_name": artifact.house_name,
            "house_id": house_id,
            "sections": artifact.sections,
            "raw_content": artifact.raw_content,
            "visual_url": visual_url,
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

    import openai as _oai
    client = _oai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a B2B messaging strategist. Be specific, benefit-led, and concise."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
        max_tokens=600,
    )
    return {"section": section, "content": resp.choices[0].message.content.strip()}


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
  body { font-family: 'Inter', system-ui, sans-serif; background: #f1f5f9; color: #0f172a; -webkit-font-smoothing: antialiased; }
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
  <div class="page">
{body}
  </div>
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
    return HTMLResponse(open("src/web/index.html", encoding="utf-8").read(), media_type="text/html; charset=utf-8")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)