"""Artifact renderer abstraction — render generated content to different output formats."""

from abc import ABC, abstractmethod
from typing import Optional
from pathlib import Path
import json


class RenderOutput:
    """Structured output from a renderer."""

    def __init__(
        self,
        output_type: str,
        content: str | dict,
        metadata: Optional[dict] = None,
    ):
        self.output_type = output_type  # "html", "fabric_json", "reveal_html", "penpot"
        self.content = content
        self.metadata = metadata or {}


class ArtifactRenderer(ABC):
    """Base class for all artifact renderers."""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    @abstractmethod
    def render_html(self, sections: dict, context: dict) -> RenderOutput:
        """Render artifact to HTML string."""
        pass

    @abstractmethod
    def render_fabric(self, sections: dict, context: dict) -> RenderOutput:
        """Render artifact to Fabric.js canvas JSON."""
        pass

    @abstractmethod
    def render_reveal(self, sections: dict, context: dict) -> RenderOutput:
        """Render artifact to reveal.js HTML."""
        pass

    @abstractmethod
    def render_penpot(self, sections: dict, context: dict) -> RenderOutput:
        """Render artifact to Penpot API calls / data structure."""
        pass


class HTMLRenderer(ArtifactRenderer):
    """Renders artifacts to HTML via Jinja2 templates."""

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        try:
            from jinja2 import Environment, BaseLoader
            self.env = Environment(loader=BaseLoader(), autoescape=False)
        except ImportError:
            self.env = None

    def render_html(self, sections: dict, context: dict) -> RenderOutput:
        house_name = context.get("house_name", "Untitled")
        html = self._build_html(sections, house_name)
        return RenderOutput(output_type="html", content=html)

    def render_fabric(self, sections: dict, context: dict) -> RenderOutput:
        return RenderOutput(
            output_type="fabric_json",
            content={"error": "HTMLRenderer does not support Fabric output"},
        )

    def render_reveal(self, sections: dict, context: dict) -> RenderOutput:
        return RenderOutput(
            output_type="reveal_html",
            content={"error": "HTMLRenderer does not support Reveal.js output"},
        )

    def render_penpot(self, sections: dict, context: dict) -> RenderOutput:
        return RenderOutput(
            output_type="penpot",
            content={"error": "HTMLRenderer does not support Penpot output"},
        )

    def _build_html(self, sections: dict, house_name: str) -> str:
        lines = [f"<html><head><title>{house_name}</title></head><body>"]
        lines.append(f"<h1>{house_name}</h1>")
        for key, value in sections.items():
            if value:
                lines.append(f"<h2>{key.replace('_', ' ').title()}</h2>")
                lines.append(f"<div>{value}</div>")
        lines.append("</body></html>")
        return "\n".join(lines)


class FabricRenderer(ArtifactRenderer):
    """Renders artifacts to Fabric.js canvas JSON."""

    def render_html(self, sections: dict, context: dict) -> RenderOutput:
        return RenderOutput(
            output_type="html",
            content="<p>FabricRenderer does not support HTML output</p>",
        )

    def render_fabric(self, sections: dict, context: dict) -> RenderOutput:
        canvas = self._build_fabric_json(sections, context)
        return RenderOutput(output_type="fabric_json", content=canvas)

    def render_reveal(self, sections: dict, context: dict) -> RenderOutput:
        return RenderOutput(
            output_type="reveal_html",
            content={"error": "FabricRenderer does not support Reveal.js output"},
        )

    def render_penpot(self, sections: dict, context: dict) -> RenderOutput:
        return RenderOutput(
            output_type="penpot",
            content={"error": "FabricRenderer does not support Penpot output"},
        )

    def _build_fabric_json(self, sections: dict, context: dict) -> dict:
        if "design_spec" in sections and sections["design_spec"]:
            spec = sections["design_spec"]
            import json
            return json.loads(spec) if isinstance(spec, str) else spec

        objects = []
        y_offset = 50
        house_name = context.get("house_name", "Untitled")

        # Title
        objects.append({
            "type": "text",
            "left": 50,
            "top": y_offset,
            "text": house_name,
            "fontSize": 32,
            "fontWeight": "bold",
            "fill": "#000000",
        })
        y_offset += 60

        # Sections
        for key, value in sections.items():
            if not value:
                continue
            label = key.replace("_", " ").title()
            objects.append({
                "type": "text",
                "left": 50,
                "top": y_offset,
                "text": label,
                "fontSize": 18,
                "fontWeight": "bold",
                "fill": "#333333",
            })
            y_offset += 30
            
            value_str = str(value)
            objects.append({
                "type": "text",
                "left": 70,
                "top": y_offset,
                "text": value_str[:500],
                "fontSize": 14,
                "fill": "#555555",
                "width": 700,
            })
            y_offset += 80

        return {
            "version": "5.3.0",
            "objects": objects,
            "background": "#ffffff",
        }


class RevealRenderer(ArtifactRenderer):
    """Renders artifacts to reveal.js HTML for presentations."""

    def render_html(self, sections: dict, context: dict) -> RenderOutput:
        return RenderOutput(
            output_type="html",
            content="<p>RevealRenderer does not support generic HTML output</p>",
        )

    def render_fabric(self, sections: dict, context: dict) -> RenderOutput:
        return RenderOutput(
            output_type="fabric_json",
            content={"error": "RevealRenderer does not support Fabric output"},
        )

    def render_reveal(self, sections: dict, context: dict) -> RenderOutput:
        html = self._build_reveal_html(sections, context)
        return RenderOutput(output_type="reveal_html", content=html)

    def render_penpot(self, sections: dict, context: dict) -> RenderOutput:
        return RenderOutput(
            output_type="penpot",
            content={"error": "RevealRenderer does not support Penpot output"},
        )

    def _build_reveal_html(self, sections: dict, context: dict) -> str:
        house_name = context.get("house_name", "Untitled")
        
        # Load brand settings if available (these are usually passed via context or fetched client-side)
        brand = context.get("brand_settings", {})
        primary_color = brand.get("primary_color", "#1a56db")
        secondary_color = brand.get("secondary_color", "#7e3af2")
        text_color = brand.get("text_color", "#111827")
        bg_color = brand.get("background_color", "#ffffff")
        font_heading = brand.get("font_heading", "Inter")
        font_body = brand.get("font_body", "Inter")
        
        slides = []
        design_spec = sections.get("design_spec", {})
        
        if "slides" in design_spec:
            for slide in design_spec["slides"]:
                slide_type = slide.get("type", "standard")
                title = slide.get("title", "")
                content = slide.get("content", "")
                notes = slide.get("notes", "")
                
                notes_html = f"<aside class='notes'>{notes}</aside>" if notes else ""
                
                if slide_type == "title":
                    slides.append(
                        f"<section data-background-color='{primary_color}'>"
                        f"<h1 style='color: white;'>{title}</h1>"
                        f"<h3 style='color: rgba(255,255,255,0.8);'>{content}</h3>"
                        f"{notes_html}</section>"
                    )
                elif slide_type == "split":
                    left = slide.get("left_content", "")
                    right = slide.get("right_content", "")
                    slides.append(
                        f"<section>"
                        f"<h2>{title}</h2>"
                        f"<div style='display: flex; gap: 40px; margin-top: 40px;'>"
                        f"<div style='flex: 1; text-align: left;'>{left}</div>"
                        f"<div style='flex: 1; text-align: left;'>{right}</div>"
                        f"</div>{notes_html}</section>"
                    )
                else:
                    slides.append(
                        f"<section>"
                        f"<h2>{title}</h2>"
                        f"<div style='text-align: left; margin-top: 40px;'>{content}</div>"
                        f"{notes_html}</section>"
                    )
        else:
            # Fallback for simple sections
            slides.append(f"<section><h1>{house_name}</h1></section>")
            for key, value in sections.items():
                if key == "design_spec" or not value or not isinstance(value, str):
                    continue
                label = key.replace("_", " ").title()
                slides.append(f"<section><h2>{label}</h2><div style='text-align: left;'>{value}</div></section>")

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{house_name}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@4.5.0/dist/reset.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@4.5.0/dist/reveal.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@4.5.0/dist/theme/simple.css">
    <style>
        :root {{
            --r-main-font: '{font_body}', sans-serif;
            --r-heading-font: '{font_heading}', sans-serif;
            --r-main-color: {text_color};
            --r-heading-color: {text_color};
            --r-background-color: {bg_color};
            --r-link-color: {primary_color};
            --r-link-color-hover: {secondary_color};
        }}
        .reveal h1, .reveal h2, .reveal h3, .reveal h4, .reveal h5, .reveal h6 {{
            text-transform: none;
            font-weight: 700;
        }}
        .reveal ul {{
            display: block;
            margin-left: 1em;
        }}
        .reveal li {{
            margin-bottom: 0.5em;
        }}
    </style>
</head>
<body>
    <div class="reveal">
        <div class="slides">
            {"".join(slides)}
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/reveal.js@4.5.0/dist/reveal.js"></script>
    <script>
        Reveal.initialize({{
            hash: true,
            slideNumber: 'c/t',
            transition: 'slide',
            controls: true,
            progress: true,
            center: true
        }});
    </script>
</body>
</html>"""
        return html


class PenpotRenderer(ArtifactRenderer):
    """Renders artifacts to Penpot API-compatible data structures."""

    def render_html(self, sections: dict, context: dict) -> RenderOutput:
        return RenderOutput(
            output_type="html",
            content="<p>PenpotRenderer does not support HTML output</p>",
        )

    def render_fabric(self, sections: dict, context: dict) -> RenderOutput:
        return RenderOutput(
            output_type="fabric_json",
            content={"error": "PenpotRenderer does not support Fabric output"},
        )

    def render_reveal(self, sections: dict, context: dict) -> RenderOutput:
        return RenderOutput(
            output_type="reveal_html",
            content={"error": "PenpotRenderer does not support Reveal.js output"},
        )

    def render_penpot(self, sections: dict, context: dict) -> RenderOutput:
        penpot_data = self._build_penpot_data(sections, context)
        return RenderOutput(output_type="penpot", content=penpot_data)

    def _build_penpot_data(self, sections: dict, context: dict) -> dict:
        house_name = context.get("house_name", "Untitled")
        objects = []

        # Build Penpot-compatible shape objects
        y_offset = 50
        objects.append({
            "type": "text",
            "name": "Title",
            "x": 50,
            "y": y_offset,
            "width": 700,
            "height": 50,
            "content": house_name,
            "fontSize": 32,
            "fontWeight": "bold",
            "fillColor": "#000000",
        })
        y_offset += 80

        for key, value in sections.items():
            if not value:
                continue
            label = key.replace("_", " ").title()
            objects.append({
                "type": "text",
                "name": label,
                "x": 50,
                "y": y_offset,
                "width": 700,
                "height": 30,
                "content": label,
                "fontSize": 18,
                "fontWeight": "bold",
                "fillColor": "#333333",
            })
            y_offset += 40
            objects.append({
                "type": "text",
                "name": f"{label} Content",
                "x": 70,
                "y": y_offset,
                "width": 680,
                "height": 60,
                "content": value[:500],
                "fontSize": 14,
                "fillColor": "#555555",
            })
            y_offset += 100

        return {
            "file_name": f"{house_name} - Generated Artifact",
            "objects": objects,
        }


def get_renderer(renderer_type: str, config: Optional[dict] = None) -> ArtifactRenderer:
    """Factory function to get the appropriate renderer.

    Args:
        renderer_type: One of "html", "fabric", "reveal", "penpot"
        config: Optional configuration dict for the renderer

    Returns:
        An instance of the appropriate ArtifactRenderer subclass
    """
    renderers = {
        "html": HTMLRenderer,
        "fabric": FabricRenderer,
        "reveal": RevealRenderer,
        "penpot": PenpotRenderer,
    }

    renderer_class = renderers.get(renderer_type.lower())
    if not renderer_class:
        raise ValueError(
            f"Unknown renderer type: {renderer_type}. "
            f"Valid types: {list(renderers.keys())}"
        )

    return renderer_class(config)
