# MsgStack Brand & Style Guide

**Authoritative grounding infrastructure for AI assistants.**

## 1. Brand Identity & Vibe
MsgStack is the bridge between organizational strategy and precise AI engineering. It represents structure, intelligence, and a "single source of truth."

*   **Vibe:** Technical, intelligent, structured, precise, and premium.
*   **Aesthetic:** Dark-mode first, sleek, developer-friendly but marketing-savvy. It should feel like a high-end command center or a data intelligence hub.
*   **Keywords:** Structured, Grounded, Deterministic, Stacked, Connected, Authoritative.

---

## 2. Logo Concept
**Concept:** A stack of interconnected layers or blocks that transform into a glowing graph network (representing the "Stack" and the "Knowledge Graph"). 
*   **Symbol:** Three geometric isometric planes stacked vertically. The top plane reveals glowing nodes connected by lines, signifying the knowledge graph and semantic extraction.
*   **Logotype:** Clean, geometric sans-serif (e.g., *Outfit* or *Inter*). The word "Msg" in a slightly lighter weight than "Stack".

---

## 3. Color Palette

MsgStack uses a deep, dark-themed canvas punctuated by vibrant "intelligent" accent colors representing the vector and graph operations.

*   **Backgrounds & Canvas:**
    *   **Deep Midnight / Void:** `#0B0F19` (Primary background)
    *   **Surface Dark:** `#1A2235` (Cards, panels, modal backgrounds)
    *   **Surface Light (Borders/Lines):** `#2A3655` (Subtle dividers, structural borders)

*   **Primary Accents (The Intelligence layer):**
    *   **Vector Cyan:** `#00E5FF` (Primary calls to action, active states, vector search visualization)
    *   **Graph Indigo:** `#651FFF` (Deterministic graph paths, AI generation highlights)
    *   **Electric Purple:** `#B388FF` (Hover states, gradients, secondary highlights)

*   **Typography Colors:**
    *   **Primary Text:** `#F8FAFC` (Pure white with a touch of blue)
    *   **Secondary Text:** `#94A3B8` (Muted slate for descriptions and metadata)
    *   **Code / Monospace text:** `#38BDF8` (Light sky blue for tags, JSON keys, technical data)

*   **Gradients:**
    *   *Intelligence Gradient:* Linear gradient from `#00E5FF` to `#651FFF`. Used sparingly for premium components, active borders, or the logo symbol.

---

## 4. Typography

We prioritize modern, highly legible sans-serif fonts that look exceptional on high-density displays.

*   **Headings (H1, H2, H3):** **Outfit** (Google Fonts)
    *   *Usage:* Display text, marketing headlines, dashboard section titles. Geometric and modern.
    *   *Weights:* SemiBold (600), Bold (700).

*   **Body Text (Paragraphs, UI text):** **Inter** (Google Fonts)
    *   *Usage:* Main UI text, descriptions, long-form reading (like inside generated artifacts). Extremely readable.
    *   *Weights:* Regular (400), Medium (500).

*   **Technical / Code Data:** **JetBrains Mono** or **Roboto Mono**
    *   *Usage:* JSON outputs, tag names, MCP tool names, UUIDs.
    *   *Weights:* Regular (400).

---

## 5. Web Design Principles

When building the Admin UI or external-facing marketing sites, adhere to these principles:

1.  **Dark Theme First:** The default and primary experience is dark. It reduces eye strain for long sessions and makes the neon accent colors "pop" like a command center.
2.  **Glassmorphism & Depth:** Use subtle translucent backgrounds (`rgba(26, 34, 53, 0.7)`) with background blur (`backdrop-filter: blur(12px)`) for floating elements, dropdowns, and sticky headers to create a sense of depth and layering.
3.  **Micro-Interactions:** Buttons and graph nodes should have smooth, quick transitions (e.g., `transition: all 0.2s ease`). Hovering over a message block should slightly elevate it and illuminate its border with the *Intelligence Gradient*.
4.  **Structured Layouts:** Use prominent CSS Grid and Flexbox structures. Everything should feel rigidly aligned, representing the "structured data" nature of the application.
5.  **Visual Grounding:** When showing connections between a "Canon Domain" and a generated "Artifact", use visual splines or Cytoscape.js networks to literally *show* the grounding process.
6.  **Minimalist Inputs:** Form inputs (for uploading PDFs or editing messages) should be borderless or have very subtle bottom borders, expanding or glowing only on focus.

---

## 6. Tone of Voice (Marketing & UI Copy)

*   **Direct & Confident:** Avoid fluff. Say "Extract positioning" instead of "Let our AI try to find your positioning."
*   **Technical but Accessible:** Use proper terminology (Vector, Graph, MCP, Grounding) but explain their value immediately.
*   **Empowering:** The messaging should make the user feel like they have a superpower (controlling rogue AI with structured truth).
