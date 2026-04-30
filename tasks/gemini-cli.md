# Task: v0.7 Structuring Prompts — Gemini CLI

**Project:** MsgStack MCP Server  
**Location:** `C:\Users\Abid\msgstack-mcp\`  
**Goal:** Add multi-content-type structuring support to `src/pipeline/structure.py` so that brand guides, competitive briefs, corp narratives, and persona libraries are structured into the same `StructuredHouse` schema using document-type-specific prompts.

---

## Context

`src/pipeline/structure.py` currently has one structuring prompt (`_STRUCTURE_PROMPT`) designed for message houses. The v0.7 milestone adds four new document types. Each type has its own `SectionType` variants and needs a tailored prompt — the LLM needs different instructions to extract "brand voice guidelines" from a brand guide vs "objection handlers" from a message house.

The underlying output model (`StructuredHouse`) stays the same — we're not changing the schema, only the prompt that drives the LLM.

Before editing, read these files completely:
- `src/pipeline/structure.py` — existing structuring logic, `_STRUCTURE_PROMPT`, `Structurer` class
- `src/models.py` — `SectionType` enum (newly expanded), `DocumentType` enum (new in v0.7), `MessageHouse` Pydantic model

---

## Work Stream: Document-Type-Specific Structuring Prompts

### Step 1: Read the existing `_STRUCTURE_PROMPT` in `structure.py`

Understand the format — it instructs GPT-4o-mini to return a JSON object matching `StructuredHouse`. Note which fields are required (`name`, `summary`, `audience`, `positioning`, `tagline`, `differentiation`, `key_messages`, `personas`) and how `key_messages` are structured (`section_type`, `priority`, `content`, `personas`, `channels`).

### Step 2: Add document-type-specific prompt strings

Add these as module-level constants after `_STRUCTURE_PROMPT`. Each prompt should follow the same JSON output contract but give the LLM different extraction instructions.

---

#### `_BRAND_GUIDE_PROMPT`

```
You are extracting brand and style guidelines from a document.

Return a JSON object matching this schema:
{
  "name": "Brand name or document title",
  "summary": "1-2 sentence overview of what this brand guide covers",
  "audience": "Internal teams this guide is intended for (e.g., marketing, content, design)",
  "positioning": "The brand's core positioning or mission statement if present",
  "tagline": "Official tagline or brand slogan if present",
  "differentiation": "What makes this brand's voice/style distinctive",
  "brand_personality": "Voice and tone descriptors extracted from the guide",
  "key_messages": [
    {
      "section_type": "brand_voice | style_rule | word_list",
      "priority": 1-5,
      "content": "The guideline or rule text verbatim or closely paraphrased",
      "personas": [],
      "channels": ["all"]
    }
  ],
  "personas": [],
  "missing_sections": ["list any major sections you couldn't extract"]
}

Rules:
- Use section_type "brand_voice" for tone/personality descriptions
- Use section_type "style_rule" for specific writing rules (capitalization, punctuation, grammar)
- Use section_type "word_list" for approved/banned word lists
- Preserve exact wording for rules — do not paraphrase style_rule or word_list entries
- Set priority 1-2 for mandatory rules, 3-5 for guidance/suggestions
```

---

#### `_COMPETITIVE_BRIEF_PROMPT`

```
You are extracting competitive intelligence from a document.

Return a JSON object matching this schema:
{
  "name": "Competitor name or document title",
  "summary": "1-2 sentence summary of this competitive brief",
  "audience": "Sales, marketing, or product teams this brief is for",
  "positioning": "How we position against this competitor",
  "tagline": "Our differentiated tagline vs this competitor (if present)",
  "differentiation": "Our key advantages over this competitor",
  "brand_personality": "",
  "key_messages": [
    {
      "section_type": "competitor_strength | competitor_weakness | competitive_response",
      "priority": 1-5,
      "content": "The intelligence or response message",
      "personas": [],
      "channels": ["all"]
    }
  ],
  "personas": [],
  "missing_sections": []
}

Rules:
- Use "competitor_strength" for things this competitor does well
- Use "competitor_weakness" for gaps, limitations, or vulnerabilities
- Use "competitive_response" for how we respond to this competitor's claims (our counter-messaging)
- Priority 1-2 for the most decisive competitive factors
```

---

#### `_CORP_NARRATIVE_PROMPT`

```
You are extracting a company's narrative, values, and founding story from a document.

Return a JSON object matching this schema:
{
  "name": "Company name",
  "summary": "1-2 sentence company overview",
  "audience": "Audiences this narrative is for (investors, employees, customers)",
  "positioning": "Core company positioning or mission statement",
  "tagline": "Company tagline or motto if present",
  "differentiation": "What makes this company's story distinct",
  "brand_personality": "Company personality and cultural values",
  "key_messages": [
    {
      "section_type": "narrative_pillar | company_value | founding_story",
      "priority": 1-5,
      "content": "The narrative element",
      "personas": [],
      "channels": ["all"]
    }
  ],
  "personas": [],
  "missing_sections": []
}

Rules:
- Use "narrative_pillar" for the core strategic themes of the company story
- Use "company_value" for stated company values or cultural principles
- Use "founding_story" for origin story elements, key milestones, or the "why we exist" narrative
```

---

#### `_PERSONA_LIBRARY_PROMPT`

```
You are extracting buyer and user persona profiles from a document.

Return a JSON object matching this schema:
{
  "name": "Persona library name or document title",
  "summary": "Brief description of what personas are covered",
  "audience": "Teams these personas are for (sales, marketing, product)",
  "positioning": "",
  "tagline": "",
  "differentiation": "",
  "brand_personality": "",
  "key_messages": [
    {
      "section_type": "persona_detail",
      "priority": 1-3,
      "content": "A specific insight about this persona — a key pain point, buying trigger, or objection in one sentence",
      "personas": ["<persona name>"],
      "channels": ["all"]
    }
  ],
  "personas": [
    {
      "name": "Role title (e.g., CISO, VP Sales)",
      "description": "Who they are and what they own",
      "pain_points": ["specific frustration 1", "..."],
      "buying_triggers": ["event or pressure that makes them evaluate", "..."],
      "objections": ["reason they hesitate to buy", "..."]
    }
  ],
  "missing_sections": []
}

Rules:
- Each persona should appear both as a full Persona object AND as key_messages with section_type "persona_detail"
- key_messages for personas should be atomic, quotable insights (one per message), not summaries
- Set priority 1 for the primary persona, 2-3 for secondary
```

---

### Step 3: Add dispatch logic to `Structurer`

The `Structurer` class has a `structure()` method (or similar). Add a `document_type` parameter:

```python
def structure(self, text: str, document_type: str = "message_house") -> tuple[StructuredHouse, dict]:
```

Inside the method, select the prompt:

```python
_PROMPT_MAP = {
    "message_house": _STRUCTURE_PROMPT,
    "brand_guide": _BRAND_GUIDE_PROMPT,
    "competitive_brief": _COMPETITIVE_BRIEF_PROMPT,
    "corp_narrative": _CORP_NARRATIVE_PROMPT,
    "persona_library": _PERSONA_LIBRARY_PROMPT,
}
prompt = _PROMPT_MAP.get(document_type, _STRUCTURE_PROMPT)
```

Pass the selected `prompt` into `_structure_single_chunk()` (or wherever the LLM call is made).

### Step 4: Propagate `document_type` through the upload pipeline

In `src/web_app.py`, the `/api/extract` or `/api/confirm-structure` endpoint creates a `Structurer` instance. Update it to accept and pass through a `document_type` field from the request body.

The request JSON should accept an optional `document_type: str = "message_house"` field. When present, pass it to `structurer.structure(text, document_type=document_type)`.

Also save `document_type` when persisting the house: `store.upsert_house(..., document_type=document_type)`.

---

## Validation

After implementing, test each prompt manually:
1. Upload the existing ServiceNow messaging house DOCX — confirm it still structures correctly as `message_house`
2. Create a simple test text with brand voice guidelines — pass with `document_type=brand_guide` and verify `brand_voice` / `style_rule` section types appear
3. Confirm no existing tests break (the default `document_type="message_house"` path is unchanged)

---

## Notes

- The `StructuredHouse` output model does NOT need to change — `key_messages` already accepts any `section_type` string
- If `SectionType` validation is strict in `StructuredHouse`, you may need to add `model_config = ConfigDict(use_enum_values=True)` or accept `str` for `section_type` in the structured output model
- The LLM will sometimes hallucinate section types — add a post-processing step that maps unknown section types to the closest valid type for the given `document_type`
