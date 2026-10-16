"""FlowPilot batch-to-flow translation package.

Public classes are loaded lazily. This keeps lightweight API routes such as
health and intake from importing the full council stack during concurrent app
startup, which previously created a circular import race.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


_PUBLIC_IMPORTS = {
    "ChemistryReasoningAgent": ("flowpilot_translate.chemistry_agent", "ChemistryReasoningAgent"),
    "InputParser": ("flowpilot_translate.input_parser", "InputParser"),
    "EmbeddingEngine": ("flowpilot_translate.embedding_engine", "EmbeddingEngine"),
    "VectorStore": ("flowpilot_translate.vector_store", "VectorStore"),
    "VectorRetriever": ("flowpilot_translate.retriever", "VectorRetriever"),
    "AnalogySelector": ("flowpilot_translate.analogy_selector", "AnalogySelector"),
    "TranslationPromptBuilder": ("flowpilot_translate.prompt_builder", "TranslationPromptBuilder"),
    "TranslationLLM": ("flowpilot_translate.translation_llm", "TranslationLLM"),
    "OutputFormatter": ("flowpilot_translate.output_formatter", "OutputFormatter"),
}

__all__ = list(_PUBLIC_IMPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute = _PUBLIC_IMPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value
