from dataclasses import dataclass, field


@dataclass
class TenderItem:
    requirement: str


@dataclass
class ProductCandidate:
    model: str
    params: list[str] = field(default_factory=list)


@dataclass
class MatchResult:
    model: str
    matched_param: str
    score: float
    confidence: str
