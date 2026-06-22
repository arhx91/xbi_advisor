"""Pydantic model for the Xebia services catalogue loaded from YAML assets."""

from pydantic import BaseModel


class XebiaServices(BaseModel):
    trainings: list[str]
    implementation_guidance_and_support: list[str]
    conversational_analytics: list[str]
    create_stakeholder_trust: list[str]
    performance_optimization: list[str]
