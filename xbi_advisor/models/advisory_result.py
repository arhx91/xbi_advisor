from pydantic import BaseModel

from xbi_advisor.models.match_result import CategoryMatches
from xbi_advisor.models.types import RuleMatchDict


class AdvisoryResult(BaseModel):
    matched_rules: list[RuleMatchDict]
    category_matches: CategoryMatches
    recommendation: str
