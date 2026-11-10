"""Model providers for the CSV upload assistant.

Every provider answers one question: "given this prompt, return JSON matching
this pydantic schema". Callers only ever see validated objects or None.

Two providers are supported and chained: Gemini is tried first when its key
is configured, and Anthropic takes over when Gemini is not configured, its
key is rejected, or a call fails. With no key at all the assistant is
disabled and the upload flow runs without it.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_ANTHROPIC_MODEL = "claude-opus-5-5"

T = TypeVar("T", bound=BaseModel)


class AiClient(Protocol):
    name: str
    enabled: bool

    def generate(self, prompt: str, schema: type[T]) -> T | None: ...


class DisabledClient:
    """Used when no provider key is set."""

    name = "disabled"
    enabled = False

    def generate(self, prompt: str, schema: type[T]) -> T | None:
        return None


class GeminiClient:
    name = "gemini"

    def __init__(self, api_key: str, model: str = DEFAULT_GEMINI_MODEL) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self.model = model
        self.enabled = True

    def generate(self, prompt: str, schema: type[T]) -> T | None:
        from google.genai import errors, types

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
        except errors.APIError as error:
            # A rejected key will not fix itself: stop asking Gemini for the
            # rest of the process so the chain goes straight to the fallback.
            if error.code in (401, 403) or "API_KEY_INVALID" in str(error):
                log.warning("Gemini rejected the API key; disabling provider: %s", error)
                self.enabled = False
            else:
                log.warning("Gemini call failed (%s): %s", error.code, error)
        except Exception as error:  # network and anything unexpected
            log.warning("Gemini call failed: %s", error)
        return None


class AnthropicClient:
    name = "anthropic"

    def __init__(self, api_key: str, model: str = DEFAULT_ANTHROPIC_MODEL) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.enabled = True

    def generate(self, prompt: str, schema: type[T]) -> T | None:
        import anthropic

        try:
            response = self._client.beta.messages.parse(
                model=self.model,
                max_tokens=8192,
                # Server-side refusal fallback: if a safety classifier declines,
                # the API re-runs the request on a fallback model in the same call.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": prompt}],
                output_format=schema,
            )
            if response.stop_reason == "refusal":
                log.warning("Anthropic declined the request (%s)", response.stop_details)
                return None
            return response.parsed_output
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as error:
            log.warning("Anthropic rejected the API key; disabling provider: %s", error)
            self.enabled = False
        except anthropic.RateLimitError as error:
            log.warning("Anthropic rate limited: %s", error)
        except anthropic.APIStatusError as error:
            log.warning("Anthropic call failed (%s): %s", error.status_code, error.message)
        except anthropic.APIConnectionError as error:
            log.warning("Anthropic unreachable: %s", error)
        except ValidationError as error:
            log.warning("Anthropic returned JSON that did not match %s: %s", schema.__name__, error)
        return None


class FallbackClient:
    """Tries each enabled provider in order; the first answer wins."""

    name = "fallback"

    def __init__(self, providers: list[AiClient]) -> None:
        self.providers = providers
        self.last_provider: str | None = None

    @property
    def enabled(self) -> bool:
        return any(provider.enabled for provider in self.providers)

    def generate(self, prompt: str, schema: type[T]) -> T | None:
        self.last_provider = None
        for provider in self.providers:
            if not provider.enabled:
                continue
            result = provider.generate(prompt, schema)
            if result is not None:
                self.last_provider = provider.name
                return result
            log.info("%s gave no answer; trying the next provider", provider.name)
        return None


@lru_cache(maxsize=1)
def get_ai_client() -> AiClient:
    providers: list[AiClient] = []
    if gemini_key := os.environ.get("GEMINI_API_KEY"):
        providers.append(GeminiClient(gemini_key, os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)))
    if anthropic_key := os.environ.get("ANTHROPIC_API_KEY"):
        providers.append(
            AnthropicClient(anthropic_key, os.environ.get("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL))
        )
    if not providers:
        log.info("No GEMINI_API_KEY or ANTHROPIC_API_KEY set; upload assistant disabled")
        return DisabledClient()
    log.info("Upload assistant providers: %s", ", ".join(p.name for p in providers))
    return FallbackClient(providers)
