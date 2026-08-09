# MsgStack Brand & Style Guide — "ATLAS" (v5)

**Ink on paper.** The star atlas as a printed object: warm paper canvas, ink text,
serif statements, one muted atlas-blue accent. The cosmic (indigo skies,
constellations, the ember star) lives in the *photography* — the UI never
imitates the night sky.

The canonical source of truth for this design system is the Claude Design
project **MsgStack Rebrand**, synced locally to
`msgstack-website/design-system/` (tokens, foundations, components, sections).
This document is a summary for contributors working in this repo.

---

## Core rules

1. **The UI is a printed page** — paper, ink, and one printed-ink blue. Indigo
   skies appear only inside photographs and their plates. The dark theme is the
   "night chapter": soft ink-indigo, never neon.
2. **Ember orange marks LOCKED / verified only.** Nothing else is ember.
3. **Serif for statements and stat numerals; sans for UI and body; mono for
   stamps and records.** Statements are sentence case — never uppercase.
4. **The ✦ four-point star** is the brand mark: wordmark (`MsgStack ✦`), index
   rules, LOCKED badges, atlas stamps (`SPEC № 441-B ✦`).
5. **Anti-slop constraints:** no gradients on UI surfaces, no glassmorphism,
   no glow, no neon accents, no purple.

## Palette

| Token | Paper (light) | Night (dark) |
|-------|--------------|--------------|
| Canvas | `#F6F3EA` | `#191825` |
| Raised surface | `#EFEADD` | `#232231` |
| Pressed | `#E5DECB` | `#2C2B3D` |
| Hairline | `#DAD2BE` | `#383650` |
| Text | `#23201A` warm ink | `#EFEBE0` warm paper-white |
| Secondary text | `#5F594A` | `#ADA89E` |
| Accent (the only working color) | `#3E4E80` atlas ink-blue | `#8A97C0` atlas-soft |
| LOCKED / verified only | `#C05A1E` ember-deep | `#E8763A` ember |

Functional status colors stay muted and inky: moss `#56673F` (success),
ochre `#8A6A1F` (warn), brick `#9E3B2E` (danger).

## Type

| Role | Face |
|------|------|
| Wordmark only | Lora 700 — `MsgStack ✦` |
| Display / statements / stat numerals | Newsreader 500/600 serif, sentence case |
| Body / UI | Instrument Sans 400/600 |
| Stamps, records, index numbers | Martian Mono 400 · ~10px · 0.14em tracking · uppercase |

## In this repo

The admin UI implements ATLAS via the CSS token layer in
`src/web/base.html` (`:root` = paper, `[data-theme="dark"]` = night). The
badge grammar (`.badge-locked`, `.badge-active`, `.badge-draft`, `.stamp`)
lives there too — use those classes rather than inventing inline colors.
`BrandSettings` defaults in `src/models.py` carry ATLAS values so generated
visual artifacts inherit the brand when a workspace has no custom brand.
