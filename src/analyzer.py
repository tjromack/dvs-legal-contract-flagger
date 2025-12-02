"""
Contract Obligation Analyzer

Uses Claude API to extract structured obligations from contract text.
This is Pass 1 of the two-pass processing approach.
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv

from .extractor import ExtractionResult, TextChunk, extract_contract

# Load .env file if present
load_dotenv()


@dataclass
class Party:
    """A party to the contract."""
    name: str
    role: str
    is_reader: bool = False


@dataclass
class Obligation:
    """An extracted obligation from the contract."""
    id: str
    party: str
    type: str  # payment, deadline, restriction, requirement, notification, consent
    description: str
    deadline: Optional[str]
    conditions: Optional[str]
    source_text: str
    source_location: str
    risk_level: str = "low"  # Set by risk_scorer later
    risk_flags: list[str] = field(default_factory=list)


@dataclass
class AutoRenewal:
    """Auto-renewal clause details."""
    exists: bool
    period: Optional[str] = None
    notice_to_cancel: Optional[str] = None


@dataclass
class KeyDefinition:
    """A defined term from the contract."""
    term: str
    definition: str
    source_location: str


@dataclass
class AnalysisResult:
    """Complete analysis result for a contract."""
    file_path: str
    parties: list[Party]
    effective_date: Optional[str]
    term: Optional[str]
    termination_notice_period: Optional[str]
    auto_renewal: AutoRenewal
    obligations: list[Obligation]
    key_definitions: list[KeyDefinition]
    extraction_notes: str
    chunks_processed: int
    raw_responses: list[dict]  # For debugging

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_path": self.file_path,
            "parties": [
                {"name": p.name, "role": p.role, "is_reader": p.is_reader}
                for p in self.parties
            ],
            "effective_date": self.effective_date,
            "term": self.term,
            "termination_notice_period": self.termination_notice_period,
            "auto_renewal": {
                "exists": self.auto_renewal.exists,
                "period": self.auto_renewal.period,
                "notice_to_cancel": self.auto_renewal.notice_to_cancel,
            },
            "obligations": [
                {
                    "id": o.id,
                    "party": o.party,
                    "type": o.type,
                    "description": o.description,
                    "deadline": o.deadline,
                    "conditions": o.conditions,
                    "source_text": o.source_text,
                    "source_location": o.source_location,
                    "risk_level": o.risk_level,
                    "risk_flags": o.risk_flags,
                }
                for o in self.obligations
            ],
            "key_definitions": [
                {
                    "term": d.term,
                    "definition": d.definition,
                    "source_location": d.source_location,
                }
                for d in self.key_definitions
            ],
            "extraction_notes": self.extraction_notes,
            "chunks_processed": self.chunks_processed,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class ContractAnalyzer:
    """
    Analyzes contracts using Claude API to extract obligations.

    Implements Pass 1 of the two-pass processing:
    - Extracts all obligations, commitments, and restrictions
    - Preserves source text for verification
    - Handles multi-chunk documents
    """

    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
    ):
        """
        Initialize the analyzer.

        Args:
            api_key: Anthropic API key. If not provided, reads from
                    ANTHROPIC_API_KEY environment variable.
            model: Claude model to use.
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment "
                "variable or pass api_key parameter."
            )

        self.client = Anthropic(api_key=self.api_key)
        self.model = model
        self._system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """Load the extraction prompt from file."""
        prompt_path = self.PROMPTS_DIR / "extraction.txt"

        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Extraction prompt not found at {prompt_path}. "
                "Please create prompts/extraction.txt"
            )

        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    def analyze(
        self,
        extraction_result: ExtractionResult,
        verbose: bool = False,
    ) -> AnalysisResult:
        """
        Analyze extracted contract text.

        Args:
            extraction_result: Result from ContractExtractor
            verbose: Print progress information

        Returns:
            AnalysisResult with extracted obligations
        """
        if verbose:
            print(f"Analyzing {extraction_result.file_path}")
            print(f"Processing {len(extraction_result.chunks)} chunks...")

        # Process each chunk
        chunk_results = []
        for i, chunk in enumerate(extraction_result.chunks):
            if verbose:
                print(f"  Chunk {i + 1}/{len(extraction_result.chunks)}: "
                      f"{chunk.source_location}...")

            result = self._analyze_chunk(chunk, i, len(extraction_result.chunks))
            chunk_results.append(result)

        # Merge results from all chunks
        merged = self._merge_chunk_results(
            chunk_results,
            extraction_result.file_path,
        )

        if verbose:
            print(f"Extracted {len(merged.obligations)} obligations")

        return merged

    def analyze_file(
        self,
        file_path: str | Path,
        verbose: bool = False,
    ) -> AnalysisResult:
        """
        Convenience method to extract and analyze a file in one step.

        Args:
            file_path: Path to PDF or text file
            verbose: Print progress information

        Returns:
            AnalysisResult with extracted obligations
        """
        extraction = extract_contract(file_path)
        return self.analyze(extraction, verbose=verbose)

    def _analyze_chunk(
        self,
        chunk: TextChunk,
        chunk_index: int,
        total_chunks: int,
    ) -> dict:
        """Analyze a single chunk with Claude."""
        # Build context-aware user message
        context = ""
        if total_chunks > 1:
            context = (
                f"[This is chunk {chunk_index + 1} of {total_chunks} from the contract. "
                f"Source: {chunk.source_location}]\n\n"
            )

        user_message = f"{context}CONTRACT TEXT:\n\n{chunk.text}"

        # Call Claude API
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=self._system_prompt,
            messages=[
                {"role": "user", "content": user_message}
            ],
        )

        # Parse JSON response
        response_text = response.content[0].text

        # Try to extract JSON from response
        try:
            # Handle case where response might have markdown code blocks
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response_text

            return json.loads(json_str)

        except json.JSONDecodeError as e:
            # Return error result if parsing fails
            return {
                "error": f"Failed to parse response: {e}",
                "raw_response": response_text,
                "parties": [],
                "obligations": [],
                "key_definitions": [],
                "extraction_notes": f"JSON parsing error: {e}",
            }

    def _merge_chunk_results(
        self,
        chunk_results: list[dict],
        file_path: str,
    ) -> AnalysisResult:
        """Merge results from multiple chunks into a single result."""
        # Collect all data
        all_parties = {}
        all_obligations = []
        all_definitions = {}
        all_notes = []
        raw_responses = chunk_results.copy()

        # Track the first chunk's metadata (usually has the header info)
        effective_date = None
        term = None
        termination_notice = None
        auto_renewal = AutoRenewal(exists=False)

        obligation_counter = 1

        for result in chunk_results:
            if "error" in result:
                all_notes.append(result.get("extraction_notes", result["error"]))
                continue

            # Parties (deduplicate by name)
            for party_data in result.get("parties", []):
                name = party_data.get("name", "Unknown")
                if name not in all_parties:
                    all_parties[name] = Party(
                        name=name,
                        role=party_data.get("role", "Unknown"),
                        is_reader=party_data.get("is_reader", False),
                    )

            # Metadata (prefer first non-null values)
            if not effective_date and result.get("effective_date"):
                effective_date = result["effective_date"]
            if not term and result.get("term"):
                term = result["term"]
            if not termination_notice and result.get("termination_notice_period"):
                termination_notice = result["termination_notice_period"]

            # Auto-renewal
            ar_data = result.get("auto_renewal", {})
            if ar_data.get("exists") and not auto_renewal.exists:
                auto_renewal = AutoRenewal(
                    exists=True,
                    period=ar_data.get("period"),
                    notice_to_cancel=ar_data.get("notice_to_cancel"),
                )

            # Obligations (renumber to ensure unique IDs)
            for obl_data in result.get("obligations", []):
                obligation = Obligation(
                    id=f"OBL-{obligation_counter:03d}",
                    party=obl_data.get("party", "Unknown"),
                    type=obl_data.get("type", "requirement"),
                    description=obl_data.get("description", ""),
                    deadline=obl_data.get("deadline"),
                    conditions=obl_data.get("conditions"),
                    source_text=obl_data.get("source_text", ""),
                    source_location=obl_data.get("source_location", "Unknown"),
                )
                all_obligations.append(obligation)
                obligation_counter += 1

            # Key definitions (deduplicate by term)
            for def_data in result.get("key_definitions", []):
                term_name = def_data.get("term", "")
                if term_name and term_name not in all_definitions:
                    all_definitions[term_name] = KeyDefinition(
                        term=term_name,
                        definition=def_data.get("definition", ""),
                        source_location=def_data.get("source_location", "Unknown"),
                    )

            # Notes
            if result.get("extraction_notes"):
                all_notes.append(result["extraction_notes"])

        return AnalysisResult(
            file_path=file_path,
            parties=list(all_parties.values()),
            effective_date=effective_date,
            term=term,
            termination_notice_period=termination_notice,
            auto_renewal=auto_renewal,
            obligations=all_obligations,
            key_definitions=list(all_definitions.values()),
            extraction_notes="\n".join(all_notes) if all_notes else "",
            chunks_processed=len(chunk_results),
            raw_responses=raw_responses,
        )


def analyze_contract(
    file_path: str | Path,
    api_key: Optional[str] = None,
    verbose: bool = False,
) -> AnalysisResult:
    """
    Convenience function to analyze a contract file.

    Args:
        file_path: Path to the contract (PDF or TXT)
        api_key: Anthropic API key (optional, uses env var if not provided)
        verbose: Print progress information

    Returns:
        AnalysisResult with extracted obligations
    """
    analyzer = ContractAnalyzer(api_key=api_key)
    return analyzer.analyze_file(file_path, verbose=verbose)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m src.analyzer <contract_file>")
        print("Set ANTHROPIC_API_KEY environment variable first.")
        sys.exit(1)

    file_path = sys.argv[1]

    try:
        result = analyze_contract(file_path, verbose=True)

        print("\n" + "=" * 60)
        print("ANALYSIS RESULTS")
        print("=" * 60)

        print(f"\nFile: {result.file_path}")
        print(f"Chunks processed: {result.chunks_processed}")

        print(f"\nParties ({len(result.parties)}):")
        for party in result.parties:
            reader_tag = " [YOU]" if party.is_reader else ""
            print(f"  - {party.name} ({party.role}){reader_tag}")

        print(f"\nContract Term:")
        print(f"  Effective Date: {result.effective_date or 'Not specified'}")
        print(f"  Term: {result.term or 'Not specified'}")
        print(f"  Termination Notice: {result.termination_notice_period or 'Not specified'}")

        if result.auto_renewal.exists:
            print(f"\n  AUTO-RENEWAL DETECTED:")
            print(f"    Period: {result.auto_renewal.period}")
            print(f"    Notice to Cancel: {result.auto_renewal.notice_to_cancel}")

        print(f"\nObligations ({len(result.obligations)}):")
        for obl in result.obligations:
            print(f"\n  [{obl.id}] {obl.party} - {obl.type.upper()}")
            print(f"    {obl.description}")
            if obl.deadline:
                print(f"    Deadline: {obl.deadline}")
            print(f"    Source: {obl.source_location}")
            # Truncate source text for display
            source_preview = obl.source_text[:100] + "..." if len(obl.source_text) > 100 else obl.source_text
            print(f"    Quote: \"{source_preview}\"")

        if result.extraction_notes:
            print(f"\nNotes: {result.extraction_notes}")

        # Save full JSON output
        output_file = Path(file_path).stem + "_analysis.json"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result.to_json())
        print(f"\nFull results saved to: {output_file}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
