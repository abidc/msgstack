# Contributing to MsgStack

Thanks for your interest in contributing! MsgStack is an open source project and contributions of all kinds are welcome.

---

## Ways to contribute

- 🐛 **Bug reports** — open an issue using the bug report template
- ✨ **Feature requests** — open an issue using the feature request template
- 📖 **Documentation** — typos, clarity improvements, missing examples
- 🔧 **Code PRs** — bug fixes, new skills, source connectors, MCP client integrations
- 🎨 **Skill templates** — new artifact types in `data/skills/` (no Python required)

---

## Development setup

```bash
git clone https://github.com/abidc/msgstack-mcp.git
cd msgstack-mcp

# Create virtualenv
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Add OPENAI_API_KEY (required)
# TURBOVEC_INDEX_PATH is optional — defaults to data/msgstack_vectors.tvim (no external service needed)

# Seed sample data
python -c "from seed_data.seed import seed; seed()"

# Start the server
python run_server.py
# Admin UI: http://localhost:8001/
# MCP:      http://localhost:8001/mcp
```

---

## Code style

We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting.

```bash
# Lint
ruff check src/

# Format
ruff format src/
```

Please run ruff before submitting a PR. CI will fail on lint errors.

---

## Adding a skill template

Skill templates are JSON files in `data/skills/`. You can add a new artifact type without writing any Python.

Each skill file defines:
```json
{
  "id": "my_skill",
  "name": "My Artifact Type",
  "description": "What this generates",
  "system_prompt": "You are a marketing writer...",
  "user_prompt": "Given this grounding context:\n\n{grounding_context}\n\nWrite a...",
  "output_sections": ["section_1", "section_2"],
  "channels": ["email", "linkedin"]
}
```

See the existing skill files in `data/skills/` for examples.

---

## PR process

1. **Fork** the repo and create a branch: `git checkout -b feat/my-feature`
2. **Write tests** for new behavior where reasonable (`tests/` directory)
3. **Run lint** before pushing: `ruff check src/`
4. **Open a PR** against `main` with a clear title and description
5. A maintainer will review within a few days

---

## What we're NOT accepting (scope guard)

To keep MsgStack focused:
- Full CMS or content calendar features
- Social media scheduling
- CRM replacement features
- Design tool replacement (Figma competitor)

For context on scope, see the [ROADMAP.md "What We're Not Building"](ROADMAP.md#what-were-not-building) section.

---

## Questions?

Open a [GitHub Discussion](https://github.com/abidc/msgstack-mcp/discussions) for anything that's not a bug report or feature request.
