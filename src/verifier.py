"""
Source Text Verification Module

Verifies that extracted source_text actually appears in the original document.
This is critical for catching LLM hallucinations - 100% source attribution
accuracy is required.

Verification approaches:
1. Exact match - source_text found verbatim
2. Normalized match - matches after whitespace/punctuation normalization
3. Fuzzy match - high similarity match (for minor LLM paraphrasing)
4. Partial match - significant portion of text found
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path
from typing import Optional

from .extractor import ExtractionResult, extract_contract


class VerificationStatus(Enum):
    """Status of source text verification."""
    VERIFIED = "verified"           # Exact or near-exact match found
    PARTIAL = "partial"             # Partial match found
    UNVERIFIED = "unverified"       # Could not verify - possible hallucination
    EMPTY = "empty"                 # No source text provided
    SKIPPED = "skipped"             # Verification skipped (e.g., no raw text)


@dataclass
class VerificationResult:
    """Result of verifying a single obligation's source text."""
    obligation_id: str
    status: VerificationStatus
    confidence: float  # 0.0 to 1.0
    source_text: str
    matched_text: Optional[str]  # The actual text found in document
    match_location: Optional[str]  # Where in document the match was found
    issues: list[str]  # Any issues or warnings

    @property
    def is_verified(self) -> bool:
        """Returns True if source text was verified."""
        return self.status in (VerificationStatus.VERIFIED, VerificationStatus.PARTIAL)

    @property
    def is_hallucination(self) -> bool:
        """Returns True if this appears to be a hallucination."""
        return self.status == VerificationStatus.UNVERIFIED and self.confidence < 0.5

    def to_dict(self) -> dict:
        return {
            "obligation_id": self.obligation_id,
            "status": self.status.value,
            "confidence": round(self.confidence, 3),
            "source_text": self.source_text,
            "matched_text": self.matched_text,
            "match_location": self.match_location,
            "issues": self.issues,
            "is_verified": self.is_verified,
            "is_hallucination": self.is_hallucination,
        }


@dataclass
class DocumentVerificationReport:
    """Complete verification report for a document."""
    file_path: str
    total_obligations: int
    verified_count: int
    partial_count: int
    unverified_count: int
    empty_count: int
    results: list[VerificationResult]

    @property
    def verification_rate(self) -> float:
        """Percentage of obligations that were verified."""
        verifiable = self.total_obligations - self.empty_count
        if verifiable == 0:
            return 1.0
        return (self.verified_count + self.partial_count) / verifiable

    @property
    def has_hallucinations(self) -> bool:
        """Returns True if any likely hallucinations were detected."""
        return any(r.is_hallucination for r in self.results)

    @property
    def hallucinations(self) -> list[VerificationResult]:
        """Returns list of likely hallucinations."""
        return [r for r in self.results if r.is_hallucination]

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "total_obligations": self.total_obligations,
            "verified_count": self.verified_count,
            "partial_count": self.partial_count,
            "unverified_count": self.unverified_count,
            "empty_count": self.empty_count,
            "verification_rate": round(self.verification_rate, 3),
            "has_hallucinations": self.has_hallucinations,
            "results": [r.to_dict() for r in self.results],
        }


class SourceVerifier:
    """
    Verifies that extracted source text exists in the original document.

    Uses multiple matching strategies:
    1. Exact match (highest confidence)
    2. Normalized match (whitespace/case insensitive)
    3. Fuzzy match (handles minor variations)
    4. Partial match (finds key phrases)
    """

    # Thresholds for matching
    EXACT_MATCH_THRESHOLD = 1.0
    NORMALIZED_MATCH_THRESHOLD = 0.95
    FUZZY_MATCH_THRESHOLD = 0.85
    PARTIAL_MATCH_THRESHOLD = 0.70
    MIN_SOURCE_LENGTH = 10  # Minimum chars for meaningful verification

    def __init__(
        self,
        fuzzy_threshold: float = FUZZY_MATCH_THRESHOLD,
        partial_threshold: float = PARTIAL_MATCH_THRESHOLD,
    ):
        """
        Initialize the verifier.

        Args:
            fuzzy_threshold: Minimum similarity for fuzzy match (0-1)
            partial_threshold: Minimum similarity for partial match (0-1)
        """
        self.fuzzy_threshold = fuzzy_threshold
        self.partial_threshold = partial_threshold

    def verify_analysis(
        self,
        analysis_result,
        extraction_result: ExtractionResult,
    ) -> DocumentVerificationReport:
        """
        Verify all obligations in an analysis result.

        Args:
            analysis_result: AnalysisResult from ContractAnalyzer
            extraction_result: ExtractionResult with the raw document text

        Returns:
            DocumentVerificationReport with verification status for each obligation
        """
        results = []
        verified_count = 0
        partial_count = 0
        unverified_count = 0
        empty_count = 0

        # Get the full document text
        document_text = extraction_result.raw_text

        for obligation in analysis_result.obligations:
            result = self.verify_source_text(
                obligation_id=obligation.id,
                source_text=obligation.source_text,
                document_text=document_text,
                source_location=obligation.source_location,
            )
            results.append(result)

            # Update counts
            if result.status == VerificationStatus.VERIFIED:
                verified_count += 1
            elif result.status == VerificationStatus.PARTIAL:
                partial_count += 1
            elif result.status == VerificationStatus.UNVERIFIED:
                unverified_count += 1
            elif result.status == VerificationStatus.EMPTY:
                empty_count += 1

        return DocumentVerificationReport(
            file_path=analysis_result.file_path,
            total_obligations=len(analysis_result.obligations),
            verified_count=verified_count,
            partial_count=partial_count,
            unverified_count=unverified_count,
            empty_count=empty_count,
            results=results,
        )

    def verify_source_text(
        self,
        obligation_id: str,
        source_text: str,
        document_text: str,
        source_location: Optional[str] = None,
    ) -> VerificationResult:
        """
        Verify a single source text against the document.

        Args:
            obligation_id: ID of the obligation being verified
            source_text: The extracted source text to verify
            document_text: The full document text to search in
            source_location: Optional location hint (e.g., "Section 3.1")

        Returns:
            VerificationResult with status and confidence
        """
        issues = []

        # Handle empty source text
        if not source_text or not source_text.strip():
            return VerificationResult(
                obligation_id=obligation_id,
                status=VerificationStatus.EMPTY,
                confidence=0.0,
                source_text=source_text or "",
                matched_text=None,
                match_location=None,
                issues=["No source text provided"],
            )

        # Handle empty document
        if not document_text or not document_text.strip():
            return VerificationResult(
                obligation_id=obligation_id,
                status=VerificationStatus.SKIPPED,
                confidence=0.0,
                source_text=source_text,
                matched_text=None,
                match_location=None,
                issues=["No document text available for verification"],
            )

        # Warn if source text is very short
        if len(source_text.strip()) < self.MIN_SOURCE_LENGTH:
            issues.append(f"Source text very short ({len(source_text)} chars)")

        # Try each matching strategy in order of strictness
        # 1. Exact match
        if source_text in document_text:
            match_loc = self._find_location(source_text, document_text, source_location)
            return VerificationResult(
                obligation_id=obligation_id,
                status=VerificationStatus.VERIFIED,
                confidence=1.0,
                source_text=source_text,
                matched_text=source_text,
                match_location=match_loc,
                issues=issues,
            )

        # 2. Normalized match (whitespace/case insensitive)
        normalized_source = self._normalize_text(source_text)
        normalized_doc = self._normalize_text(document_text)

        if normalized_source in normalized_doc:
            # Find the actual matched text in original document
            matched = self._find_original_match(source_text, document_text)
            match_loc = self._find_location(matched or source_text, document_text, source_location)
            return VerificationResult(
                obligation_id=obligation_id,
                status=VerificationStatus.VERIFIED,
                confidence=0.95,
                source_text=source_text,
                matched_text=matched,
                match_location=match_loc,
                issues=issues + ["Matched after normalization"],
            )

        # 3. Fuzzy match - find best matching substring
        best_match, similarity = self._fuzzy_find(source_text, document_text)

        if similarity >= self.fuzzy_threshold:
            match_loc = self._find_location(best_match, document_text, source_location)
            return VerificationResult(
                obligation_id=obligation_id,
                status=VerificationStatus.VERIFIED,
                confidence=similarity,
                source_text=source_text,
                matched_text=best_match,
                match_location=match_loc,
                issues=issues + [f"Fuzzy match (similarity: {similarity:.2%})"],
            )

        if similarity >= self.partial_threshold:
            match_loc = self._find_location(best_match, document_text, source_location)
            return VerificationResult(
                obligation_id=obligation_id,
                status=VerificationStatus.PARTIAL,
                confidence=similarity,
                source_text=source_text,
                matched_text=best_match,
                match_location=match_loc,
                issues=issues + [f"Partial match only (similarity: {similarity:.2%})"],
            )

        # 4. Try to find key phrases
        key_phrases = self._extract_key_phrases(source_text)
        phrases_found = 0
        for phrase in key_phrases:
            if phrase.lower() in document_text.lower():
                phrases_found += 1

        if key_phrases and phrases_found / len(key_phrases) >= 0.5:
            return VerificationResult(
                obligation_id=obligation_id,
                status=VerificationStatus.PARTIAL,
                confidence=phrases_found / len(key_phrases) * 0.7,
                source_text=source_text,
                matched_text=None,
                match_location=source_location,
                issues=issues + [f"Found {phrases_found}/{len(key_phrases)} key phrases"],
            )

        # Could not verify - possible hallucination
        return VerificationResult(
            obligation_id=obligation_id,
            status=VerificationStatus.UNVERIFIED,
            confidence=similarity,  # Still report best similarity found
            source_text=source_text,
            matched_text=best_match if similarity > 0.3 else None,
            match_location=None,
            issues=issues + [
                "POSSIBLE HALLUCINATION: Source text not found in document",
                f"Best similarity found: {similarity:.2%}",
            ],
        )

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison (lowercase, collapse whitespace)."""
        # Lowercase
        text = text.lower()
        # Replace various whitespace with single space
        text = re.sub(r'\s+', ' ', text)
        # Remove common punctuation variations
        text = re.sub(r'[""''`]', '"', text)
        text = re.sub(r'[–—]', '-', text)
        return text.strip()

    def _fuzzy_find(self, needle: str, haystack: str) -> tuple[str, float]:
        """
        Find the best fuzzy match for needle in haystack.

        Returns:
            Tuple of (best matching substring, similarity score)
        """
        needle_normalized = self._normalize_text(needle)
        needle_len = len(needle_normalized)

        if needle_len == 0:
            return ("", 0.0)

        best_match = ""
        best_score = 0.0

        # Slide a window through the document
        # Use varying window sizes around the needle length
        haystack_normalized = self._normalize_text(haystack)

        for window_mult in [1.0, 1.2, 1.5, 0.8]:
            window_size = int(needle_len * window_mult)
            if window_size > len(haystack_normalized):
                window_size = len(haystack_normalized)

            step = max(1, window_size // 4)

            for i in range(0, len(haystack_normalized) - window_size + 1, step):
                window = haystack_normalized[i:i + window_size]
                score = SequenceMatcher(None, needle_normalized, window).ratio()

                if score > best_score:
                    best_score = score
                    # Get the original (non-normalized) text
                    best_match = self._get_original_substring(haystack, i, i + window_size)

        return (best_match, best_score)

    def _get_original_substring(self, text: str, norm_start: int, norm_end: int) -> str:
        """
        Map normalized positions back to original text positions.
        This is approximate but works for most cases.
        """
        # Simple approximation: use ratio of positions
        ratio = len(text) / len(self._normalize_text(text)) if text else 1
        orig_start = int(norm_start * ratio)
        orig_end = int(norm_end * ratio)

        # Expand to word boundaries
        while orig_start > 0 and text[orig_start - 1] not in ' \n\t':
            orig_start -= 1
        while orig_end < len(text) and text[orig_end - 1] not in ' \n\t.':
            orig_end += 1

        return text[orig_start:orig_end].strip()

    def _find_original_match(self, source: str, document: str) -> Optional[str]:
        """Find the original text that matches the normalized source."""
        normalized_source = self._normalize_text(source)

        # Split document into sentences and find matching one
        sentences = re.split(r'[.!?]\s+', document)

        for sentence in sentences:
            if self._normalize_text(sentence) == normalized_source:
                return sentence.strip()

            if normalized_source in self._normalize_text(sentence):
                return sentence.strip()

        return None

    def _find_location(
        self,
        text: str,
        document: str,
        hint: Optional[str] = None,
    ) -> str:
        """Determine the location of text in the document."""
        if hint:
            return hint

        # Try to find page markers
        page_pattern = r'\[Page (\d+)\]'
        pages = list(re.finditer(page_pattern, document))

        if not pages:
            return "Unknown location"

        # Find which page the text appears on
        text_pos = document.find(text)
        if text_pos == -1:
            text_pos = document.lower().find(text.lower())

        if text_pos == -1:
            return "Unknown location"

        for i, page_match in enumerate(pages):
            page_start = page_match.end()
            page_end = pages[i + 1].start() if i + 1 < len(pages) else len(document)

            if page_start <= text_pos < page_end:
                return f"Page {page_match.group(1)}"

        return "Unknown location"

    def _extract_key_phrases(self, text: str) -> list[str]:
        """Extract key phrases from text for partial matching."""
        # Split into meaningful chunks
        phrases = []

        # Get quoted phrases
        quoted = re.findall(r'"([^"]+)"', text)
        phrases.extend(quoted)

        # Get dollar amounts
        amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?', text)
        phrases.extend(amounts)

        # Get dates
        dates = re.findall(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', text)
        phrases.extend(dates)

        # Get significant word sequences (3+ words, no common words)
        common_words = {'the', 'a', 'an', 'and', 'or', 'of', 'to', 'in', 'for', 'shall', 'will', 'may'}
        words = text.split()
        for i in range(len(words) - 2):
            chunk = words[i:i + 3]
            if not all(w.lower() in common_words for w in chunk):
                phrases.append(' '.join(chunk))

        return phrases[:10]  # Limit to 10 phrases


def verify_analysis(
    analysis_result,
    extraction_result: ExtractionResult,
) -> DocumentVerificationReport:
    """
    Convenience function to verify an analysis result.

    Args:
        analysis_result: AnalysisResult from ContractAnalyzer
        extraction_result: ExtractionResult with raw document text

    Returns:
        DocumentVerificationReport
    """
    verifier = SourceVerifier()
    return verifier.verify_analysis(analysis_result, extraction_result)


def verify_contract(
    file_path: str | Path,
    analysis_result,
) -> DocumentVerificationReport:
    """
    Convenience function to verify analysis against original file.

    Args:
        file_path: Path to original contract file
        analysis_result: AnalysisResult from ContractAnalyzer

    Returns:
        DocumentVerificationReport
    """
    extraction = extract_contract(file_path)
    verifier = SourceVerifier()
    return verifier.verify_analysis(analysis_result, extraction)


if __name__ == "__main__":
    import json
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.analyzer import analyze_contract
    from src.extractor import extract_contract

    if len(sys.argv) < 2:
        print("Usage: python -m src.verifier <contract_file>")
        print("Set ANTHROPIC_API_KEY environment variable first.")
        sys.exit(1)

    file_path = sys.argv[1]

    try:
        print(f"Extracting text from {file_path}...")
        extraction = extract_contract(file_path)

        print("Analyzing contract...")
        analysis = analyze_contract(file_path, verbose=False)
        print(f"Found {len(analysis.obligations)} obligations")

        print("Verifying source text...")
        report = verify_analysis(analysis, extraction)

        print("\n" + "=" * 60)
        print("VERIFICATION REPORT")
        print("=" * 60)

        print(f"\nFile: {report.file_path}")
        print(f"Total Obligations: {report.total_obligations}")
        print(f"\nVerification Results:")
        print(f"  Verified:   {report.verified_count}")
        print(f"  Partial:    {report.partial_count}")
        print(f"  Unverified: {report.unverified_count}")
        print(f"  Empty:      {report.empty_count}")
        print(f"\nVerification Rate: {report.verification_rate:.1%}")

        if report.has_hallucinations:
            print(f"\n{'='*60}")
            print("WARNING: POSSIBLE HALLUCINATIONS DETECTED")
            print("=" * 60)
            for result in report.hallucinations:
                print(f"\n  [{result.obligation_id}]")
                print(f"    Status: {result.status.value}")
                print(f"    Confidence: {result.confidence:.1%}")
                print(f"    Source Text: \"{result.source_text[:100]}...\"")
                for issue in result.issues:
                    print(f"    - {issue}")
        else:
            print("\nNo hallucinations detected.")

        # Show any partial matches
        partial_results = [r for r in report.results if r.status == VerificationStatus.PARTIAL]
        if partial_results:
            print(f"\n{'='*60}")
            print("PARTIAL MATCHES (Review Recommended)")
            print("=" * 60)
            for result in partial_results[:5]:  # Show first 5
                print(f"\n  [{result.obligation_id}] Confidence: {result.confidence:.1%}")
                for issue in result.issues:
                    print(f"    - {issue}")

        # Save detailed report
        output_file = Path(file_path).stem + "_verification.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"\nFull report saved to: {output_file}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
