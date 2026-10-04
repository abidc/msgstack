# Decision-Model Routing

Implements the "System One" decision-model pattern — TypeSafe AI's Jev (proprietary,
waitlisted) and its open Apache 2.0 equivalents, Cloudflare **Clef-flash** and Amazon
**Strands Decider 2B** — for jobs that are "pick one of N fixed options" or "rate on a
scale," not prose generation. These models return a choice plus a calibrated confidence
in well under a second; using a full LLM call for a job that was never generation in the
first place is ~200x more expensive and slower than it needs to be.

## Where this applies in MsgStack

- Tier-1 verbatim-violation flagging (`src/pipeline/generator.py::find_tier1_violations`) —
  the word-overlap heuristic's threshold is crude at the margins; borderline scores get a
  second opinion instead of a hard cutoff guess.
- Ingestion-conflict severity classification, competitive-intel extraction confidence, and
  Slack/Teams agent intent/skill routing are the same shape of problem (pick one of a fixed
  set) and are good future candidates as those features land — `decide()` in
  `src/decision_model.py` is written generically for exactly this.

## How it works

`src/decision_model.py` exposes one function:

```python
from src.decision_model import decide

result = decide(
    options=["violation", "not_a_violation"],
    prompt="...",
    context="...",
)
# result.choice, result.confidence, result.source ("decision_model" | "llm_fallback" | "trivial")
```

- If `DECISION_MODEL_URL` is set, `decide()` calls `POST {DECISION_MODEL_URL}/decide` with
  `{"options": [...], "prompt": "...", "context": "..."}` and expects back
  `{"choice": "...", "confidence": 0.0-1.0}` — Clef-flash's native response shape. Swapping
  to Strands Decider or another Apache 2.0 decision model: point the URL at it and confirm
  its response matches this shape (adjust `_decide_via_decision_model` if not).
- If `DECISION_MODEL_URL` is unset, or the endpoint call fails for any reason, `decide()`
  falls back to the existing OpenRouter-routed `llm_client()` with a constrained prompt
  asking it to pick from the same fixed option set. **This means `decide()` always works
  with zero extra infrastructure** — the decision model is a cost/latency optimization on
  top of a path that already functions without it.
- Both paths validate the returned choice is actually a member of the fixed option set
  (case-insensitive exact match; the decision-model path also falls back to the LLM path if
  the model returns something outside the set) and raise `ValueError` rather than silently
  returning something else.

**Important: callers that use `decide()` as an opportunistic refinement (like the Tier-1
borderline check) should only invoke it when `settings.decision_model_url` is actually
configured**, not unconditionally. Falling back to a full LLM call just to refine an
already-reasonable heuristic reintroduces the exact latency/cost problem decision models
exist to avoid, for marginal accuracy gain. Callers where an answer is strictly required
either way (future: Slack/Teams intent routing) should call `decide()` unconditionally and
accept the LLM-fallback cost when no decision model is configured.

## Self-hosting Clef-flash (optional)

Most self-hosters won't have a GPU available on day one, so this is not part of the
default `docker-compose.yml` stack. To run Clef-flash locally:

```yaml
# Add to docker-compose.yml if you have a GPU available:
  decision-model:
    image: cloudflare/clef-flash:latest   # verify current image/tag before use
    container_name: msgstack-decision-model
    restart: unless-stopped
    ports:
      - "9999:9999"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

Then set `DECISION_MODEL_URL=http://decision-model:9999` in `.env`. Without it, everything
in this codebase that calls `decide()` keeps working via the LLM fallback — nothing breaks,
it's just not getting the latency/cost benefit yet.

**This compose snippet is documented here, not added to the live `docker-compose.yml`
directly** — at the time this was written, that file had concurrent in-progress changes
from other work landing in the same repo. Add it once those changes are merged.

## Why not wire this into every classification in the codebase right now

Promoting every "pick one of N" spot in the pipeline to use `decide()` indiscriminately
would scatter a lot of change across files other in-flight work is actively touching. This
pass deliberately wired only the one clear, low-collision case (Tier-1 borderline
refinement in `generator.py`, plus `config.py`'s one new settings field). Ingestion-conflict
severity and competitive-intel extraction confidence are documented above as the next
candidates — pick them up once the features they belong to have landed.
