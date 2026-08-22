"""LLM Provider abstraction and multi-provider factory for Ask Your Data."""

import os
from abc import ABC, abstractmethod
from typing import Any, Optional, Type, TypeVar
from pydantic import BaseModel
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

T = TypeVar("T", bound=BaseModel)


class BaseLLMProvider(ABC):
    """Abstract interface for LLM Providers (DeepSeek, OpenAI, Local/Ollama, Mock)."""

    provider_name: str = "generic"

    @abstractmethod
    def get_chat_model(self, temperature: float = 0.0) -> BaseChatModel:
        """Return the configured LangChain chat model."""
        pass

    def with_structured_output(self, schema: Type[T], temperature: float = 0.0):
        """Return a runnable with structured output adhering to the Pydantic schema."""
        model = self.get_chat_model(temperature=temperature)
        return model.with_structured_output(schema)


class DeepSeekLLMProvider(BaseLLMProvider):
    """DeepSeek Chat provider (default production LLM)."""

    provider_name = "deepseek"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        self.model = model or os.getenv("LLM_MODEL") or "deepseek-chat"
        self.base_url = (
            base_url
            or os.getenv("LLM_BASE_URL")
            or "https://api.deepseek.com/v1"
        )

    def get_chat_model(self, temperature: float = 0.0) -> BaseChatModel:
        if not self.api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY or LLM_API_KEY must be provided for DeepSeek provider."
            )
        return ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=temperature,
            max_retries=2,
            timeout=30.0,
        )


class OpenAILLMProvider(BaseLLMProvider):
    """OpenAI provider (GPT-4o, GPT-4o-mini)."""

    provider_name = "openai"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"
        self.base_url = base_url or os.getenv("LLM_BASE_URL") or "https://api.openai.com/v1"

    def get_chat_model(self, temperature: float = 0.0) -> BaseChatModel:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY or LLM_API_KEY must be provided for OpenAI provider.")
        return ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=temperature,
            max_retries=2,
            timeout=30.0,
        )


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM Provider reserved strictly for offline deterministic tests."""

    provider_name = "mock"

    def __init__(self, canned_response: Optional[str] = None):
        self.canned_response = canned_response

    def get_chat_model(self, temperature: float = 0.0) -> BaseChatModel:
        raise NotImplementedError("MockLLMProvider uses direct deterministic fallbacks.")

    def with_structured_output(self, schema: Type[T], temperature: float = 0.0):
        import json
        from langchain_core.runnables import RunnableLambda
        canned = self.canned_response

        def _invoke(inputs):
            if canned:
                try:
                    data = json.loads(canned)
                    return schema(**data)
                except Exception:
                    pass
            try:
                return schema(
                    answer="Réponse de test.",
                    executive_summary="Résumé de test.",
                    key_insights=["Insight 1"],
                    warnings=[],
                    suggested_followups=["Question 1"],
                )
            except Exception:
                return schema.model_construct()

        return RunnableLambda(_invoke)


def get_llm_provider(
    provider_name: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
) -> BaseLLMProvider:
    """Factory retrieving the configured LLM provider from env or arguments."""
    p_name = (provider_name or os.getenv("LLM_PROVIDER") or "deepseek").strip().lower()

    if p_name in ("mock", "test", "testing"):
        return MockLLMProvider()
    elif p_name in ("openai", "gpt"):
        return OpenAILLMProvider(api_key=api_key, model=model, base_url=base_url)
    elif p_name in ("deepseek", "deepseek-chat"):
        return DeepSeekLLMProvider(api_key=api_key, model=model, base_url=base_url)
    else:
        # Default to DeepSeek for unknown or empty
        return DeepSeekLLMProvider(api_key=api_key, model=model, base_url=base_url)
