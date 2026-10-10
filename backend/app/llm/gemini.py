"""
Thin wrapper around Google's Gemini API.

This is the ONLY file in AgentForge that talks to Gemini directly. Every
agent (in later phases) will call methods on GeminiClient instead of
importing google.genai itself. That means if we ever wanted to swap in a
different model provider, this is the one file that would need to change.

Uses the current official Google GenAI Python SDK:
    pip install google-genai
    from google import genai

(NOT the old, deprecated `google-generativeai` package — that one is
retired. Verified against the official SDK's GitHub repo and docs while
building this file.)

Get a free Gemini API key at https://aistudio.google.com/apikey and put it
in your .env file as GEMINI_API_KEY=... (see .env.example).
"""

from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.core.config import Settings, settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Generic type for structured-output responses: generate_structured() is
# given a Pydantic model class and hands back an instance of that class.
ModelT = TypeVar("ModelT", bound=BaseModel)


class GeminiConfigError(Exception):
    """Raised when Gemini can't be used because it isn't configured
    correctly — e.g. no API key set. This is a setup problem, not a
    network/API problem, so we raise it separately."""


class GeminiRequestError(Exception):
    """Raised when a request to the Gemini API itself fails — network
    error, invalid request, rate limit, etc. Wraps the original SDK
    exception so callers get one consistent error type to handle."""


class GeminiClient:
    """
    Small wrapper around google.genai.Client with two methods:

    - generate_text(...)       -> plain string response
    - generate_structured(...) -> a validated Pydantic object

    Agents in later phases will use generate_structured() whenever they
    need reliable, parseable output (e.g. "give me a RootCause"), and
    generate_text() for free-form reasoning or summaries.
    """

    def __init__(self, config: Settings = settings):
        if not config.gemini_api_key:
            # Fail loudly and clearly, right at the point Gemini is first
            # needed — not with a cryptic SDK error later.
            raise GeminiConfigError(
                "GEMINI_API_KEY is not set. Get a free key at "
                "https://aistudio.google.com/apikey and add it to your "
                ".env file (see .env.example)."
            )

        self._model = config.gemini_model
        self._embedding_model = config.gemini_embedding_model
        # The SDK client itself does the actual HTTP calls to Gemini.
        # We never log config.gemini_api_key anywhere in this file.
        self._client = genai.Client(api_key=config.gemini_api_key)

    def generate_text(self, prompt: str, system_instruction: str | None = None) -> str:
        """
        Send a prompt to Gemini and get back plain text.

        system_instruction sets the model's persona/role for this call
        (e.g. "You are a careful software debugging assistant.").
        """
        logger.info("Calling Gemini model=%s for generate_text", self._model)
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                ),
            )
        except Exception as exc:  # the SDK can raise several exception types
            logger.error("Gemini request failed: %s", exc)
            raise GeminiRequestError(f"Gemini generate_text call failed: {exc}") from exc

        if not response.text:
            raise GeminiRequestError(
                "Gemini returned an empty response (it may have been blocked "
                "by safety filters, or the model returned no candidates)."
            )
        return response.text

    def generate_structured(
        self,
        prompt: str,
        response_model: type[ModelT],
        system_instruction: str | None = None,
    ) -> ModelT:
        """
        Send a prompt to Gemini and get back a validated instance of
        `response_model` (a Pydantic BaseModel subclass).

        Example:
            class Triage(BaseModel):
                severity: str
                reasoning: str

            result = client.generate_structured("...", Triage)
            result.severity  # a real, validated Triage instance

        We ask Gemini to return JSON matching the model's schema, then let
        Pydantic parse and validate it. If Gemini returns something that
        doesn't match the schema, this raises a normal Pydantic
        ValidationError so the caller can see exactly what was wrong.
        """
        logger.info(
            "Calling Gemini model=%s for generate_structured (%s)",
            self._model,
            response_model.__name__,
        )
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=response_model,
                ),
            )
        except Exception as exc:
            logger.error("Gemini request failed: %s", exc)
            raise GeminiRequestError(
                f"Gemini generate_structured call failed: {exc}"
            ) from exc

        if not response.text:
            raise GeminiRequestError("Gemini returned an empty response.")

        # response.text is a JSON string; Pydantic validates it against
        # response_model and raises ValidationError if it doesn't match.
        return response_model.model_validate_json(response.text)

    def embed_texts(self, texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
        """
        Turn a list of text strings into embedding vectors (lists of
        floats), one per input text, for the RAG pipeline.

        task_type tells Gemini how the embedding will be used, which
        changes how it's computed: use "RETRIEVAL_DOCUMENT" when embedding
        knowledge-base chunks to store, and "RETRIEVAL_QUERY" when
        embedding a search query at lookup time. Using the right one for
        each side measurably improves retrieval quality.

        We ask for 768-dimensional embeddings (output_dimensionality)
        instead of the model's default 3072 — plenty of quality for a
        learning-project knowledge base, at a quarter of the storage
        cost. See docs/03-rag.md for more on this trade-off.
        """
        if not texts:
            return []

        logger.info(
            "Calling Gemini model=%s for embed_texts (%d texts, task_type=%s)",
            self._embedding_model,
            len(texts),
            task_type,
        )
        try:
            response = self._client.models.embed_content(
                model=self._embedding_model,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=768,
                ),
            )
        except Exception as exc:
            logger.error("Gemini embedding request failed: %s", exc)
            raise GeminiRequestError(f"Gemini embed_texts call failed: {exc}") from exc

        if not response.embeddings:
            raise GeminiRequestError("Gemini returned no embeddings.")

        return [embedding.values for embedding in response.embeddings]
