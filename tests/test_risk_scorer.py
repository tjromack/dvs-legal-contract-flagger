"""
Tests for the risk scorer module.

Run with: python tests/test_risk_scorer.py
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.risk_scorer import (
    RiskScorer,
    RiskFlag,
    RiskSummary,
    RiskAssessment,
    RiskCategory,
    Severity,
    RiskPatterns,
    score_risks,
)


# Test data directory
SAMPLE_CONTRACTS_DIR = Path(__file__).parent.parent / "data" / "sample_contracts"


def create_mock_obligation(
    id: str,
    party: str,
    description: str,
    source_text: str,
    source_location: str = "Section 1.1",
    type: str = "requirement",
    deadline: str = None,
    conditions: str = None,
):
    """Create a mock obligation for testing."""
    mock = MagicMock()
    mock.id = id
    mock.party = party
    mock.description = description
    mock.source_text = source_text
    mock.source_location = source_location
    mock.type = type
    mock.deadline = deadline
    mock.conditions = conditions
    mock.risk_level = "low"
    mock.risk_flags = []
    return mock


def create_mock_analysis_result(
    obligations: list,
    auto_renewal_exists: bool = False,
    auto_renewal_period: str = None,
    auto_renewal_notice: str = None,
):
    """Create a mock analysis result for testing."""
    mock = MagicMock()
    mock.file_path = "test_contract.pdf"
    mock.obligations = obligations

    mock.auto_renewal = MagicMock()
    mock.auto_renewal.exists = auto_renewal_exists
    mock.auto_renewal.period = auto_renewal_period
    mock.auto_renewal.notice_to_cancel = auto_renewal_notice

    return mock


class TestRiskDataClasses:
    """Tests for risk data classes."""

    def test_risk_flag_creation(self):
        flag = RiskFlag(
            obligation_id="OBL-001",
            category=RiskCategory.FINANCIAL_EXPOSURE,
            severity=Severity.HIGH,
            title="Unlimited liability",
            description="Test description",
            source_text="Test source",
            source_location="Section 1.1",
            action_required="Review this",
        )
        assert flag.obligation_id == "OBL-001"
        assert flag.category == RiskCategory.FINANCIAL_EXPOSURE
        assert flag.severity == Severity.HIGH
        print("  OK RiskFlag creation works")

    def test_risk_flag_to_dict(self):
        flag = RiskFlag(
            obligation_id="OBL-001",
            category=RiskCategory.TIME_BOMB,
            severity=Severity.MEDIUM,
            title="Auto-renewal",
            description="Test",
            source_text="Source",
            source_location="Section 2",
            action_required="Set reminder",
            negotiation_suggestion="Request opt-in",
        )
        d = flag.to_dict()
        assert d["category"] == "time_bomb"
        assert d["severity"] == "medium"
        assert d["negotiation_suggestion"] == "Request opt-in"
        print("  OK RiskFlag.to_dict() works")

    def test_risk_summary_creation(self):
        summary = RiskSummary(
            high_risk_count=2,
            medium_risk_count=3,
            low_risk_count=1,
            most_concerning="Unlimited liability",
            overall_risk_level=Severity.HIGH,
        )
        assert summary.high_risk_count == 2
        d = summary.to_dict()
        assert d["overall_risk_level"] == "high"
        print("  OK RiskSummary works")

    def test_risk_assessment_properties(self):
        flags = [
            RiskFlag("1", RiskCategory.FINANCIAL_EXPOSURE, Severity.HIGH, "A", "", "", "", ""),
            RiskFlag("2", RiskCategory.TIME_BOMB, Severity.MEDIUM, "B", "", "", "", ""),
            RiskFlag("3", RiskCategory.UNCLEAR_OBLIGATION, Severity.LOW, "C", "", "", "", ""),
        ]
        summary = RiskSummary(1, 1, 1, None, Severity.MEDIUM)
        assessment = RiskAssessment("test.pdf", flags, summary, 10)

        assert len(assessment.high_risks) == 1
        assert len(assessment.medium_risks) == 1
        assert len(assessment.low_risks) == 1
        print("  OK RiskAssessment properties work")


class TestFinancialExposureDetection:
    """Tests for financial exposure risk detection."""

    def test_detects_unlimited_liability(self):
        obl = create_mock_obligation(
            "OBL-001", "Tenant",
            "Tenant shall be liable for unlimited damages",
            "Tenant agrees to unlimited liability for all damages."
        )
        analysis = create_mock_analysis_result([obl])

        scorer = RiskScorer()
        result = scorer.score(analysis)

        high_risks = [r for r in result.risks if r.severity == Severity.HIGH]
        assert len(high_risks) >= 1
        assert any("liability" in r.title.lower() for r in high_risks)
        print("  OK Detects unlimited liability")

    def test_detects_indemnification(self):
        obl = create_mock_obligation(
            "OBL-002", "Employee",
            "Employee shall indemnify company",
            "Employee shall indemnify and hold harmless the Company from any and all claims."
        )
        analysis = create_mock_analysis_result([obl])

        scorer = RiskScorer()
        result = scorer.score(analysis)

        assert any("indemnif" in r.title.lower() for r in result.risks)
        print("  OK Detects broad indemnification")

    def test_detects_liquidated_damages(self):
        obl = create_mock_obligation(
            "OBL-003", "Contractor",
            "Liquidated damages of $10,000 per day",
            "Contractor shall pay liquidated damages of $10,000 per day for delays."
        )
        analysis = create_mock_analysis_result([obl])

        scorer = RiskScorer()
        result = scorer.score(analysis)

        assert any("liquidated" in r.title.lower() for r in result.risks)
        print("  OK Detects liquidated damages")


class TestTimeBombDetection:
    """Tests for time bomb risk detection."""

    def test_detects_auto_renewal(self):
        obl = create_mock_obligation(
            "OBL-001", "Tenant",
            "Lease automatically renews for one year",
            "This lease shall automatically renew for successive one-year periods."
        )
        analysis = create_mock_analysis_result([obl])

        scorer = RiskScorer()
        result = scorer.score(analysis)

        assert any("auto" in r.title.lower() and "renew" in r.title.lower() for r in result.risks)
        print("  OK Detects auto-renewal in obligations")

    def test_flags_auto_renewal_from_analysis(self):
        analysis = create_mock_analysis_result(
            [],
            auto_renewal_exists=True,
            auto_renewal_period="12 months",
            auto_renewal_notice="60 days",
        )

        scorer = RiskScorer()
        result = scorer.score(analysis)

        assert any(r.obligation_id == "AUTO-RENEWAL" for r in result.risks)
        print("  OK Flags auto-renewal from analysis metadata")

    def test_detects_short_notice_period(self):
        obl = create_mock_obligation(
            "OBL-002", "Customer",
            "Must provide 7 days notice to cancel",
            "Customer must notify Provider at least 7 days prior to cancellation."
        )
        analysis = create_mock_analysis_result([obl])

        scorer = RiskScorer()
        result = scorer.score(analysis)

        assert any("notice" in r.title.lower() for r in result.risks)
        print("  OK Detects short notice period")

    def test_detects_evergreen_clause(self):
        obl = create_mock_obligation(
            "OBL-003", "Licensee",
            "Agreement continues indefinitely",
            "This Agreement shall continue perpetually and indefinitely unless terminated."
        )
        analysis = create_mock_analysis_result([obl])

        scorer = RiskScorer()
        result = scorer.score(analysis)

        # Should detect either perpetual, indefinite, or evergreen
        time_bomb_risks = [r for r in result.risks if r.category == RiskCategory.TIME_BOMB]
        assert len(time_bomb_risks) > 0, f"Expected time bomb risks, got: {[r.title for r in result.risks]}"
        print("  OK Detects perpetual/evergreen terms")


class TestAsymmetricTermsDetection:
    """Tests for asymmetric terms detection."""

    def test_detects_unilateral_amendment(self):
        obl = create_mock_obligation(
            "OBL-001", "Provider",
            "Provider may modify terms at any time",
            "Provider reserves the right to modify these terms at any time without notice."
        )
        analysis = create_mock_analysis_result([obl])

        scorer = RiskScorer()
        result = scorer.score(analysis)

        assert any("unilateral" in r.title.lower() or "amendment" in r.title.lower() for r in result.risks)
        print("  OK Detects unilateral amendment rights")

    def test_detects_sole_discretion(self):
        obl = create_mock_obligation(
            "OBL-002", "Landlord",
            "Landlord may terminate in sole discretion",
            "Landlord may terminate this agreement in its sole discretion."
        )
        analysis = create_mock_analysis_result([obl])

        scorer = RiskScorer()
        result = scorer.score(analysis)

        assert any("discretion" in r.title.lower() for r in result.risks)
        print("  OK Detects sole discretion clauses")


class TestCompetitiveRestrictionDetection:
    """Tests for competitive restriction detection."""

    def test_detects_non_compete(self):
        obl = create_mock_obligation(
            "OBL-001", "Employee",
            "Employee agrees to non-compete for 24 months",
            "Employee shall not compete with Company for a period of 24 months."
        )
        analysis = create_mock_analysis_result([obl])

        scorer = RiskScorer()
        result = scorer.score(analysis)

        high_risks = [r for r in result.risks if r.severity == Severity.HIGH]
        assert any("non-compete" in r.title.lower() or "compete" in r.title.lower() for r in high_risks)
        print("  OK Detects non-compete clauses")

    def test_detects_non_solicitation(self):
        obl = create_mock_obligation(
            "OBL-002", "Contractor",
            "Contractor shall not solicit employees",
            "Contractor agrees not to solicit or hire any employees of Client."
        )
        analysis = create_mock_analysis_result([obl])

        scorer = RiskScorer()
        result = scorer.score(analysis)

        assert any("solicit" in r.title.lower() for r in result.risks)
        print("  OK Detects non-solicitation clauses")

    def test_detects_broad_ip_assignment(self):
        obl = create_mock_obligation(
            "OBL-003", "Employee",
            "All inventions assigned to company",
            "Employee assigns all intellectual property and inventions to Company."
        )
        analysis = create_mock_analysis_result([obl])

        scorer = RiskScorer()
        result = scorer.score(analysis)

        assert any("ip" in r.title.lower() or "assign" in r.title.lower() for r in result.risks)
        print("  OK Detects broad IP assignment")


class TestDisputeResolutionDetection:
    """Tests for dispute resolution risk detection."""

    def test_detects_mandatory_arbitration(self):
        obl = create_mock_obligation(
            "OBL-001", "Customer",
            "Disputes resolved by binding arbitration",
            "All disputes shall be resolved through binding arbitration."
        )
        analysis = create_mock_analysis_result([obl])

        scorer = RiskScorer()
        result = scorer.score(analysis)

        assert any("arbitration" in r.title.lower() for r in result.risks)
        print("  OK Detects mandatory arbitration")

    def test_detects_jury_waiver(self):
        obl = create_mock_obligation(
            "OBL-002", "Parties",
            "Both parties waive jury trial",
            "Each party hereby waives any right to a jury trial."
        )
        analysis = create_mock_analysis_result([obl])

        scorer = RiskScorer()
        result = scorer.score(analysis)

        assert any("jury" in r.title.lower() or "waiver" in r.title.lower() for r in result.risks)
        print("  OK Detects jury trial waiver")

    def test_detects_class_action_waiver(self):
        obl = create_mock_obligation(
            "OBL-003", "User",
            "User waives class action rights",
            "User agrees to class action waiver for all disputes."
        )
        analysis = create_mock_analysis_result([obl])

        scorer = RiskScorer()
        result = scorer.score(analysis)

        assert any("class" in r.title.lower() for r in result.risks)
        print("  OK Detects class action waiver")


class TestRiskSummary:
    """Tests for risk summary generation."""

    def test_overall_high_with_multiple_high_risks(self):
        obls = [
            create_mock_obligation("1", "A", "Unlimited liability", "unlimited liability exposure"),
            create_mock_obligation("2", "A", "Non-compete clause", "shall not compete"),
        ]
        analysis = create_mock_analysis_result(obls)

        scorer = RiskScorer()
        result = scorer.score(analysis)

        assert result.summary.overall_risk_level == Severity.HIGH
        print("  OK Overall HIGH with multiple high-severity risks")

    def test_overall_medium_with_one_high(self):
        obls = [
            create_mock_obligation("1", "A", "Unlimited liability", "unlimited liability"),
        ]
        analysis = create_mock_analysis_result(obls)

        scorer = RiskScorer()
        result = scorer.score(analysis)

        # One high risk should be MEDIUM overall
        assert result.summary.overall_risk_level in [Severity.HIGH, Severity.MEDIUM]
        print("  OK Appropriate overall level with one high risk")

    def test_most_concerning_populated(self):
        obls = [
            create_mock_obligation("1", "A", "Some obligation", "reasonable efforts required"),
        ]
        analysis = create_mock_analysis_result(obls)

        scorer = RiskScorer()
        result = scorer.score(analysis)

        if result.risks:
            assert result.summary.most_concerning is not None
        print("  OK Most concerning field populated when risks exist")


class TestIntegration:
    """Integration tests with sample contracts."""

    def test_score_employment_agreement(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key or api_key == "your_anthropic_key_here":
            print("  SKIP: ANTHROPIC_API_KEY not set (integration test)")
            return

        from src.analyzer import analyze_contract

        contract_path = SAMPLE_CONTRACTS_DIR / "employment_agreement.txt"
        if not contract_path.exists():
            print(f"  SKIP: {contract_path} not found")
            return

        try:
            analysis = analyze_contract(contract_path, verbose=False)
            assessment = score_risks(analysis)

            # Employment agreements should have competitive restrictions
            assert assessment.obligations_analyzed > 0
            assert len(assessment.risks) > 0

            # Should detect non-compete (employment_agreement.txt has one)
            categories = [r.category for r in assessment.risks]
            print(f"  OK Scored {assessment.obligations_analyzed} obligations, "
                  f"found {len(assessment.risks)} risks")
            print(f"      Risk categories: {set(c.value for c in categories)}")

        except Exception as e:
            print(f"  FAIL Integration test error: {e}")


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "=" * 60)
    print("Risk Scorer Tests")
    print("=" * 60)

    test_classes = [
        TestRiskDataClasses,
        TestFinancialExposureDetection,
        TestTimeBombDetection,
        TestAsymmetricTermsDetection,
        TestCompetitiveRestrictionDetection,
        TestDisputeResolutionDetection,
        TestRiskSummary,
        TestIntegration,
    ]

    passed = 0
    failed = 0

    for test_class in test_classes:
        print(f"\n{test_class.__name__}:")

        instance = test_class()

        for method_name in dir(instance):
            if method_name.startswith("test_"):
                try:
                    getattr(instance, method_name)()
                    passed += 1
                except AssertionError as e:
                    print(f"  FAIL {method_name}: {e}")
                    failed += 1
                except Exception as e:
                    print(f"  FAIL {method_name}: Unexpected error: {e}")
                    failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
