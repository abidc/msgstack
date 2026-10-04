"""Decision-model routing for fixed-option choices.

Implements the "System One" decision-model pattern (TypeSafe AI's Jev;
open-weight Apache 2.0 equivalents Cloudflare Clef-flash and Amazon Strands
Decider 2B) for jobs that are "pick one of N options" or "rate on a scale,"
not prose generation — these models return a choice plus a calibrated
confidence in well under a second, far cheaper than a full LLM call for a
job that was never generation in the first place.

This module has no hard dependency on a decision-model endpoint actually
running: most self-hosters won't have the (optional, GPU-bound) service from
docker-compose.yml's `decision-model` profile up on day one. When
DECISION_MODEL_URL is unset, or the endpoint call fails, `decide()` falls
back to the existing OpenRouter-routed `llm_client()` with a constrained
prompt that asks it to pick from the same fixed option set. Call sites don't
need to know which path served the request — only `DecisionResult.source`
tells you, for logging/metrics.
"""

import json
import logging
from dataclasses import dataclass

import requests

from src.config import llm_client, llm_model, settings

log = logging.getLogger(__name__)

DECISION_MODEL_TIMEOUT_S = 5.0


@dataclass
class DecisionResult:
    choice: str
    confidence: float
    source: str  # "decision_model" | "llm_fallback"


def decide(options: list[str], prompt: str, context: str = "") -> DecisionResult:
    """Pick one of `options` for `prompt`, with a calibrated confidence.

    `options` must be the exact fixed set of valid choices — both paths
    validate the returned choice is a member of that set (or recoverable to
    one) and raise ValueError rather than silently returning something else.
    """
    if not options:
        raise ValueError("decide() requires a non-empty options list")
    if len(options) == 1:
        return DecisionResult(choice=options[0], confidence=1.0, source="trivial")

    if settings.decision_model_url:
        try:
            return _decide_via_decision_model(options, prompt, context)
        except Exception:
            log.warning(
                "Decision-model endpoint at %s failed, falling back to LLM",
                settings.decision_model_url,
                exc_info=True,
            )

    return _decide_via_llm_fallback(options, prompt, context)


def _decide_via_decision_model(options: list[str], prompt: str, context: str) -> DecisionResult:
    """Call a Clef-flash-compatible decision-model endpoint.

    Swapping to Strands Decider or another Apache 2.0 decision model: point
    DECISION_MODEL_URL at it and confirm its `/decide` response shape matches
    {"choice": str, "confidence": float} — adjust the parsing below if not.
    """
    resp = requests.post(
        f"{settings.decision_model_url}/decide",
        json={"options": options, "prompt": prompt, "context": context},
        timeout=DECISION_MODEL_TIMEOUT_S,
    )
    resp.raise_for_status()
    data = resp.json()
    choice = _resolve_choice(data.get("choice"), options)
    if choice is None:
        raise ValueError(f"decision model returned an option outside the fixed set: {data.get('choice')!r}")
    return DecisionResult(choice=choice, confidence=float(data.get("confidence", 1.0)), source="decision_model")


def _decide_via_llm_fallback(options: list[str], prompt: str, context: str) -> DecisionResult:
    """Ask the configured LLM (via the existing OpenRouter routing) to pick one option.

    Not the fast path this module exists to avoid for high-volume routing —
    it's the always-available fallback so decide() works with zero extra
    infrastructure, at ordinary LLM-call cost and latency instead of
    decision-model cost and latency.
    """
    options_block = "\n".join(f"- {o}" for o in options)
    context_line = f"Context: {context}\n\n" if context else ""
    full_prompt = (
        f"{prompt}\n\n{context_line}"
        "Choose exactly one of the following options. Respond with ONLY a JSON object, "
        'no other text: {"choice": "<one of the options, verbatim>", "confidence": <0.0-1.0>}\n\n'
        f"Options:\n{options_block}"
    )
    client = llm_client()
    resp = client.chat.completions.create(
        model=llm_model("gpt-4o-mini"),
        messages=[{"role": "user", "content": full_prompt}],
        temperature=0,
        max_tokens=150,
    )
    raw = (resp.choices[0].message.content or "").strip()
    choice, confidence = _parse_fallback_response(raw, options)
    if choice is None:
        raise ValueError(f"LLM fallback produced no option from the fixed set: {raw!r}")
    return DecisionResult(choice=choice, confidence=confidence, source="llm_fallback")


def _parse_fallback_response(raw: str, options: list[str]) -> tuple[str | None, float]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        data = json.loads(cleaned)
        choice = _resolve_choice(data.get("choice"), options)
        if choice is not None:
            return choice, float(data.get("confidence", 0.7))
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
        pass
    # Best-effort recovery: the model answered in plain text instead of JSON.
    for option in options:
        if option.lower() in raw.lower():
            return option, 0.5
    return None, 0.0


def _resolve_choice(raw_choice, options: list[str]) -> str | None:
    """Map a possibly-inexact returned choice back to the exact option string, or None."""
    if raw_choice is None:
        return None
    if raw_choice in options:
        return raw_choice
    raw_lower = str(raw_choice).strip().lower()
    for option in options:
        if option.lower() == raw_lower:
            return option
    return None
