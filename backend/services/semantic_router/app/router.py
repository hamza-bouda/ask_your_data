"""Semantic Router Logic.

Classifies user questions into specific intents using DeepSeek API via LangChain.
"""
import os
from enum import Enum
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

load_dotenv()

class Intent(str, Enum):
    DATA_QUERY = "DATA_QUERY"          # Wants to query data
    CHART_GENERATION = "CHART_GENERATION"  # Wants a chart
    UNRELATED = "UNRELATED"            # Chit-chat or unrelated
    AMBIGUOUS = "AMBIGUOUS"            # Needs clarification

class RouteResult(BaseModel):
    intent: Intent = Field(description="The classified intent of the user query.")
    confidence: float = Field(description="Confidence score between 0 and 1.")
    clarification_options: list[str] = Field(
        default_factory=list,
        description="If intent is AMBIGUOUS, provide 2-3 specific interpretation options."
    )

def _get_llm():
    # Use DeepSeek via OpenAI compatible endpoint
    return ChatOpenAI(
        model="deepseek-chat", 
        api_key=os.getenv("DEEPSEEK_API_KEY"), 
        base_url="https://api.deepseek.com/v1",
        max_retries=2
    )

def classify_intent(query: str) -> RouteResult:
    """Classify the intent of a user query using DeepSeek structured output."""
    llm = _get_llm()
    structured_llm = llm.with_structured_output(RouteResult)
    
    system_msg = (
        "You are a semantic router for a BI conversational agent. "
        "Your job is to classify the user's query into one of the following intents:\n"
        "- DATA_QUERY: User is asking a clear question about data.\n"
        "- CHART_GENERATION: User explicitly asks for a graph, chart, or plot.\n"
        "- UNRELATED: General chatter, hellos, or questions outside a business context.\n"
        "- AMBIGUOUS: The query is too vague, has multiple interpretations, or is missing critical context (like date ranges or specific metrics). "
        "If AMBIGUOUS, you must provide 'clarification_options' with a few specific ways to interpret it.\n"
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_msg),
        ("human", "{query}")
    ])
    
    chain = prompt | structured_llm
    
    try:
        result = chain.invoke({"query": query})
        return result
    except Exception as e:
        # Fallback heuristic if LLM fails
        return RouteResult(intent=Intent.DATA_QUERY, confidence=0.0)
