"""
Tests for the source text verification module.

Run with: python tests/test_verifier.py
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.verifier import (
    SourceVerifier,
    VerificationResult,
    VerificationStatus,
    DocumentVerificationReport,
    verify_analysis,
)
from src.extractor import ExtractionResult


# Test data directory
SAMPLE_CONTRACTS_DIR = Path(__file__).parent.parent / "data" / "sample_contracts"


def create_mock_obligation(
    id: str,
    source_text: str,
    source_location: str = "Section 1.1",
):
    """Create a mock obligation for testing."""
    mock = MagicMock()
    mock.id = id
    mock.source_text = source_text
    mock.source_location = source_location
    return mock


def create_mock_analysis(obligations: list):
    """Create a mock analysis result."""
    mock = MagicMock()
    mock.file_path = "test.pdf"
    mock.obligations = obligations
    return mock


def create_mock_extraction(raw_text: str):
    """Create a mock extraction result."""
    mock = MagicMock()
    mock.raw_text = raw_text
    return mock


class TestVerificationResult:
    """Tests for VerificationResult dataclass."""

    def test_verified_result(self):
        result = VerificationResult(
            obligation_id="OBL-001",
            status=VerificationStatus.VERIFIED,
            confidence=1.0,
            source_text="Test text",
            matched_text="Test text",
            match_location="Page 1",
            issues=[],
        )
        assert result.is_verified is True
        assert result.is_hallucination is False
        print("  OK Verified result properties correct")

    def test_partial_result(self):
        result = VerificationResult(
            obligation_id="OBL-002",
            status=VerificationStatus.PARTIAL,
            confidence=0.75,
            source_text="Test text",
            matched_text="Test",
            match_location="Page 2",
            issues=["Partial match"],
        )
        assert result.is_verified is True  # Partial counts as verified
        assert result.is_hallucination is False
        print("  OK Partial result properties correct")

    def test_unverified_result(self):
        result = VerificationResult(
            obligation_id="OBL-003",
            status=VerificationStatus.UNVERIFIED,
            confidence=0.3,
            source_text="Fake text",
            matched_text=None,
            match_location=None,
            issues=["POSSIBLE HALLUCINATION"],
        )
        assert result.is_verified is False
        assert result.is_hallucination is True
        print("  OK Unverified/hallucination result correct")

    def test_to_dict(self):
        result = VerificationResult(
            obligation_id="OBL-001",
            status=VerificationStatus.VERIFIED,
            confidence=0.95,
            source_text="Test",
            matched_text="Test",
            match_location="Page 1",
            issues=[],
        )
        d = result.to_dict()
        assert d["status"] == "verified"
        assert d["confidence"] == 0.95
        assert d["is_verified"] is True
        print("  OK to_dict() works")


class TestDocumentVerificationReport:
    """Tests for DocumentVerificationReport."""

    def test_verification_rate(self):
        results = [
            VerificationResult("1", VerificationStatus.VERIFIED, 1.0, "a", "a", "", []),
            VerificationResult("2", VerificationStatus.VERIFIED, 0.9, "b", "b", "", []),
            VerificationResult("3", VerificationStatus.PARTIAL, 0.75, "c", "c", "", []),
            VerificationResult("4", VerificationStatus.UNVERIFIED, 0.3, "d", None, None, []),
        ]
        report = DocumentVerificationReport(
            file_path="test.pdf",
            total_obligations=4,
            verified_count=2,
            partial_count=1,
            unverified_count=1,
            empty_count=0,
            results=results,
        )
        assert report.verification_rate == 0.75  # 3/4 verified
        print("  OK Verification rate calculated correctly")

    def test_has_hallucinations(self):
        results = [
            VerificationResult("1", VerificationStatus.VERIFIED, 1.0, "a", "a", "", []),
            VerificationResult("2", VerificationStatus.UNVERIFIED, 0.2, "b", None, None, []),
        ]
        report = DocumentVerificationReport(
            file_path="test.pdf",
            total_obligations=2,
            verified_count=1,
            partial_count=0,
            unverified_count=1,
            empty_count=0,
            results=results,
        )
        assert report.has_hallucinations is True
        assert len(report.hallucinations) == 1
        print("  OK Hallucination detection works")


class TestExactMatch:
    """Tests for exact text matching."""

    def test_exact_match(self):
        verifier = SourceVerifier()
        document = "This is a contract. The tenant shall pay rent monthly. End of contract."

        result = verifier.verify_source_text(
            obligation_id="OBL-001",
            source_text="The tenant shall pay rent monthly.",
            document_text=document,
        )

        assert result.status == VerificationStatus.VERIFIED
        assert result.confidence == 1.0
        print("  OK Exact match verified with 100% confidence")

    def test_exact_match_case_sensitive(self):
        verifier = SourceVerifier()
        document = "The Tenant shall pay rent."

        result = verifier.verify_source_text(
            obligation_id="OBL-001",
            source_text="The Tenant shall pay rent.",
            document_text=document,
        )

        assert result.status == VerificationStatus.VERIFIED
        assert result.confidence == 1.0
        print("  OK Case-sensitive exact match works")


class TestNormalizedMatch:
    """Tests for normalized text matching."""

    def test_whitespace_normalization(self):
        verifier = SourceVerifier()
        document = "The tenant  shall   pay rent\nmonthly."

        result = verifier.verify_source_text(
            obligation_id="OBL-001",
            source_text="The tenant shall pay rent monthly.",
            document_text=document,
        )

        assert result.status == VerificationStatus.VERIFIED
        assert result.confidence >= 0.9
        print("  OK Whitespace differences normalized")

    def test_case_insensitive_match(self):
        verifier = SourceVerifier()
        document = "THE TENANT SHALL PAY RENT MONTHLY."

        result = verifier.verify_source_text(
            obligation_id="OBL-001",
            source_text="the tenant shall pay rent monthly.",
            document_text=document,
        )

        assert result.status == VerificationStatus.VERIFIED
        print("  OK Case-insensitive matching works")


class TestFuzzyMatch:
    """Tests for fuzzy text matching."""

    def test_minor_differences(self):
        verifier = SourceVerifier()
        document = "The tenant shall pay monthly rent of $1,000."

        result = verifier.verify_source_text(
            obligation_id="OBL-001",
            source_text="The tenant shall pay monthly rent of $1000.",  # Missing comma
            document_text=document,
        )

        assert result.status == VerificationStatus.VERIFIED
        assert result.confidence >= 0.85
        print("  OK Minor differences fuzzy matched")

    def test_word_order_variation(self):
        verifier = SourceVerifier()
        document = "Tenant agrees to pay rent on the first of each month."

        result = verifier.verify_source_text(
            obligation_id="OBL-001",
            source_text="Tenant agrees to pay rent on the 1st of each month.",
            document_text=document,
        )

        # Should still find a reasonable match
        assert result.confidence >= 0.7
        print("  OK Word variations handled")


class TestPartialMatch:
    """Tests for partial matching."""

    def test_partial_text_found(self):
        verifier = SourceVerifier()
        document = "The complete sentence is: Tenant shall pay rent of $2,000 per month."

        result = verifier.verify_source_text(
            obligation_id="OBL-001",
            source_text="Tenant shall pay rent of $2,000 per month on the first day.",  # Extra text
            document_text=document,
        )

        # Should find partial match
        assert result.status in (VerificationStatus.VERIFIED, VerificationStatus.PARTIAL)
        print("  OK Partial text matching works")

    def test_key_phrase_matching(self):
        verifier = SourceVerifier()
        document = "Payment terms: The amount of $5,000 is due on 12/31/2024."

        result = verifier.verify_source_text(
            obligation_id="OBL-001",
            source_text='Pay "$5,000" by the date of "12/31/2024".',
            document_text=document,
        )

        # Should find key phrases like dollar amount and date
        assert result.confidence > 0.3
        print("  OK Key phrase extraction works")


class TestHallucinationDetection:
    """Tests for hallucination detection."""

    def test_detects_hallucinated_text(self):
        verifier = SourceVerifier()
        document = "This is a simple rental agreement. The tenant pays $1,000 monthly."

        result = verifier.verify_source_text(
            obligation_id="OBL-001",
            source_text="The landlord shall provide free parking and utilities.",  # Not in document
            document_text=document,
        )

        assert result.status == VerificationStatus.UNVERIFIED
        assert result.is_hallucination is True
        assert any("HALLUCINATION" in issue for issue in result.issues)
        print("  OK Hallucination detected correctly")

    def test_completely_different_text(self):
        verifier = SourceVerifier()
        document = "Agreement for sale of goods. Buyer agrees to purchase items."

        result = verifier.verify_source_text(
            obligation_id="OBL-001",
            source_text="Employee shall not compete with employer for 24 months.",
            document_text=document,
        )

        assert result.status == VerificationStatus.UNVERIFIED
        assert result.confidence < 0.5
        print("  OK Completely different text marked unverified")


class TestEmptyInputs:
    """Tests for handling empty inputs."""

    def test_empty_source_text(self):
        verifier = SourceVerifier()

        result = verifier.verify_source_text(
            obligation_id="OBL-001",
            source_text="",
            document_text="Some document text.",
        )

        assert result.status == VerificationStatus.EMPTY
        print("  OK Empty source text handled")

    def test_whitespace_only_source(self):
        verifier = SourceVerifier()

        result = verifier.verify_source_text(
            obligation_id="OBL-001",
            source_text="   \n\t  ",
            document_text="Some document text.",
        )

        assert result.status == VerificationStatus.EMPTY
        print("  OK Whitespace-only source text handled")

    def test_empty_document(self):
        verifier = SourceVerifier()

        result = verifier.verify_source_text(
            obligation_id="OBL-001",
            source_text="Some obligation text.",
            document_text="",
        )

        assert result.status == VerificationStatus.SKIPPED
        print("  OK Empty document handled")


class TestFullVerification:
    """Tests for full document verification."""

    def test_verify_multiple_obligations(self):
        verifier = SourceVerifier()

        document = """
        RENTAL AGREEMENT

        1. RENT
        Tenant shall pay monthly rent of $2,000 on the first of each month.

        2. DEPOSIT
        Tenant shall provide a security deposit of $4,000.

        3. TERM
        This agreement is for a period of 12 months.
        """

        obligations = [
            create_mock_obligation("OBL-001", "Tenant shall pay monthly rent of $2,000"),
            create_mock_obligation("OBL-002", "security deposit of $4,000"),
            create_mock_obligation("OBL-003", "This is hallucinated text not in document"),
        ]

        analysis = create_mock_analysis(obligations)
        extraction = create_mock_extraction(document)

        report = verifier.verify_analysis(analysis, extraction)

        assert report.total_obligations == 3
        assert report.verified_count >= 2
        assert report.unverified_count >= 1
        assert report.has_hallucinations is True
        print("  OK Multi-obligation verification works")


class TestIntegration:
    """Integration tests with real contracts."""

    def test_verify_real_contract(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key or api_key == "your_anthropic_key_here":
            print("  SKIP: ANTHROPIC_API_KEY not set (integration test)")
            return

        from src.analyzer import analyze_contract
        from src.extractor import extract_contract

        contract_path = SAMPLE_CONTRACTS_DIR / "mutual_nda.txt"
        if not contract_path.exists():
            print(f"  SKIP: {contract_path} not found")
            return

        try:
            extraction = extract_contract(contract_path)
            analysis = analyze_contract(contract_path, verbose=False)
            report = verify_analysis(analysis, extraction)

            print(f"  OK Verified real contract:")
            print(f"      Total: {report.total_obligations}")
            print(f"      Verified: {report.verified_count}")
            print(f"      Partial: {report.partial_count}")
            print(f"      Unverified: {report.unverified_count}")
            print(f"      Rate: {report.verification_rate:.1%}")

            if report.has_hallucinations:
                print(f"      WARNING: {len(report.hallucinations)} possible hallucinations")

        except Exception as e:
            print(f"  FAIL Integration test error: {e}")


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "=" * 60)
    print("Source Verifier Tests")
    print("=" * 60)

    test_classes = [
        TestVerificationResult,
        TestDocumentVerificationReport,
        TestExactMatch,
        TestNormalizedMatch,
        TestFuzzyMatch,
        TestPartialMatch,
        TestHallucinationDetection,
        TestEmptyInputs,
        TestFullVerification,
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
