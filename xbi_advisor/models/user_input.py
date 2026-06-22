"""Pydantic models for structured user input from Typeform surveys."""

from datetime import datetime

from pydantic import BaseModel


class DataGovernance(BaseModel):
    data_ownership: str | None = None


class MaturityLevel(BaseModel):
    data_literacy: str | None = None
    data_savviness: str | None = None
    bi_usage: str | None = None


class UserInput(BaseModel):
    respondent_id: str
    submitted_at: datetime
    data_governance: DataGovernance | None = None
    maturity_level: MaturityLevel | None = None
