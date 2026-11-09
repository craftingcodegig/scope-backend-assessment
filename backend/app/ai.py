"""Thin wrapper around the Gemini API used by the CSV upload assistant.

Every call asks for JSON that matches a pydantic schema, so callers only ever
see validated objects. When no API key is configured, or a call fails, the
client returns None and the upload flow continues without AI help.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.5-flash"

T = TypeVar("T", bound=BaseModel)


class AiClient(Protocol):
    enabled: bool

    def generate(self, prompt: str, schema: type[T]) -> T | None: ...


class DisabledClient:
    """Used when GEMINI_API_KEY is not set."""

    enabled = False

    def generate(self, prompt: str, schema: type[T]) -> T | None:
        return None


class GeminiClient:
    enabled = True

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self.model = model

    def generate(self, prompt: str, schema: type[T]) -> T | None:
        from google.genai import types

        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0,
                ),
            )
            return schema.model_validate_json(response.text or "")
        except ValidationError as error:
            log.warning("Gemini returned JSON that did not match %s: %s", schema.__name__, error)
        except Exception as error:  # network, quota, safety blocks
            log.warning("Gemini call failed: %s", error)
        return None


@lru_cache(maxsize=1)
def get_ai_client() -> AiClient:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log.info("GEMINI_API_KEY not set; upload assistant disabled")
        return DisabledClient()
    return GeminiClient(api_key, os.environ.get("GEMINI_MODEL", DEFAULT_MODEL))
