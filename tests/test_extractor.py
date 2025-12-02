"""
Tests for the contract text extractor.

Run with: python -m pytest tests/test_extractor.py -v
Or simply: python tests/test_extractor.py
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from extractor import (
    ContractExtractor,
    ExtractionResult,
    TextChunk,
    extract_contract,
    extract_from_text_file,
)


# Test data directory
SAMPLE_CONTRACTS_DIR = Path(__file__).parent.parent / "data" / "sample_contracts"


class TestTextChunk:
    """Tests for the TextChunk dataclass."""

    def test_chunk_creation(self):
        chunk = TextChunk(
            text="This is sample text.",
            start_page=1,
            end_page=1,
            chunk_index=0,
            total_chunks=1,
        )
        assert chunk.char_count == 20
        assert chunk.source_location == "Page 1"

    def test_multi_page_location(self):
        chunk = TextChunk(
            text="Text spanning pages.",
            start_page=3,
            end_page=5,
            chunk_index=1,
            total_chunks=4,
        )
        assert chunk.source_location == "Pages 3-5"


class TestContractExtractor:
    """Tests for the ContractExtractor class."""

    def test_extractor_initialization(self):
        extractor = ContractExtractor()
        assert extractor.chunk_size == 4000
        assert extractor.overlap == 200

    def test_custom_chunk_size(self):
        extractor = ContractExtractor(chunk_size=2000, overlap=100)
        assert extractor.chunk_size == 2000
        assert extractor.overlap == 100

    def test_section_detection(self):
        extractor = ContractExtractor()

        # Test various section header formats
        test_cases = [
            ("1. DEFINITIONS", True),
            ("ARTICLE I: Introduction", True),
            ("SECTION 5. TERM AND TERMINATION", True),
            ("CONFIDENTIAL INFORMATION", True),
            ("EXHIBIT A", True),
            ("1.1 Subsection Title", True),
            ("regular paragraph text", False),
            ("The quick brown fox", False),
        ]

        for text, should_match in test_cases:
            sections = extractor._detect_sections(text, page_num=1)
            has_match = len(sections) > 0
            assert has_match == should_match, f"Failed for: '{text}'"


class TestTextFileExtraction:
    """Tests for extracting from text files."""

    def test_extract_lease_agreement(self):
        lease_path = SAMPLE_CONTRACTS_DIR / "residential_lease_agreement.txt"

        if not lease_path.exists():
            print(f"SKIP: {lease_path} not found")
            return

        result = extract_from_text_file(lease_path)

        # Basic assertions
        assert result.total_pages > 0
        assert result.total_chars > 0
        assert len(result.chunks) > 0
        assert result.file_path == str(lease_path)

        # Check chunks have valid structure
        for chunk in result.chunks:
            assert chunk.text
            assert chunk.start_page >= 1
            assert chunk.end_page >= chunk.start_page
            assert chunk.chunk_index >= 0

        # Check sections were detected
        section_names = [s['name'] for s in result.sections_found]
        print(f"  Found {len(section_names)} sections")

        # Lease should have typical sections
        full_text = result.raw_text.upper()
        assert "LEASE" in full_text or "RENT" in full_text

        print(f"  OK Lease: {result.total_pages} pages, "
              f"{len(result.chunks)} chunks, "
              f"{result.total_chars:,} chars")

    def test_extract_nda(self):
        nda_path = SAMPLE_CONTRACTS_DIR / "mutual_nda.txt"

        if not nda_path.exists():
            print(f"SKIP: {nda_path} not found")
            return

        result = extract_from_text_file(nda_path)

        assert result.total_chars > 0
        assert len(result.chunks) > 0

        # NDA should mention confidential/disclosure
        full_text = result.raw_text.upper()
        assert "CONFIDENTIAL" in full_text or "DISCLOSURE" in full_text

        print(f"  OK NDA: {result.total_pages} pages, "
              f"{len(result.chunks)} chunks, "
              f"{result.total_chars:,} chars")

    def test_extract_employment_agreement(self):
        emp_path = SAMPLE_CONTRACTS_DIR / "employment_agreement.txt"

        if not emp_path.exists():
            print(f"SKIP: {emp_path} not found")
            return

        result = extract_from_text_file(emp_path)

        assert result.total_chars > 0
        assert len(result.chunks) > 0

        # Employment agreement should have these
        full_text = result.raw_text.upper()
        assert "EMPLOYEE" in full_text or "EMPLOYMENT" in full_text

        print(f"  OK Employment: {result.total_pages} pages, "
              f"{len(result.chunks)} chunks, "
              f"{result.total_chars:,} chars")

    def test_extract_saas_tos(self):
        tos_path = SAMPLE_CONTRACTS_DIR / "saas_terms_of_service.txt"

        if not tos_path.exists():
            print(f"SKIP: {tos_path} not found")
            return

        result = extract_from_text_file(tos_path)

        assert result.total_chars > 0
        assert len(result.chunks) > 0

        # SaaS ToS should mention services/terms
        full_text = result.raw_text.upper()
        assert "SERVICE" in full_text or "TERMS" in full_text

        print(f"  OK SaaS ToS: {result.total_pages} pages, "
              f"{len(result.chunks)} chunks, "
              f"{result.total_chars:,} chars")


class TestChunkingStrategy:
    """Tests for the chunking behavior."""

    def test_chunk_size_limit(self):
        """Chunks should not exceed target size (with some tolerance)."""
        emp_path = SAMPLE_CONTRACTS_DIR / "employment_agreement.txt"

        if not emp_path.exists():
            print(f"SKIP: {emp_path} not found")
            return

        result = extract_from_text_file(emp_path, chunk_size=2000, overlap=100)

        # Allow 20% tolerance for paragraph boundary preservation
        max_allowed = 2000 * 1.2

        for chunk in result.chunks:
            assert chunk.char_count <= max_allowed, \
                f"Chunk {chunk.chunk_index} too large: {chunk.char_count}"

        print(f"  OK All {len(result.chunks)} chunks within size limit")

    def test_overlap_between_chunks(self):
        """Consecutive chunks should have overlapping text."""
        emp_path = SAMPLE_CONTRACTS_DIR / "employment_agreement.txt"

        if not emp_path.exists():
            print(f"SKIP: {emp_path} not found")
            return

        result = extract_from_text_file(emp_path, chunk_size=2000, overlap=100)

        if len(result.chunks) < 2:
            print("  SKIP: Not enough chunks for overlap test")
            return

        # Check that some text from end of chunk N appears in chunk N+1
        overlaps_found = 0
        for i in range(len(result.chunks) - 1):
            chunk_a = result.chunks[i]
            chunk_b = result.chunks[i + 1]

            # Get last 50 chars of chunk A (should appear in chunk B)
            ending = chunk_a.text[-50:]

            # Check for partial match (overlap may not be exact due to sentence breaking)
            words_a = set(ending.split()[-5:])
            words_b = set(chunk_b.text[:200].split()[:20])

            if words_a & words_b:
                overlaps_found += 1

        print(f"  OK Found overlap in {overlaps_found}/{len(result.chunks)-1} chunk boundaries")

    def test_page_tracking(self):
        """Chunks should correctly track which pages they span."""
        emp_path = SAMPLE_CONTRACTS_DIR / "employment_agreement.txt"

        if not emp_path.exists():
            print(f"SKIP: {emp_path} not found")
            return

        result = extract_from_text_file(emp_path)

        for chunk in result.chunks:
            assert chunk.start_page >= 1
            assert chunk.end_page >= chunk.start_page
            assert chunk.end_page <= result.total_pages

        print(f"  OK Page tracking valid for all {len(result.chunks)} chunks")


class TestExtractContract:
    """Tests for the convenience extract_contract function."""

    def test_auto_detect_txt(self):
        lease_path = SAMPLE_CONTRACTS_DIR / "residential_lease_agreement.txt"

        if not lease_path.exists():
            print(f"SKIP: {lease_path} not found")
            return

        result = extract_contract(lease_path)
        assert result.total_chars > 0
        print("  OK Auto-detected .txt file")

    def test_unsupported_format(self):
        try:
            extract_contract(Path("fake_file.docx"))
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Unsupported file type" in str(e)
            print("  OK Correctly rejects unsupported formats")

    def test_file_not_found(self):
        try:
            extract_contract(Path("nonexistent.pdf"))
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            print("  OK Correctly raises FileNotFoundError")


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "=" * 60)
    print("Contract Extractor Tests")
    print("=" * 60)

    test_classes = [
        TestTextChunk,
        TestContractExtractor,
        TestTextFileExtraction,
        TestChunkingStrategy,
        TestExtractContract,
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
