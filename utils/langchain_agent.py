"""
LangChain wrapper for Gemini drafting (TASK 2 suggested stack).

Uses LangChain + langchain-google-genai: SystemMessage + HumanMessage → structured Pydantic output.
Rule-based escalation remains in Python; LangChain wraps the LLM call only.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field


class EmailDraftModel(BaseModel):
    """Structured email output (Pydantic guardrail before downstream string checks)."""

    subject: str = Field(..., min_length=5, description="Subject line with invoice reference")
    body: str = Field(..., min_length=50, description="Full professional email body")


def invoke_structured_draft(
    *,
    google_api_key: str,
    model_name: str,
    system_instruction: str,
    user_prompt: str,
    temperature: float = 0.65,
) -> dict[str, Any]:
    """
    Invoke Gemini through LangChain with structured (Pydantic) output.

    Returns a dict with keys subject and body.
    """
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=google_api_key,
        temperature=float(temperature),
    )
    structured = llm.with_structured_output(EmailDraftModel)
    messages = [
        SystemMessage(content=system_instruction),
        HumanMessage(content=user_prompt),
    ]
    result: EmailDraftModel = structured.invoke(messages)
    return {"subject": result.subject.strip(), "body": result.body.strip()}
