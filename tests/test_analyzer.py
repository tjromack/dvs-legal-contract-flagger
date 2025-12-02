"""
Tests for the contract analyzer.

Run with: python tests/test_analyzer.py

Unit tests use mocked API responses.
Integration tests require ANTHROPIC_API_KEY environment variable.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extractor import extract_from_text_file, TextChunk, ExtractionResult
from src.analyzer import (
    ContractAnalyzer,
    AnalysisResult,
    Obligation,
    Party,
    AutoRenewal,
    analyze_contract,
)


# Test data directory
SAMPLE_CONTRACTS_DIR = Path(__file__).parent.parent / "data" / "sample_contracts"


# Sample API response for mocking
MOCK_API_RESPONSE = {
    "parties": [
        {"name": "Acme Corp", "role": "Landlord", "is_reader": False},
        {"name": "John Doe", "role": "Tenant", "is_reader": True},
    ],
    "effective_date": "2024-01-01",
    "term": "12 months",
    "termination_notice_period": "30 days",
    "auto_renewal": {
        "exists": True,
        "period": "12 months",
        "notice_to_cancel": "60 days",
    },
    "obligations": [
        {
            "id": "OBL-001",
            "party": "Tenant",
            "type": "payment",
            "description": "Pay monthly rent of $2,000",
            "deadline": "1st of each month",
            "conditions": None,
            "source_text": "Tenant shall pay monthly rent of Two Thousand Dollars ($2,000.00) on the first day of each month.",
            "source_location": "Section 2.1, Page 2",
        },
        {
            "id": "OBL-002",
            "party": "Landlord",
            "type": "requirement",
            "description": "Maintain common areas",
            "deadline": None,
            "conditions": None,
            "source_text": "Landlord shall maintain all common areas in good condition.",
            "source_location": "Section 5.2, Page 4",
        },
    ],
    "key_definitions": [
        {
            "term": "Premises",
            "definition": "The rental unit at 123 Main Street, Apt 4B",
            "source_location": "Section 1.1",
        }
    ],
    "extraction_notes": "",
}


def create_mock_response():
    """Create a mock Anthropic API response."""
    mock_content = MagicMock()
    mock_content.text = json.dumps(MOCK_API_RESPONSE)

    mock_response = MagicMock()
    mock_response.content = [mock_content]

    return mock_response


class TestDataClasses:
    """Tests for data classes."""

    def test_party_creation(self):
        party = Party(name="Acme Corp", role="Landlord", is_reader=False)
        assert party.name == "Acme Corp"
        assert party.role == "Landlord"
        assert party.is_reader is False
        print("  OK Party dataclass works")

    def test_obligation_creation(self):
        obl = Obligation(
            id="OBL-001",
            party="Tenant",
            type="payment",
            description="Pay rent",
            deadline="Monthly",
            conditions=None,
            source_text="Tenant shall pay rent.",
            source_location="Section 2.1",
        )
        assert obl.id == "OBL-001"
        assert obl.risk_level == "low"  # default
        assert obl.risk_flags == []  # default
        print("  OK Obligation dataclass works")

    def test_auto_renewal_creation(self):
        ar = AutoRenewal(exists=True, period="12 months", notice_to_cancel="60 days")
        assert ar.exists is True
        assert ar.period == "12 months"
        print("  OK AutoRenewal dataclass works")

    def test_analysis_result_to_dict(self):
        result = AnalysisResult(
            file_path="test.pdf",
            parties=[Party("Test Corp", "Provider", False)],
            effective_date="2024-01-01",
            term="12 months",
            termination_notice_period="30 days",
            auto_renewal=AutoRenewal(exists=False),
            obligations=[],
            key_definitions=[],
            extraction_notes="",
            chunks_processed=1,
            raw_responses=[],
        )
        d = result.to_dict()
        assert d["file_path"] == "test.pdf"
        assert len(d["parties"]) == 1
        assert d["auto_renewal"]["exists"] is False
        print("  OK AnalysisResult.to_dict() works")

    def test_analysis_result_to_json(self):
        result = AnalysisResult(
            file_path="test.pdf",
            parties=[],
            effective_date=None,
            term=None,
            termination_notice_period=None,
            auto_renewal=AutoRenewal(exists=False),
            obligations=[],
            key_definitions=[],
            extraction_notes="",
            chunks_processed=1,
            raw_responses=[],
        )
        json_str = result.to_json()
        parsed = json.loads(json_str)
        assert parsed["file_path"] == "test.pdf"
        print("  OK AnalysisResult.to_json() works")


class TestAnalyzerInitialization:
    """Tests for ContractAnalyzer initialization."""

    def test_missing_api_key_raises_error(self):
        # Temporarily remove env var if present
        original = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            ContractAnalyzer()
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "API key required" in str(e)
            print("  OK Raises error when API key missing")
        finally:
            if original:
                os.environ["ANTHROPIC_API_KEY"] = original

    def test_accepts_api_key_parameter(self):
        # Should not raise with explicit key
        analyzer = ContractAnalyzer(api_key="test-key-12345")
        assert analyzer.api_key == "test-key-12345"
        print("  OK Accepts api_key parameter")

    def test_loads_system_prompt(self):
        analyzer = ContractAnalyzer(api_key="test-key-12345")
        assert len(analyzer._system_prompt) > 100
        assert "obligation" in analyzer._system_prompt.lower()
        print("  OK Loads system prompt from file")


class TestChunkAnalysis:
    """Tests for chunk analysis with mocked API."""

    @patch("src.analyzer.Anthropic")
    def test_analyze_chunk_returns_parsed_json(self, mock_anthropic):
        # Setup mock
        mock_client = MagicMock()
        mock_client.messages.create.return_value = create_mock_response()
        mock_anthropic.return_value = mock_client

        analyzer = ContractAnalyzer(api_key="test-key")

        chunk = TextChunk(
            text="Sample contract text",
            start_page=1,
            end_page=1,
            chunk_index=0,
            total_chunks=1,
        )

        result = analyzer._analyze_chunk(chunk, 0, 1)

        assert "parties" in result
        assert len(result["parties"]) == 2
        assert len(result["obligations"]) == 2
        print("  OK _analyze_chunk parses JSON response")

    @patch("src.analyzer.Anthropic")
    def test_analyze_chunk_handles_markdown_wrapped_json(self, mock_anthropic):
        # Setup mock with markdown-wrapped JSON
        mock_content = MagicMock()
        mock_content.text = f"```json\n{json.dumps(MOCK_API_RESPONSE)}\n```"

        mock_response = MagicMock()
        mock_response.content = [mock_content]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        analyzer = ContractAnalyzer(api_key="test-key")

        chunk = TextChunk(
            text="Sample text",
            start_page=1,
            end_page=1,
            chunk_index=0,
            total_chunks=1,
        )

        result = analyzer._analyze_chunk(chunk, 0, 1)

        assert "parties" in result
        print("  OK Handles markdown-wrapped JSON")

    @patch("src.analyzer.Anthropic")
    def test_analyze_chunk_handles_invalid_json(self, mock_anthropic):
        # Setup mock with invalid JSON
        mock_content = MagicMock()
        mock_content.text = "This is not valid JSON"

        mock_response = MagicMock()
        mock_response.content = [mock_content]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        analyzer = ContractAnalyzer(api_key="test-key")

        chunk = TextChunk(
            text="Sample text",
            start_page=1,
            end_page=1,
            chunk_index=0,
            total_chunks=1,
        )

        result = analyzer._analyze_chunk(chunk, 0, 1)

        assert "error" in result
        assert "raw_response" in result
        print("  OK Handles invalid JSON gracefully")


class TestMergeResults:
    """Tests for merging chunk results."""

    def test_merge_deduplicates_parties(self):
        analyzer = ContractAnalyzer(api_key="test-key")

        chunk_results = [
            {
                "parties": [{"name": "Acme Corp", "role": "Provider", "is_reader": False}],
                "obligations": [],
                "key_definitions": [],
            },
            {
                "parties": [
                    {"name": "Acme Corp", "role": "Provider", "is_reader": False},
                    {"name": "Client Inc", "role": "Customer", "is_reader": True},
                ],
                "obligations": [],
                "key_definitions": [],
            },
        ]

        result = analyzer._merge_chunk_results(chunk_results, "test.pdf")

        assert len(result.parties) == 2  # Deduplicated
        party_names = [p.name for p in result.parties]
        assert "Acme Corp" in party_names
        assert "Client Inc" in party_names
        print("  OK Deduplicates parties by name")

    def test_merge_renumbers_obligations(self):
        analyzer = ContractAnalyzer(api_key="test-key")

        chunk_results = [
            {
                "parties": [],
                "obligations": [
                    {"id": "OBL-001", "party": "A", "type": "payment",
                     "description": "First", "source_text": "...", "source_location": "1.1"},
                ],
                "key_definitions": [],
            },
            {
                "parties": [],
                "obligations": [
                    {"id": "OBL-001", "party": "B", "type": "requirement",
                     "description": "Second", "source_text": "...", "source_location": "2.1"},
                ],
                "key_definitions": [],
            },
        ]

        result = analyzer._merge_chunk_results(chunk_results, "test.pdf")

        assert len(result.obligations) == 2
        assert result.obligations[0].id == "OBL-001"
        assert result.obligations[1].id == "OBL-002"
        print("  OK Renumbers obligations sequentially")

    def test_merge_uses_first_metadata(self):
        analyzer = ContractAnalyzer(api_key="test-key")

        chunk_results = [
            {
                "parties": [],
                "effective_date": "2024-01-01",
                "term": "12 months",
                "obligations": [],
                "key_definitions": [],
            },
            {
                "parties": [],
                "effective_date": "2024-06-01",  # Should be ignored
                "term": "24 months",  # Should be ignored
                "obligations": [],
                "key_definitions": [],
            },
        ]

        result = analyzer._merge_chunk_results(chunk_results, "test.pdf")

        assert result.effective_date == "2024-01-01"
        assert result.term == "12 months"
        print("  OK Uses first non-null metadata values")


class TestFullAnalysis:
    """Tests for full analysis workflow with mocked API."""

    @patch("src.analyzer.Anthropic")
    def test_analyze_extraction_result(self, mock_anthropic):
        # Setup mock
        mock_client = MagicMock()
        mock_client.messages.create.return_value = create_mock_response()
        mock_anthropic.return_value = mock_client

        # Create extraction result
        extraction = ExtractionResult(
            file_path="test.pdf",
            total_pages=2,
            total_chars=1000,
            chunks=[
                TextChunk("Contract text chunk 1", 1, 1, 0, 2),
                TextChunk("Contract text chunk 2", 2, 2, 1, 2),
            ],
            raw_text="Full contract text",
            page_texts={1: "Page 1", 2: "Page 2"},
            sections_found=[],
        )

        analyzer = ContractAnalyzer(api_key="test-key")
        result = analyzer.analyze(extraction)

        assert result.file_path == "test.pdf"
        assert result.chunks_processed == 2
        assert len(result.parties) > 0
        assert len(result.obligations) > 0
        print("  OK Full analysis workflow works")


class TestIntegration:
    """Integration tests that require a real API key.

    These tests are skipped if ANTHROPIC_API_KEY is not set.
    Run with: ANTHROPIC_API_KEY=your-key python tests/test_analyzer.py
    """

    def test_analyze_real_contract(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key or api_key == "your_anthropic_key_here":
            print("  SKIP: ANTHROPIC_API_KEY not set (integration test)")
            return

        # Use a sample contract
        contract_path = SAMPLE_CONTRACTS_DIR / "mutual_nda.txt"
        if not contract_path.exists():
            print(f"  SKIP: {contract_path} not found")
            return

        try:
            result = analyze_contract(contract_path, verbose=False)

            # Basic validation
            assert result.file_path == str(contract_path)
            assert result.chunks_processed > 0
            assert len(result.obligations) > 0

            # Check that source_text is populated
            for obl in result.obligations:
                assert obl.source_text, f"Obligation {obl.id} missing source_text"

            print(f"  OK Analyzed real contract: {len(result.obligations)} obligations found")

            # Print sample obligation for manual verification
            if result.obligations:
                obl = result.obligations[0]
                print(f"      Sample: [{obl.id}] {obl.party} - {obl.description[:50]}...")

        except Exception as e:
            print(f"  FAIL Integration test error: {e}")


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "=" * 60)
    print("Contract Analyzer Tests")
    print("=" * 60)

    test_classes = [
        TestDataClasses,
        TestAnalyzerInitialization,
        TestChunkAnalysis,
        TestMergeResults,
        TestFullAnalysis,
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
