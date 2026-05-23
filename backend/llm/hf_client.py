"""Hugging Face Transformers client for Mistral 7B-Instruct.

This module is **opt-in**: importing it triggers transformers + torch
imports, and the first call downloads ~14 GB of Mistral weights into
`~/.cache/huggingface/`. The default RAGAS judge in
`backend.evaluation.ragas_eval` is the already-running Ollama server,
which is faster on most hardware. Use this module only when you
specifically want HF transformers as the judge (e.g., to match the
"HuggingFace Transformers" claim in the dissertation literally).

Usage:
    from backend.llm.hf_client import HFMistralClient
    llm = HFMistralClient.create()           # loads model on first call
    print(llm.invoke("Hello"))               # LangChain invoke()

The class subclasses `langchain_core.language_models.llms.LLM` so it
plugs straight into `ragas.llms.LangchainLLMWrapper`.

Environment:
    HF_MODEL_ID         (default: mistralai/Mistral-7B-Instruct-v0.2)
    HF_DEVICE           (default: auto — uses cuda if available, else cpu)
    HF_TORCH_DTYPE      (default: float16 on cuda, float32 on cpu)
    HF_MAX_NEW_TOKENS   (default: 512)
    HF_TEMPERATURE      (default: 0.25)
"""

from __future__ import annotations

import os
from typing import Any, ClassVar, List, Optional

try:
    from langchain_core.language_models.llms import LLM
except Exception:
    try:
        from langchain.llms.base import LLM  # type: ignore
    except Exception:
        LLM = None  # type: ignore


HF_MODEL_ID = os.getenv("HF_MODEL_ID", "mistralai/Mistral-7B-Instruct-v0.2")
HF_DEVICE = os.getenv("HF_DEVICE", "auto")
HF_TORCH_DTYPE = os.getenv("HF_TORCH_DTYPE", "")  # empty = auto
HF_MAX_NEW_TOKENS = int(os.getenv("HF_MAX_NEW_TOKENS", "512"))
HF_TEMPERATURE = float(os.getenv("HF_TEMPERATURE", "0.25"))


_PIPELINE = None  # lazy-initialised text-generation pipeline


def _resolve_device(requested: str) -> str:
    if requested != "auto":
        return requested
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _resolve_dtype(requested: str, device: str):
    import torch
    if requested == "float16":
        return torch.float16
    if requested == "float32":
        return torch.float32
    if requested == "bfloat16":
        return torch.bfloat16
    return torch.float16 if device == "cuda" else torch.float32


def _build_pipeline():
    """Load the model, tokenizer and `text-generation` pipeline. Called once
    and cached at module level so a process loads Mistral at most once."""
    global _PIPELINE
    if _PIPELINE is not None:
        return _PIPELINE

    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        pipeline,
    )
    device = _resolve_device(HF_DEVICE)
    dtype = _resolve_dtype(HF_TORCH_DTYPE, device)

    tokenizer = AutoTokenizer.from_pretrained(HF_MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(
        HF_MODEL_ID,
        torch_dtype=dtype,
        device_map="auto" if device == "cuda" else None,
    )
    if device == "cpu":
        model = model.to("cpu")

    _PIPELINE = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        max_new_tokens=HF_MAX_NEW_TOKENS,
        temperature=HF_TEMPERATURE,
        do_sample=HF_TEMPERATURE > 0.0,
        return_full_text=False,
    )
    return _PIPELINE


if LLM is not None:
    class HFMistralClient(LLM):
        """LangChain-compatible Mistral 7B-Instruct judge.

        Pydantic discourages non-serialisable instance attributes, so the
        underlying `text-generation` pipeline lives in a module-level cache
        rather than on the instance. Constructing the class is cheap; the
        actual weights load on the first `_call`.
        """

        model_id: str = HF_MODEL_ID
        max_new_tokens: int = HF_MAX_NEW_TOKENS
        temperature: float = HF_TEMPERATURE

        @property
        def _llm_type(self) -> str:
            return "hf_mistral_finlaw"

        def _call(
            self,
            prompt: str,
            stop: Optional[List[str]] = None,
            run_manager: Any = None,
            **kwargs: Any,
        ) -> str:
            pipe = _build_pipeline()
            kwargs_pipe = {
                "max_new_tokens": self.max_new_tokens,
                "temperature": self.temperature,
                "do_sample": self.temperature > 0.0,
                "return_full_text": False,
            }
            out = pipe(prompt, **kwargs_pipe)
            text = (out[0]["generated_text"] if out else "").strip()
            if stop:
                for s in stop:
                    idx = text.find(s)
                    if idx != -1:
                        text = text[:idx]
            return text

        @classmethod
        def create(cls, **overrides: Any) -> "HFMistralClient":
            """Convenience constructor that returns a configured instance.
            Pre-warms the pipeline if `prewarm=True` is passed."""
            prewarm = bool(overrides.pop("prewarm", False))
            inst = cls(**overrides)
            if prewarm:
                _build_pipeline()
            return inst
else:
    # langchain not installed yet → expose a clear error for callers.
    class HFMistralClient:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError(
                "HFMistralClient requires langchain-core. "
                "Install with `pip install langchain-core langchain-community`."
            )

        @classmethod
        def create(cls, **overrides: Any) -> "HFMistralClient":
            return cls()
