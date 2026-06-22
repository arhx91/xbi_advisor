from pydantic import BaseModel

from xbi_advisor.models.types import RuleMatchDict

type CategoryMatches = dict[str, list[RuleMatchDict]]


class MatchResult(BaseModel):
    matched_rules: list[RuleMatchDict]
    category_matches: CategoryMatches
