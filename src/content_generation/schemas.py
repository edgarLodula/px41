from dataclasses import dataclass

@dataclass
class Issue:
    rule_id: str
    severity: str
    weight: int
    line: int
    context: str
    message: str
    fix: str | None = None
    start: int | None = None
    end: int | None = None

@dataclass
class Evaluation:
    score: int
    passed: bool
    total_issues: int
    critical_count: int
    high_count: int
    medium_count: int
    issues: list[Issue]
    diagnosis: str