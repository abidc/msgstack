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

app = FastAPI(title="MsgStack Admin", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
STORE_PATH = DATA_DIR / "msgstack.db"
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

store = Store(str(STORE_PATH))
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
                "section_type": m.section_type.value,
                "priority": m.priority,
                "content": m.content,
                "variants": m.variants,
                "personas": m.personas,
                "channels": [c.value for c in m.channels],
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

    return {
        "id": str(house.id),
        "name": house.name,
        "status": "created",
        "message_count": len(structured.key_messages),
        "persona_count": len(structured.personas),
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