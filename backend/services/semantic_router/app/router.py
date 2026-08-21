"""Semantic Router Logic.

Classifies user questions into specific intents using DeepSeek API via LangChain and outputs a structured Semantic Plan.
"""
import os
from enum import Enum
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

load_dotenv()

class Intent(str, Enum):
    DATA_QUERY = "DATA_QUERY"          
    CHART_GENERATION = "CHART_GENERATION"  
    UNRELATED = "UNRELATED"            
    AMBIGUOUS = "AMBIGUOUS"            

class SemanticPlanOut(BaseModel):
    intent: Intent = Field(description="The classified intent of the user query.")
    confidence: float = Field(description="Confidence score between 0 and 1.")
    clarification_options: list[str] = Field(
        default_factory=list,
        description="If intent is AMBIGUOUS, provide 2-3 specific interpretation options."
    )
    source_tables: list[str] = Field(default_factory=list, description="List of table names selected from context.")
    metric: str | None = Field(None, description="The core business metric being requested.")
    dimensions: list[str] = Field(default_factory=list, description="Columns or attributes used to group or slice.")
    filters: list[str] = Field(default_factory=list, description="Specific conditions applied.")
    period: str | None = Field(None, description="The time period for the query.")
    grain: str | None = Field(None, description="The temporal or spatial grain.")
    reasoning: str | None = Field(None, description="Brief explanation of why these tables and metrics were selected.")


def _get_llm():
    return ChatOpenAI(
        model="deepseek-chat", 
        api_key=os.getenv("DEEPSEEK_API_KEY"), 
        base_url="https://api.deepseek.com/v1",
        max_retries=2
    )

def create_semantic_plan(query: str, context: dict, chat_history: list) -> dict:
    """Classify the intent and generate a semantic plan based on context."""
    llm = _get_llm()
    structured_llm = llm.with_structured_output(SemanticPlanOut)
    
    system_msg = (
        "You are a semantic router for a BI conversational agent. "
        "Your job is to classify the user's query into one of the following intents:\n"
        "- DATA_QUERY: User is asking a clear question about data.\n"
        "- CHART_GENERATION: User explicitly asks for a graph, chart, or plot.\n"
        "- UNRELATED: General chatter, hellos, or questions outside a business context.\n"
        "- AMBIGUOUS: The query is too vague, has multiple interpretations, or is missing critical context. "
        "If AMBIGUOUS, you must provide 'clarification_options' with a few specific ways to interpret it.\n"
        "\nIf the intent is DATA_QUERY or CHART_GENERATION, use the provided schema context (which includes tables, relations, metrics) "
        "to fill in 'source_tables', 'metric', 'dimensions', 'filters', 'period', 'grain' and 'reasoning'. "
        "If you cannot determine the metric or tables because the query is too vague, classify as AMBIGUOUS."
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_msg),
        ("human", "Context: {context}\n\nHistory: {history}\n\nQuery: {query}")
    ])
    
    chain = prompt | structured_llm
    
    try:
        result = chain.invoke({
            "query": query, 
            "context": str(context), 
            "history": str(chat_history)
        })
        return result.model_dump()
    except Exception as e:
        print(f"Error creating semantic plan: {e}")
        return {"intent": "DATA_QUERY", "confidence": 0.0}
