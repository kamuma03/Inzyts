from pydantic import BaseModel, Field
from typing import List, Optional


class AnalysisRecommendation(BaseModel):
    """Recommended analysis for a specific domain concept."""

    concept: str
    analysis_type: str
    description: str
    required_columns: List[str] = []


class KPI(BaseModel):
    """Key Performance Indicator definition."""

    name: str
    formula_description: str
    required_concepts: List[str]


class DomainConcept(BaseModel):
    """A concept within a domain (e.g., 'Patient ID', 'Transaction Amount')."""

    name: str
    description: str
    regex_patterns: List[str] = Field(
        default_factory=list, description="Regex patterns to match column names"
    )
    synonyms: List[str] = Field(default_factory=list, description="Common column names")
    data_type_hint: Optional[str] = None  # e.g., "numeric", "datetime"


class DomainTemplate(BaseModel):
    """Template for a specific domain or industry."""

    domain_name: str
    description: str
    concepts: List[DomainConcept]
    recommended_analyses: List[AnalysisRecommendation] = []
    kpis: List[KPI] = []

    def match_score(self, columns: List[str]) -> float:
        """Calculate how well a list of columns matches this domain."""
        matched_concepts = 0
        columns_lower = [c.lower() for c in columns]

        for concept in self.concepts:
            # Check synonyms
            if any(s.lower() in columns_lower for s in concept.synonyms):
                matched_concepts += 1
                continue

            # Check regex (simplified for prototype: just substring match on name if no regex)
            # In real impl, use re.match with concept.regex_patterns
            for col in columns_lower:
                for pattern in concept.regex_patterns:
                    if pattern in col:  # broad check
                        matched_concepts += 1
                        break

        if not self.concepts:
            return 0.0

        return matched_concepts / len(self.concepts)
