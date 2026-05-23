"""Ollama HTTP client — streams tokens from a locally-running Ollama server.

Supports per-request overrides for `num_predict`, `temperature`, `num_ctx`,
plus mirostat / top-p / top-k options. Multi-model is dropped at the
application level (front-end no longer exposes a chooser) but the client
still accepts a `model_id` override; when `None`, `OLLAMA_MODEL` (default
`mistral:7b-instruct`) is used.

Environment:
    OLLAMA_BASE_URL  (default: http://127.0.0.1:11434)
    OLLAMA_MODEL     (default: mistral:7b-instruct)
    OLLAMA_TIMEOUT   (default: 300)
    OLLAMA_NUM_PREDICT (default: 640)
    OLLAMA_TEMPERATURE (default: 0.25)
    OLLAMA_NUM_CTX     (default: 8192)
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import requests

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "mistral:7b-instruct")
TIMEOUT_S = int(os.getenv("OLLAMA_TIMEOUT", "300"))

GEN_OPTIONS = {
    "num_predict": int(os.getenv("OLLAMA_NUM_PREDICT", "640")),
    "temperature": float(os.getenv("OLLAMA_TEMPERATURE", "0.25")),
    "num_ctx": int(os.getenv("OLLAMA_NUM_CTX", "8192")),
}


def _tags():
    url = f"{OLLAMA_BASE}/api/tags"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return [m.get("name") for m in r.json().get("models", []) if m.get("name")]


def ensure_model_ready(model_id: Optional[str]) -> str:
    model = model_id or DEFAULT_MODEL
    try:
        names = _tags()
    except requests.RequestException as e:
        raise RuntimeError(
            f"Ollama not reachable at {OLLAMA_BASE}: {e}. "
            "Start Ollama and pull at least one model."
        )
    if model not in names:
        raise RuntimeError(
            f"Model '{model}' is not installed. Installed: {', '.join(names) or '(none)'}.\n"
            "Run:  ollama pull mistral:7b-instruct   (or pull the selected model)"
        )
    return model


def _merge_options(overrides: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    opts = dict(GEN_OPTIONS)
    if not overrides:
        return opts
    for k in (
        "num_predict",
        "temperature",
        "num_ctx",
        "top_p",
        "top_k",
        "mirostat",
        "mirostat_eta",
        "mirostat_tau",
    ):
        if k in overrides and overrides[k] is not None:
            opts[k] = overrides[k]
    if "num_predict" in opts:
        opts["num_predict"] = int(opts["num_predict"])
    if "num_ctx" in opts:
        opts["num_ctx"] = int(opts["num_ctx"])
    if "temperature" in opts:
        opts["temperature"] = float(opts["temperature"])
    return opts


def generate_stream(messages, model_id=None, options: Optional[Dict[str, Any]] = None):
    """Yield assistant tokens as they arrive.

    `options` may include: num_predict, temperature, num_ctx, top_p, top_k, mirostat, ...
    """
    model = ensure_model_ready(model_id)
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": _merge_options(options),
    }
    url = f"{OLLAMA_BASE}/api/chat"
    try:
        with requests.post(url, json=payload, stream=True, timeout=TIMEOUT_S) as resp:
            resp.raise_for_status()
            got_any = False
            for raw in resp.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                chunk = json.loads(raw)
                msg = chunk.get("message", {})
                content = msg.get("content", "")
                if content:
                    got_any = True
                    yield content
                if chunk.get("done"):
                    break
            if not got_any:
                raise RuntimeError(
                    "The model connection returned no tokens. Try again or reduce load."
                )
    except requests.RequestException as e:
        raise RuntimeError(
            f"Ollama chat failed for model '{model}': {e}. "
            f"Is Ollama running at {OLLAMA_BASE}? Is the model pulled?"
        )
