"""
Risk Scoring Module

Implements Pass 2 of the two-pass processing approach.
Evaluates extracted obligations against risk heuristics and assigns severity levels.

Supports two modes:
1. Rule-based scoring (fast, no API cost) - default
2. LLM-enhanced scoring (more nuanced) - optional
"""

import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


class RiskCategory(Enum):
    """Categories of contract risk."""
    FINANCIAL_EXPOSURE = "financial_exposure"
    TIME_BOMB = "time_bomb"
    ASYMMETRIC_TERMS = "asymmetric_terms"
    COMPETITIVE_RESTRICTION = "competitive_restriction"
    UNCLEAR_OBLIGATION = "unclear_obligation"
    CONSENT_RISK = "consent_risk"
    DISPUTE_RESOLUTION = "dispute_resolution"


class Severity(Enum):
    """Risk severity levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class RiskFlag:
    """A flagged risk in the contract."""
    obligation_id: str
    category: RiskCategory
    severity: Severity
    title: str
    description: str
    source_text: str
    source_location: str
    action_required: str
    negotiation_suggestion: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "obligation_id": self.obligation_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "source_text": self.source_text,
            "source_location": self.source_location,
            "action_required": self.action_required,
            "negotiation_suggestion": self.negotiation_suggestion,
        }


@dataclass
class RiskSummary:
    """Summary of all risks found."""
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    most_concerning: Optional[str]
    overall_risk_level: Severity

    def to_dict(self) -> dict:
        return {
            "high_risk_count": self.high_risk_count,
            "medium_risk_count": self.medium_risk_count,
            "low_risk_count": self.low_risk_count,
            "most_concerning": self.most_concerning,
            "overall_risk_level": self.overall_risk_level.value,
        }


@dataclass
class RiskAssessment:
    """Complete risk assessment for a contract."""
    file_path: str
    risks: list[RiskFlag]
    summary: RiskSummary
    obligations_analyzed: int

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "risks": [r.to_dict() for r in self.risks],
            "summary": self.summary.to_dict(),
            "obligations_analyzed": self.obligations_analyzed,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @property
    def high_risks(self) -> list[RiskFlag]:
        return [r for r in self.risks if r.severity == Severity.HIGH]

    @property
    def medium_risks(self) -> list[RiskFlag]:
        return [r for r in self.risks if r.severity == Severity.MEDIUM]

    @property
    def low_risks(self) -> list[RiskFlag]:
        return [r for r in self.risks if r.severity == Severity.LOW]


class RiskPatterns:
    """
    Pattern-based risk detection rules.

    Each pattern set contains:
    - regex patterns to match
    - severity level
    - description template
    - suggested action
    """

    # Financial Exposure Patterns (HIGH)
    FINANCIAL_EXPOSURE = {
        "patterns": [
            (r'unlimited\s+liab', 'Unlimited liability exposure'),
            (r'without\s+(?:any\s+)?limit', 'Uncapped financial exposure'),
            (r'shall\s+indemnify.*(?:any\s+and\s+all|all\s+claims)', 'Broad indemnification'),
            (r'liquidated\s+damages', 'Liquidated damages clause'),
            (r'personal(?:ly)?\s+guarant', 'Personal guarantee required'),
            (r'joint(?:ly)?\s+and\s+several(?:ly)?', 'Joint and several liability'),
            (r'(?:penalty|penalt(?:y|ies))\s+(?:of|for|equal)', 'Penalty clause'),
            (r'(?:late\s+fee|penalty).*(?:1[0-9]|[2-9][0-9])\s*%', 'Excessive late fee (>10%)'),
            (r'(?:security\s+deposit|deposit).*(?:three|four|[3-9])\s*month', 'Large security deposit'),
            (r'forfeit(?:ure)?.*(?:deposit|payment)', 'Forfeiture of payments'),
        ],
        "severity": Severity.HIGH,
        "category": RiskCategory.FINANCIAL_EXPOSURE,
        "action": "Review financial exposure limits. Consider negotiating caps on liability.",
        "negotiation": "Request liability caps equal to contract value or insurance limits.",
    }

    # Time Bomb Patterns (MEDIUM)
    TIME_BOMBS = {
        "patterns": [
            (r'auto(?:matic(?:ally)?)?[\s-]*renew', 'Auto-renewal clause'),
            (r'(?:shall|will)\s+(?:automatically\s+)?(?:renew|extend|continue)', 'Automatic extension'),
            (r'(?:notice|notify).*(?:at\s+least\s+)?(?:[1-9]|1[0-4])\s*(?:days?|business\s+days?)\s+(?:prior|before|in\s+advance)', 'Short notice period (<15 days)'),
            (r'(?:notice|notify).*(?:at\s+least\s+)?(?:1[5-9]|2[0-9])\s*(?:days?)\s+(?:prior|before)', 'Notice period (15-29 days)'),
            (r'retroactive', 'Retroactive terms'),
            (r'(?:cure|remedy).*(?:[1-7])\s*(?:days?|business\s+days?)', 'Short cure period (<7 days)'),
            (r'evergreen', 'Evergreen clause'),
            (r'(?:perpetual|indefinite)(?:ly)?', 'Indefinite term'),
            (r'in\s+(?:its|their|sole)\s+discretion.*(?:terminate|cancel)', 'Discretionary termination'),
        ],
        "severity": Severity.MEDIUM,
        "category": RiskCategory.TIME_BOMB,
        "action": "Set calendar reminders for notice deadlines. Review renewal terms.",
        "negotiation": "Request longer notice periods (60-90 days) and opt-out renewal.",
    }

    # Asymmetric Terms Patterns (MEDIUM)
    ASYMMETRIC_TERMS = {
        "patterns": [
            (r'(?:may|reserves?\s+the\s+right\s+to)\s+(?:modify|amend|change).*(?:at\s+any\s+time|without\s+(?:prior\s+)?notice)', 'Unilateral amendment right'),
            (r'(?:in\s+(?:its|their|sole)\s+discretion)', 'Sole discretion clause'),
            (r'(?:may|can)\s+(?:terminate|cancel).*(?:for\s+(?:any|no)\s+reason|at\s+(?:any\s+)?(?:time|will))', 'One-sided termination right'),
            (r'(?:may|reserves?\s+the\s+right\s+to)\s+increase.*(?:fee|price|rate|rent)', 'Unilateral price increase'),
            (r'non-?refundable', 'Non-refundable payment'),
            (r'waive.*(?:right|claim)', 'Waiver of rights'),
            (r'(?:you|tenant|employee|customer)\s+(?:shall|must|agree\s+to)\s+indemnify', 'One-sided indemnification'),
        ],
        "severity": Severity.MEDIUM,
        "category": RiskCategory.ASYMMETRIC_TERMS,
        "action": "Identify imbalanced terms and request reciprocal rights.",
        "negotiation": "Request mutual obligations or balanced termination rights.",
    }

    # Competitive Restrictions (HIGH)
    COMPETITIVE_RESTRICTIONS = {
        "patterns": [
            (r'non[\s-]*compete', 'Non-compete clause'),
            (r'(?:shall|agree)\s+not\s+(?:to\s+)?(?:compete|engage)', 'Competition restriction'),
            (r'non[\s-]*solicit', 'Non-solicitation clause'),
            (r'(?:shall|agree)\s+not\s+(?:to\s+)?(?:solicit|recruit|hire)', 'Solicitation restriction'),
            (r'exclusiv(?:e|ity)', 'Exclusivity requirement'),
            (r'(?:assign|transfer).*(?:all|any).*(?:intellectual\s+property|ip|invention|work\s+product)', 'Broad IP assignment'),
            (r'(?:work(?:s)?\s+(?:for\s+hire|made\s+for\s+hire)|work-?for-?hire)', 'Work for hire'),
            (r'(?:18|24|36)\s*months?', 'Extended restriction period'),
            (r'(?:worldwide|global|anywhere)', 'Worldwide geographic scope'),
            (r'(?:trade\s+secret|proprietary\s+information).*(?:perpetual|indefinite|forever)', 'Perpetual trade secret obligation'),
        ],
        "severity": Severity.HIGH,
        "category": RiskCategory.COMPETITIVE_RESTRICTION,
        "action": "Carefully review scope and duration of restrictions.",
        "negotiation": "Narrow geographic scope, shorten duration, clarify permitted activities.",
    }

    # Unclear Obligations (LOW)
    UNCLEAR_OBLIGATIONS = {
        "patterns": [
            (r'reasonable\s+efforts?', 'Reasonable efforts standard'),
            (r'best\s+efforts?', 'Best efforts standard'),
            (r'commercially\s+reasonable', 'Commercially reasonable standard'),
            (r'as\s+(?:needed|required|necessary)', 'Undefined "as needed" obligation'),
            (r'from\s+time\s+to\s+time', 'Undefined frequency'),
            (r'(?:material|substantial)(?:ly)?(?!\s+(?:all|breach))', 'Undefined materiality'),
            (r'(?:to\s+(?:its|their)\s+satisfaction)', 'Subjective satisfaction'),
            (r'(?:promptly|timely)(?!\s+\d)', 'Undefined timeline'),
            (r'(?:adequate|sufficient|appropriate)', 'Undefined adequacy'),
        ],
        "severity": Severity.LOW,
        "category": RiskCategory.UNCLEAR_OBLIGATION,
        "action": "Clarify vague terms before signing if possible.",
        "negotiation": "Request specific definitions, timelines, or objective standards.",
    }

    # Consent/Approval Risks (MEDIUM)
    CONSENT_RISKS = {
        "patterns": [
            (r'(?:consent|approval).*(?:not\s+(?:to\s+be\s+)?unreasonably\s+(?:withheld|delayed))', 'Consent standard'),
            (r'(?:prior\s+(?:written\s+)?(?:consent|approval))', 'Prior approval required'),
            (r'(?:sole\s+(?:and\s+absolute\s+)?discretion)', 'Sole discretion'),
            (r'(?:without\s+(?:prior\s+)?(?:consent|approval))', 'No consent required'),
            (r'(?:may\s+(?:withhold|deny)\s+(?:consent|approval))', 'Discretionary denial'),
        ],
        "severity": Severity.MEDIUM,
        "category": RiskCategory.CONSENT_RISK,
        "action": "Understand what requires approval and ensure timelines are defined.",
        "negotiation": "Add response deadlines and objective criteria for approval.",
    }

    # Dispute Resolution (MEDIUM)
    DISPUTE_RESOLUTION = {
        "patterns": [
            (r'(?:binding\s+)?arbitration', 'Mandatory arbitration'),
            (r'(?:waive|waiver).*(?:jury|trial)', 'Jury trial waiver'),
            (r'class\s+action\s+waiver', 'Class action waiver'),
            (r'(?:waive|waiver).*(?:class|collective|representative)', 'Collective action waiver'),
            (r'(?:prevailing\s+party|loser\s+pays).*(?:attorney|legal)\s+fees?', 'Loser pays provision'),
            (r'(?:exclusive\s+(?:jurisdiction|venue))', 'Exclusive venue'),
            (r'(?:within\s+(?:one|1)\s+year|(?:one|1)[\s-]*year\s+(?:statute|limitation))', 'Short limitation period'),
            (r'(?:six|6)\s*months?.*(?:bring|commence|file)', 'Very short limitation period'),
        ],
        "severity": Severity.MEDIUM,
        "category": RiskCategory.DISPUTE_RESOLUTION,
        "action": "Understand dispute resolution process and venue requirements.",
        "negotiation": "Request mutual venue or mediation before arbitration.",
    }

    ALL_PATTERNS = [
        FINANCIAL_EXPOSURE,
        TIME_BOMBS,
        ASYMMETRIC_TERMS,
        COMPETITIVE_RESTRICTIONS,
        UNCLEAR_OBLIGATIONS,
        CONSENT_RISKS,
        DISPUTE_RESOLUTION,
    ]


class RiskScorer:
    """
    Scores obligations for risk using pattern matching and optional LLM analysis.

    Default mode uses fast, rule-based pattern matching.
    LLM mode provides more nuanced analysis but requires API calls.
    """

    def __init__(self, use_llm: bool = False, api_key: Optional[str] = None):
        """
        Initialize the risk scorer.

        Args:
            use_llm: Whether to use LLM for enhanced analysis (Pass 2).
            api_key: Anthropic API key (only needed if use_llm=True).
        """
        self.use_llm = use_llm
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

        if use_llm and not self.api_key:
            raise ValueError("API key required for LLM-based risk scoring.")

    def score(self, analysis_result) -> RiskAssessment:
        """
        Score all obligations in an analysis result for risk.

        Args:
            analysis_result: AnalysisResult from ContractAnalyzer

        Returns:
            RiskAssessment with all flagged risks
        """
        all_risks = []

        # Score each obligation
        for obligation in analysis_result.obligations:
            risks = self._score_obligation(obligation)
            all_risks.extend(risks)

        # Also check auto-renewal specifically
        if analysis_result.auto_renewal.exists:
            auto_renewal_risk = self._score_auto_renewal(analysis_result.auto_renewal)
            if auto_renewal_risk:
                all_risks.append(auto_renewal_risk)

        # Create summary
        summary = self._create_summary(all_risks)

        return RiskAssessment(
            file_path=analysis_result.file_path,
            risks=all_risks,
            summary=summary,
            obligations_analyzed=len(analysis_result.obligations),
        )

    def _score_obligation(self, obligation) -> list[RiskFlag]:
        """Score a single obligation for risks."""
        risks = []

        # Combine all text to search
        search_text = " ".join([
            obligation.description or "",
            obligation.source_text or "",
            obligation.conditions or "",
        ]).lower()

        # Check each pattern set
        for pattern_set in RiskPatterns.ALL_PATTERNS:
            for pattern, match_description in pattern_set["patterns"]:
                if re.search(pattern, search_text, re.IGNORECASE):
                    risk = RiskFlag(
                        obligation_id=obligation.id,
                        category=pattern_set["category"],
                        severity=pattern_set["severity"],
                        title=match_description,
                        description=self._build_description(
                            match_description,
                            obligation,
                            pattern_set["category"],
                        ),
                        source_text=obligation.source_text,
                        source_location=obligation.source_location,
                        action_required=pattern_set["action"],
                        negotiation_suggestion=pattern_set.get("negotiation"),
                    )
                    risks.append(risk)
                    break  # One match per pattern set per obligation

        # Update obligation's risk level based on highest severity found
        if risks:
            highest_severity = max(risks, key=lambda r: self._severity_rank(r.severity))
            obligation.risk_level = highest_severity.severity.value
            obligation.risk_flags = [r.title for r in risks]

        return risks

    def _score_auto_renewal(self, auto_renewal) -> Optional[RiskFlag]:
        """Create a risk flag for auto-renewal if present."""
        notice_period = auto_renewal.notice_to_cancel or ""

        # Check if notice period is short
        short_notice = False
        if notice_period:
            # Extract number of days
            match = re.search(r'(\d+)\s*(?:days?|business\s+days?)', notice_period.lower())
            if match:
                days = int(match.group(1))
                short_notice = days < 30

        severity = Severity.MEDIUM if short_notice else Severity.LOW

        return RiskFlag(
            obligation_id="AUTO-RENEWAL",
            category=RiskCategory.TIME_BOMB,
            severity=severity,
            title="Auto-Renewal Clause",
            description=(
                f"Contract automatically renews for {auto_renewal.period or 'unspecified period'}. "
                f"Notice required to cancel: {auto_renewal.notice_to_cancel or 'not specified'}."
            ),
            source_text="",
            source_location="See termination section",
            action_required="Set calendar reminder for renewal notice deadline.",
            negotiation_suggestion="Request opt-in renewal instead of auto-renewal.",
        )

    def _build_description(self, match_type: str, obligation, category: RiskCategory) -> str:
        """Build a descriptive risk explanation."""
        descriptions = {
            RiskCategory.FINANCIAL_EXPOSURE: (
                f"{match_type} detected. This could expose you to significant financial "
                f"liability. The obligation requires: {obligation.description}"
            ),
            RiskCategory.TIME_BOMB: (
                f"{match_type} detected. This creates a deadline-sensitive obligation "
                f"that could trigger automatically. Review carefully: {obligation.description}"
            ),
            RiskCategory.ASYMMETRIC_TERMS: (
                f"{match_type} detected. This creates an imbalanced obligation where "
                f"one party has more rights than the other: {obligation.description}"
            ),
            RiskCategory.COMPETITIVE_RESTRICTION: (
                f"{match_type} detected. This restricts your ability to work with "
                f"competitors or use certain skills/knowledge: {obligation.description}"
            ),
            RiskCategory.UNCLEAR_OBLIGATION: (
                f"{match_type} detected. The obligation uses vague language that could "
                f"be interpreted differently by each party: {obligation.description}"
            ),
            RiskCategory.CONSENT_RISK: (
                f"{match_type} detected. This requires obtaining approval which could "
                f"cause delays or be denied: {obligation.description}"
            ),
            RiskCategory.DISPUTE_RESOLUTION: (
                f"{match_type} detected. This affects how disputes are resolved and "
                f"may limit your legal options: {obligation.description}"
            ),
        }
        return descriptions.get(category, f"{match_type}: {obligation.description}")

    def _severity_rank(self, severity: Severity) -> int:
        """Return numeric rank for severity comparison."""
        return {Severity.LOW: 1, Severity.MEDIUM: 2, Severity.HIGH: 3}[severity]

    def _create_summary(self, risks: list[RiskFlag]) -> RiskSummary:
        """Create a summary of all risks."""
        high_count = sum(1 for r in risks if r.severity == Severity.HIGH)
        medium_count = sum(1 for r in risks if r.severity == Severity.MEDIUM)
        low_count = sum(1 for r in risks if r.severity == Severity.LOW)

        # Determine overall risk level
        if high_count >= 2:
            overall = Severity.HIGH
        elif high_count >= 1 or medium_count >= 3:
            overall = Severity.MEDIUM
        else:
            overall = Severity.LOW

        # Find most concerning risk
        most_concerning = None
        if risks:
            highest = max(risks, key=lambda r: self._severity_rank(r.severity))
            most_concerning = f"{highest.title} ({highest.category.value})"

        return RiskSummary(
            high_risk_count=high_count,
            medium_risk_count=medium_count,
            low_risk_count=low_count,
            most_concerning=most_concerning,
            overall_risk_level=overall,
        )


def score_risks(analysis_result, use_llm: bool = False) -> RiskAssessment:
    """
    Convenience function to score risks in an analysis result.

    Args:
        analysis_result: AnalysisResult from ContractAnalyzer
        use_llm: Whether to use LLM-enhanced scoring

    Returns:
        RiskAssessment with flagged risks
    """
    scorer = RiskScorer(use_llm=use_llm)
    return scorer.score(analysis_result)


if __name__ == "__main__":
    import sys

    # Import analyzer here to avoid circular imports
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.analyzer import analyze_contract

    if len(sys.argv) < 2:
        print("Usage: python -m src.risk_scorer <contract_file>")
        print("Set ANTHROPIC_API_KEY environment variable first.")
        sys.exit(1)

    file_path = sys.argv[1]

    try:
        # First analyze the contract
        print(f"Analyzing {file_path}...")
        analysis = analyze_contract(file_path, verbose=False)
        print(f"Found {len(analysis.obligations)} obligations")

        # Then score for risks
        print("Scoring risks...")
        assessment = score_risks(analysis)

        print("\n" + "=" * 60)
        print("RISK ASSESSMENT")
        print("=" * 60)

        print(f"\nFile: {assessment.file_path}")
        print(f"Obligations analyzed: {assessment.obligations_analyzed}")
        print(f"\nOverall Risk Level: {assessment.summary.overall_risk_level.value.upper()}")

        if assessment.summary.most_concerning:
            print(f"Most Concerning: {assessment.summary.most_concerning}")

        print(f"\nRisk Counts:")
        print(f"  HIGH:   {assessment.summary.high_risk_count}")
        print(f"  MEDIUM: {assessment.summary.medium_risk_count}")
        print(f"  LOW:    {assessment.summary.low_risk_count}")

        if assessment.high_risks:
            print(f"\n{'='*60}")
            print("HIGH RISK FLAGS")
            print("=" * 60)
            for risk in assessment.high_risks:
                print(f"\n  [{risk.obligation_id}] {risk.title}")
                print(f"    Category: {risk.category.value}")
                print(f"    {risk.description[:100]}...")
                print(f"    Action: {risk.action_required}")
                if risk.negotiation_suggestion:
                    print(f"    Negotiate: {risk.negotiation_suggestion}")

        if assessment.medium_risks:
            print(f"\n{'='*60}")
            print("MEDIUM RISK FLAGS")
            print("=" * 60)
            for risk in assessment.medium_risks:
                print(f"\n  [{risk.obligation_id}] {risk.title}")
                print(f"    Category: {risk.category.value}")
                print(f"    Action: {risk.action_required}")

        # Save JSON output
        output_file = Path(file_path).stem + "_risks.json"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(assessment.to_json())
        print(f"\nFull results saved to: {output_file}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
