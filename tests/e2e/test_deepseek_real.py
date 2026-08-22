"""End-to-End test validating real DeepSeek API integration when DEEPSEEK_API_KEY is configured."""

import os
import pytest
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage
from contracts.llm import DeepSeekLLMProvider, get_llm_provider


class TestIntentSchema(BaseModel):
    intent: str
    confidence: float


def _is_real_deepseek_key() -> bool:
    key = os.getenv("DEEPSEEK_API_KEY", "")
    if not key or "placeholder" in key.lower() or "test" in key.lower() or key in {"mock", "placeholder"}:
        return False
    return True


@pytest.mark.integration
@pytest.mark.skipif(
    not _is_real_deepseek_key(),
    reason="Valid real DEEPSEEK_API_KEY environment variable is not configured. Skipped in offline CI.",
)
class TestDeepSeekRealIntegration:
    """Live integration tests against the actual DeepSeek API."""

    def test_deepseek_live_text_generation(self):
        """Send a real prompt to DeepSeek and verify valid structured completion."""
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not _is_real_deepseek_key():
            pytest.skip("Valid real DEEPSEEK_API_KEY is not configured.")
        provider = DeepSeekLLMProvider(api_key=api_key)
        model = provider.get_chat_model()

        response = model.invoke([
            SystemMessage(content="Tu es un assistant concis."),
            HumanMessage(content="Réponds UNIQUEMENT avec le mot 'READY' en majuscules.")
        ])

        assert "READY" in response.content.upper()

    def test_deepseek_live_structured_json(self):
        """Verify DeepSeek generates valid JSON conforming to our schema."""
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not _is_real_deepseek_key():
            pytest.skip("Valid real DEEPSEEK_API_KEY is not configured.")
        provider = DeepSeekLLMProvider(api_key=api_key)
        structured_model = provider.with_structured_output(TestIntentSchema)

        data = structured_model.invoke([
            SystemMessage(content="Tu es un classificateur d'intention analytique."),
            HumanMessage(content="Donne-moi le chiffre d'affaires du mois dernier.")
        ])

        assert data.intent in {"DATA_QUERY", "CATALOG_QUERY", "UNRELATED"}
        assert data.confidence >= 0.0
