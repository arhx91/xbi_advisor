from typing import TypedDict


class RuleMatchDict(TypedDict):
    id: str
    recommendation: str
    description: str
    scores: dict[str, int]
