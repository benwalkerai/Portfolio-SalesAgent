"""
Pydantic models for data validation

Author: Ben Walker (BenRWalker@icloud.com)
"""
from pydantic import BaseModel, Field
from typing import Optional, List

class NameCheckOutput(BaseModel):
    is_name_in_message: bool
    name: str

class InputGuardrailOutput(BaseModel):
    is_safe: bool = Field(description="Whether the input is safe to process")
    is_prompt_injection: bool = Field(description="Whether prompt injection detected")
    contains_pii: bool = Field(description="Whether PII detected")
    is_off_topic: bool = Field(description="Whether request is outside domain boundary")
    is_harmful: bool = Field(description="Whether content contains harmful language")
    risk_score: float = Field(description="Overall risk score 0-1", ge=0, le=1)
    flagged_issues: List[str] = Field(description="List of specific issues found")
    sanitized_input: Optional[str] = Field(description="Sanitized version if modifications needed")

class OutputGuardrailOutput(BaseModel):
    is_safe: bool = Field(description="Whether the output is safe to return")
    contains_sensitive_data: bool = Field(description="Whether output leaks sensitive data")
    is_harmful_content: bool = Field(description="Whether output contains harmful content")
    is_hallucination: bool = Field(description="Whether output appears to be hallucinated")
    is_off_topic: bool = Field(description="Whether output is off-topic")
    toxicity_score: float = Field(description="Toxicity score 0-1", ge=0, le=1)
    flagged_issues: List[str] = Field(description="List of specific issues found")
    redacted_output: Optional[str] = Field(description="Redacted version if sensitive data found")
