from enum import StrEnum


class RiskCategory(StrEnum):
    GOVERNANCE = "governance"
    MATURITY = "maturity"
    TOOLING = "tooling"
    SECURITY = "security"
    PROCESS = "process"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
