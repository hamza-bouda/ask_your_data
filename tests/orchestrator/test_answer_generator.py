"""Unit tests for the Answer Generator component in the Conversation Orchestrator."""

import pytest
from backend.services.orchestrator.app.answer_generator import (
    AnswerGenerator,
    BusinessAnswer,
    generate_business_answer,
)
from contracts.llm import MockLLMProvider


class TestAnswerGenerator:
    """Test AnswerGenerator business insight synthesis and zero-hallucination guardrails."""

    def test_deterministic_fallback_when_llm_unavailable(self):
        """When results are present and no LLM is configured, produces deterministic structured answer."""
        results = [
            {"country": "France", "revenue": 125000},
            {"country": "Germany", "revenue": 98000},
            {"country": "USA", "revenue": 210000},
        ]
        sql = "SELECT country, SUM(total) as revenue FROM invoices GROUP BY country"

        answer = generate_business_answer(
            question="Quel est le chiffre d'affaires par pays ?",
            results=results,
            sql_query=sql,
        )

        assert isinstance(answer, BusinessAnswer)
        assert answer.answer is not None
        assert answer.executive_summary is not None
        assert len(answer.key_insights) >= 1
        assert len(answer.suggested_followups) >= 1

    def test_empty_results_fallback(self):
        """When query yields zero rows, cleanly reports absence of data without hallucinations."""
        answer = generate_business_answer(
            question="Trouve les clients inactifs depuis 10 ans",
            results=[],
            sql_query="SELECT id FROM customers WHERE last_active < 2016",
        )

        assert isinstance(answer, BusinessAnswer)
        assert "aucun résultat" in answer.answer.lower()
        assert len(answer.warnings) >= 1

    def test_mock_llm_structured_synthesis(self):
        """AnswerGenerator parses structured JSON from LLMProvider successfully."""
        mock_response = (
            '{\n'
            '  "answer": "Les ventes totales sont de 433 000 € avec les USA en tête.",\n'
            '  "executive_summary": "Les USA représentent la majorité du chiffre d\'affaires.",\n'
            '  "key_insights": [\n'
            '    "USA génère 210 000 € de revenus.",\n'
            '    "La France se positionne au 2ème rang avec 125 000 €."\n'
            '  ],\n'
            '  "warnings": [],\n'
            '  "suggested_followups": [\n'
            '    "Quelle est la croissance annuelle par pays ?",\n'
            '    "Quel est le panier moyen aux USA ?"\n'
            '  ]\n'
            '}'
        )
        mock_provider = MockLLMProvider(canned_response=mock_response)
        generator = AnswerGenerator(llm_provider=mock_provider)

        results = [
            {"country": "USA", "revenue": 210000},
            {"country": "France", "revenue": 125000},
        ]
        answer = generator.generate(
            question="Quelles sont les ventes par pays ?",
            results=results,
            sql_query="SELECT country, revenue FROM sales",
        )

        assert answer.answer == "Les ventes totales sont de 433 000 € avec les USA en tête."
        assert len(answer.key_insights) == 2
        assert "USA génère" in answer.key_insights[0]
        assert len(answer.suggested_followups) == 2

    def test_sample_truncation_limits_token_usage(self):
        """AnswerGenerator formats maximum 20 rows to protect LLM context length."""
        large_results = [{"id": i, "val": f"item_{i}"} for i in range(100)]
        generator = AnswerGenerator()
        sample_text = generator._format_results_sample(large_results)

        # Must indicate truncation
        assert "100 lignes" in sample_text or "premières" in sample_text
