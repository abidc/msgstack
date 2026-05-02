"""Design JSON Schema v2 — artifact layout system."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PagePreset(str, Enum):
    LETTER = "letter"
    A4 = "a4"
    WIDE_16_9 = "16:9"


class Orientation(str, Enum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class ZoneType(str, Enum):
    HEADER = "header"
    HERO = "hero"
    POSITIONING_BLOCK = "positioning_block"
    PILLAR_GRID = "pillar_grid"
    MESSAGE_LIST = "message_list"
    PERSONA_STRIP = "persona_strip"
    PROOF_BLOCK = "proof_block"
    CTA_FOOTER = "cta_footer"


class Emphasis(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    MUTED = "muted"


class TextStyle(str, Enum):
    HEADING = "heading"
    BODY = "body"
    CAPTION = "caption"


class Zone(BaseModel):
    id: str
    type: ZoneType
    row: int
    col: int
    colspan: int = 1
    text_content: str = ""
    text_style: TextStyle = TextStyle.BODY
    background: str = ""
    icon_type: str = ""
    image_zone: bool = False
    list_items: list[str] = Field(default_factory=list)
    emphasis: Emphasis = Emphasis.PRIMARY
    brand_refs: list[str] = Field(default_factory=list)


class PageSpec(BaseModel):
    width: int
    height: int
    orientation: Orientation = Orientation.PORTRAIT
    margin: int = 40
    preset: PagePreset | None = None

    @classmethod
    def from_preset(cls, preset: PagePreset) -> "PageSpec":
        presets = {
            PagePreset.LETTER: (612, 792, Orientation.PORTRAIT),
            PagePreset.A4: (595, 842, Orientation.PORTRAIT),
            PagePreset.WIDE_16_9: (1920, 1080, Orientation.LANDSCAPE),
        }
        w, h, ori = presets[preset]
        return cls(width=w, height=h, orientation=ori, preset=preset)


class DesignSpec(BaseModel):
    version: str = "2.0"
    page_spec: PageSpec
    zones: list[Zone] = Field(default_factory=list)
    brand_tokens: dict = Field(default_factory=dict)
