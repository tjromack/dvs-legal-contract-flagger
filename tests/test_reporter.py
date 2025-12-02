"""
Tests for the report generation module.

Run with: python tests/test_reporter.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.reporter import (
    ContractReporter,
    ContractReport,
    generate_report,
)
from src.risk_scorer import RiskCategory, Severity, RiskFlag, RiskSummary, RiskAssessment
from src.verifier import VerificationResult, VerificationStatus, DocumentVerificationReport


# Test data directory
SAMPLE_CONTRACTS_DIR = Path(__file__).parent.parent / "data" / "sample_contracts"


def create_mock_party(name: str, role: str, is_reader: bool = False):
    """Create a mock party."""
    mock = MagicMock()
    mock.name = name
    mock.role = role
    mock.is_reader = is_reader
    return mock


def create_mock_obligation(
    id: str,
    party: str,
    description: str,
    source_text: str = "Sample source text",
    source_location: str = "Section 1.1",
    type: str = "requirement",
    deadline: str = None,
    conditions: str = None,
):
    """Create a mock obligation."""
    mock = MagicMock()
    mock.id = id
    mock.party = party
    mock.type = type
    mock.description = description
    mock.deadline = deadline
    mock.conditions = conditions
    mock.source_text = source_text
    mock.source_location = source_location
    return mock


def create_mock_auto_renewal(exists: bool, period: str = None, notice: str = None):
    """Create a mock auto-renewal."""
    mock = MagicMock()
    mock.exists = exists
    mock.period = period
    mock.notice_to_cancel = notice
    return mock


def create_mock_analysis():
    """Create a mock analysis result."""
    mock = MagicMock()
    mock.file_path = "test_contract.pdf"
    mock.parties = [
        create_mock_party("Acme Corp", "Provider", False),
        create_mock_party("Client Inc", "Customer", True),
    ]
    mock.effective_date = "2024-01-01"
    mock.term = "12 months"
    mock.termination_notice_period = "30 days"
    mock.auto_renewal = create_mock_auto_renewal(True, "12 months", "60 days")
    mock.obligations = [
        create_mock_obligation("OBL-001", "Client", "Pay monthly fee of $1,000"),
        create_mock_obligation("OBL-002", "Provider", "Deliver services"),
        create_mock_obligation("OBL-003", "Client", "Non-compete for 24 months"),
    ]
    return mock


def create_mock_risk_assessment():
    """Create a mock risk assessment."""
    risks = [
        RiskFlag(
            obligation_id="OBL-003",
            category=RiskCategory.COMPETITIVE_RESTRICTION,
            severity=Severity.HIGH,
            title="Non-compete clause",
            description="24 month non-compete restriction",
            source_text="shall not compete",
            source_location="Section 8.1",
            action_required="Review scope and duration",
            negotiation_suggestion="Reduce to 12 months",
        ),
        RiskFlag(
            obligation_id="OBL-001",
            category=RiskCategory.TIME_BOMB,
            severity=Severity.MEDIUM,
            title="Auto-renewal",
            description="Contract auto-renews",
            source_text="shall automatically renew",
            source_location="Section 10.1",
            action_required="Set calendar reminder",
        ),
    ]
    summary = RiskSummary(
        high_risk_count=1,
        medium_risk_count=1,
        low_risk_count=0,
        most_concerning="Non-compete clause",
        overall_risk_level=Severity.HIGH,
    )
    return RiskAssessment(
        file_path="test_contract.pdf",
        risks=risks,
        summary=summary,
        obligations_analyzed=3,
    )


def create_mock_verification():
    """Create a mock verification report."""
    results = [
        VerificationResult(
            obligation_id="OBL-001",
            status=VerificationStatus.VERIFIED,
            confidence=1.0,
            source_text="Pay monthly fee",
            matched_text="Pay monthly fee",
            match_location="Page 2",
            issues=[],
        ),
        VerificationResult(
            obligation_id="OBL-002",
            status=VerificationStatus.VERIFIED,
            confidence=0.95,
            source_text="Deliver services",
            matched_text="Deliver services",
            match_location="Page 3",
            issues=[],
        ),
        VerificationResult(
            obligation_id="OBL-003",
            status=VerificationStatus.PARTIAL,
            confidence=0.75,
            source_text="shall not compete",
            matched_text="shall not compete with",
            match_location="Page 5",
            issues=["Partial match"],
        ),
    ]
    return DocumentVerificationReport(
        file_path="test_contract.pdf",
        total_obligations=3,
        verified_count=2,
        partial_count=1,
        unverified_count=0,
        empty_count=0,
        results=results,
    )


class TestContractReport:
    """Tests for ContractReport dataclass."""

    def test_to_dict(self):
        report = ContractReport(
            file_path="test.pdf",
            file_name="test.pdf",
            generated_at="2024-01-01T00:00:00",
            parties=[{"name": "Test", "role": "Client", "is_reader": True}],
            effective_date="2024-01-01",
            term="12 months",
            termination_notice_period="30 days",
            auto_renewal={"exists": True, "period": "12 months", "notice_to_cancel": "60 days"},
            obligations=[],
            risk_flags=[],
            risk_summary={"high_risk_count": 0, "medium_risk_count": 0, "low_risk_count": 0, "overall_risk_level": "low"},
            verification_rate=1.0,
            has_hallucinations=False,
            items_needing_review=[],
            summary="Test summary",
        )

        d = report.to_dict()
        assert d["file_path"] == "test.pdf"
        assert d["parties"][0]["name"] == "Test"
        assert d["verification"]["rate"] == 1.0
        print("  OK to_dict() works correctly")

    def test_to_json(self):
        report = ContractReport(
            file_path="test.pdf",
            file_name="test.pdf",
            generated_at="2024-01-01T00:00:00",
            parties=[],
            effective_date=None,
            term=None,
            termination_notice_period=None,
            auto_renewal={"exists": False},
            obligations=[],
            risk_flags=[],
            risk_summary={"overall_risk_level": "low"},
            verification_rate=1.0,
            has_hallucinations=False,
            items_needing_review=[],
            summary="",
        )

        json_str = report.to_json()
        parsed = json.loads(json_str)
        assert parsed["file_path"] == "test.pdf"
        print("  OK to_json() produces valid JSON")


class TestContractReporter:
    """Tests for ContractReporter class."""

    def test_generate_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ContractReporter(tmpdir)

            analysis = create_mock_analysis()
            risk_assessment = create_mock_risk_assessment()
            verification = create_mock_verification()

            report = reporter.generate_report(analysis, risk_assessment, verification)

            assert report.file_name == "test_contract.pdf"
            assert len(report.parties) == 2
            assert len(report.obligations) == 3
            assert len(report.risk_flags) == 2
            print("  OK generate_report() creates complete report")

    def test_obligations_have_risk_levels(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ContractReporter(tmpdir)

            analysis = create_mock_analysis()
            risk_assessment = create_mock_risk_assessment()
            verification = create_mock_verification()

            report = reporter.generate_report(analysis, risk_assessment, verification)

            # OBL-003 should have high risk level (non-compete)
            obl_003 = next(o for o in report.obligations if o["id"] == "OBL-003")
            assert obl_003["risk_level"] == "high"
            assert "Non-compete clause" in obl_003["risk_flags"]
            print("  OK Obligations have correct risk levels")

    def test_items_needing_review(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ContractReporter(tmpdir)

            analysis = create_mock_analysis()
            risk_assessment = create_mock_risk_assessment()
            verification = create_mock_verification()

            report = reporter.generate_report(analysis, risk_assessment, verification)

            # Should have items for high risk and partial match
            assert len(report.items_needing_review) >= 1
            print("  OK Items needing review identified")


class TestReportSaving:
    """Tests for saving reports to files."""

    def test_save_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ContractReporter(tmpdir)

            analysis = create_mock_analysis()
            risk_assessment = create_mock_risk_assessment()
            verification = create_mock_verification()

            report = reporter.generate_report(analysis, risk_assessment, verification)
            json_path = reporter.save_json(report)

            assert json_path.exists()
            assert json_path.suffix == ".json"

            # Verify it's valid JSON
            with open(json_path) as f:
                data = json.load(f)
            assert data["file_name"] == "test_contract.pdf"
            print("  OK JSON report saved correctly")

    def test_save_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ContractReporter(tmpdir)

            analysis = create_mock_analysis()
            risk_assessment = create_mock_risk_assessment()
            verification = create_mock_verification()

            report = reporter.generate_report(analysis, risk_assessment, verification)
            text_path = reporter.save_text(report)

            assert text_path.exists()
            assert text_path.suffix == ".txt"

            content = text_path.read_text()
            assert "CONTRACT ANALYSIS" in content
            assert "test_contract.pdf" in content
            print("  OK Text report saved correctly")

    def test_save_markdown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ContractReporter(tmpdir)

            analysis = create_mock_analysis()
            risk_assessment = create_mock_risk_assessment()
            verification = create_mock_verification()

            report = reporter.generate_report(analysis, risk_assessment, verification)
            md_path = reporter.save_markdown(report)

            assert md_path.exists()
            assert md_path.suffix == ".md"

            content = md_path.read_text()
            assert "# Contract Analysis" in content
            assert "## Risk Flags" in content
            print("  OK Markdown report saved correctly")


class TestTextFormatting:
    """Tests for text report formatting."""

    def test_format_includes_parties(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ContractReporter(tmpdir)

            analysis = create_mock_analysis()
            risk_assessment = create_mock_risk_assessment()
            verification = create_mock_verification()

            report = reporter.generate_report(analysis, risk_assessment, verification)
            text = reporter.format_text_report(report)

            assert "Acme Corp" in text
            assert "Client Inc" in text
            assert "[YOU]" in text  # is_reader marker
            print("  OK Parties formatted correctly")

    def test_format_includes_risks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ContractReporter(tmpdir)

            analysis = create_mock_analysis()
            risk_assessment = create_mock_risk_assessment()
            verification = create_mock_verification()

            report = reporter.generate_report(analysis, risk_assessment, verification)
            text = reporter.format_text_report(report)

            assert "HIGH RISK" in text
            assert "Non-compete" in text
            assert "MEDIUM RISK" in text
            print("  OK Risk flags formatted correctly")

    def test_format_includes_auto_renewal_warning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ContractReporter(tmpdir)

            analysis = create_mock_analysis()
            risk_assessment = create_mock_risk_assessment()
            verification = create_mock_verification()

            report = reporter.generate_report(analysis, risk_assessment, verification)
            text = reporter.format_text_report(report)

            assert "AUTO-RENEWAL" in text
            assert "60 days" in text or "notice" in text.lower()
            print("  OK Auto-renewal warning included")


class TestMarkdownFormatting:
    """Tests for markdown report formatting."""

    def test_markdown_has_structure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ContractReporter(tmpdir)

            analysis = create_mock_analysis()
            risk_assessment = create_mock_risk_assessment()
            verification = create_mock_verification()

            report = reporter.generate_report(analysis, risk_assessment, verification)
            md = reporter.format_markdown_report(report)

            assert "# Contract Analysis" in md
            assert "## Summary" in md
            assert "## Risk Flags" in md
            assert "## Obligations" in md
            print("  OK Markdown has proper structure")

    def test_markdown_has_tables(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ContractReporter(tmpdir)

            analysis = create_mock_analysis()
            risk_assessment = create_mock_risk_assessment()
            verification = create_mock_verification()

            report = reporter.generate_report(analysis, risk_assessment, verification)
            md = reporter.format_markdown_report(report)

            assert "| Field | Value |" in md
            assert "|-------|-------|" in md
            print("  OK Markdown contains tables")


class TestIntegration:
    """Integration tests with real contracts."""

    def test_full_pipeline(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key or api_key == "your_anthropic_key_here":
            print("  SKIP: ANTHROPIC_API_KEY not set (integration test)")
            return

        from src.analyzer import analyze_contract
        from src.extractor import extract_contract
        from src.risk_scorer import score_risks
        from src.verifier import verify_analysis

        contract_path = SAMPLE_CONTRACTS_DIR / "mutual_nda.txt"
        if not contract_path.exists():
            print(f"  SKIP: {contract_path} not found")
            return

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Full pipeline
                extraction = extract_contract(contract_path)
                analysis = analyze_contract(contract_path, verbose=False)
                verification = verify_analysis(analysis, extraction)
                risk_assessment = score_risks(analysis)

                # Generate report
                reporter = ContractReporter(tmpdir)
                report = reporter.generate_report(analysis, risk_assessment, verification)

                # Save all formats
                json_path = reporter.save_json(report)
                text_path = reporter.save_text(report)
                md_path = reporter.save_markdown(report)

                assert json_path.exists()
                assert text_path.exists()
                assert md_path.exists()

                print(f"  OK Full pipeline test passed")
                print(f"      Obligations: {len(report.obligations)}")
                print(f"      Risk flags: {len(report.risk_flags)}")
                print(f"      Verification: {report.verification_rate:.1%}")

        except Exception as e:
            print(f"  FAIL Integration test error: {e}")


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "=" * 60)
    print("Reporter Tests")
    print("=" * 60)

    test_classes = [
        TestContractReport,
        TestContractReporter,
        TestReportSaving,
        TestTextFormatting,
        TestMarkdownFormatting,
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
