"""
DVS Legal Contract Clause Flagger

An AI system that extracts obligations, deadlines, and risk indicators from
legal contracts, with human-in-the-loop verification for high-stakes clauses.

Usage:
    python main.py --input <contract_file_or_directory> --output <output_directory>

Examples:
    python main.py --input contracts/lease.pdf --output results/
    python main.py --input contracts/ --output results/
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.extractor import extract_contract
from src.analyzer import analyze_contract
from src.risk_scorer import score_risks
from src.verifier import verify_analysis
from src.reporter import ContractReporter

# Load environment variables
load_dotenv()


def print_header(text: str, char: str = "=", width: int = 60) -> None:
    """Print a formatted header."""
    print(char * width)
    print(text)
    print(char * width)


def print_progress(step: str, end: str = "... ") -> None:
    """Print a progress indicator."""
    print(step, end=end, flush=True)


def process_single_file(
    input_path: Path,
    output_dir: Path,
    verbose: bool = False,
) -> bool:
    """
    Process a single contract file through the full pipeline.

    Args:
        input_path: Path to the contract file
        output_dir: Directory to save results
        verbose: Whether to print detailed output

    Returns:
        True if processing succeeded, False otherwise
    """
    file_name = input_path.name

    print(f"\nProcessing: {file_name}")

    try:
        # Step 1: Extract text
        print_progress("Extracting text")
        extraction = extract_contract(input_path)
        print(f"done ({extraction.total_pages} pages)")

        # Step 2: Analyze with LLM (Pass 1)
        print_progress("Pass 1: Extracting obligations")
        analysis = analyze_contract(input_path, verbose=False)
        print(f"done ({len(analysis.obligations)} obligations found)")

        # Step 3: Verify source attribution
        print_progress("Verifying source attribution")
        verification = verify_analysis(analysis, extraction)
        verified_str = f"{verification.verified_count}/{verification.total_obligations}"
        print(f"done ({verified_str} verified)")

        # Step 4: Score risks (Pass 2)
        print_progress("Pass 2: Analyzing risks")
        risk_assessment = score_risks(analysis)
        print("done")

        # Step 5: Generate report
        reporter = ContractReporter(output_dir)
        report = reporter.generate_report(analysis, risk_assessment, verification)

        # Print summary
        print()
        print_summary(report, analysis, risk_assessment, verification)

        # Save reports
        json_path = reporter.save_json(report)
        reporter.save_text(report)  # Also save text summary

        print(f"\nFull report saved to: {json_path}")

        return True

    except FileNotFoundError as e:
        print(f"\nError: File not found - {e}")
        return False

    except ValueError as e:
        print(f"\nError: Invalid input - {e}")
        return False

    except Exception as e:
        print(f"\nError processing {file_name}: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False


def print_summary(report, analysis, risk_assessment, verification) -> None:
    """Print the CLI summary matching README example."""
    print_header("SUMMARY", "=", 44)

    # Document info
    print(f"Document: {report.file_name}")

    # Parties
    if analysis.parties:
        party_strs = []
        for p in analysis.parties:
            if p.is_reader:
                party_strs.append(f"{p.name} (You)")
            else:
                party_strs.append(f"{p.name} ({p.role})")
        # Deduplicate and limit to first 2
        unique_parties = list(dict.fromkeys(party_strs))[:2]
        print(f"Parties: {', '.join(unique_parties)}")

    # Term
    term_parts = []
    if analysis.term:
        term_parts.append(analysis.term)
    if analysis.effective_date:
        term_parts.append(f"starting {analysis.effective_date}")
    if term_parts:
        print(f"Term: {' '.join(term_parts)}")

    print()

    # High Risk Flags
    high_risks = risk_assessment.high_risks
    if high_risks:
        print(f"[HIGH RISK FLAGS] ({len(high_risks)}):")
        for i, risk in enumerate(high_risks[:5], 1):  # Limit to 5
            location = f"({risk.source_location})" if risk.source_location else ""
            print(f"  {i}. {risk.title} {location}")
        if len(high_risks) > 5:
            print(f"  ... and {len(high_risks) - 5} more")
        print()

    # Medium Risk Flags
    medium_risks = risk_assessment.medium_risks
    if medium_risks:
        print(f"[MEDIUM RISK FLAGS] ({len(medium_risks)}):")
        for i, risk in enumerate(medium_risks[:5], 1):  # Limit to 5
            location = f"({risk.source_location})" if risk.source_location else ""
            print(f"  {i}. {risk.title} {location}")
        if len(medium_risks) > 5:
            print(f"  ... and {len(medium_risks) - 5} more")
        print()

    # Items needing human review
    review_items = report.items_needing_review
    hallucinations = [r for r in review_items if r.get("type") == "possible_hallucination"]
    partial_matches = [r for r in review_items if r.get("type") == "partial_match"]

    needs_review = hallucinations + partial_matches
    if needs_review:
        print(f"[!] ITEMS NEEDING HUMAN REVIEW ({len(needs_review)}):")
        for item in needs_review[:3]:
            reason = item.get("reason", "Verification needed")
            print(f"  - {item['obligation_id']}: {reason}")
        if len(needs_review) > 3:
            print(f"  ... and {len(needs_review) - 3} more")
        print()

    # Verification status
    if verification.has_hallucinations:
        print("[WARNING] Possible hallucinations detected - review flagged items")
    elif verification.verification_rate < 1.0:
        print(f"[NOTE] Verification rate: {verification.verification_rate:.0%}")


def process_directory(
    input_dir: Path,
    output_dir: Path,
    verbose: bool = False,
) -> tuple[int, int]:
    """
    Process all contracts in a directory.

    Args:
        input_dir: Directory containing contract files
        output_dir: Directory to save results
        verbose: Whether to print detailed output

    Returns:
        Tuple of (success_count, failure_count)
    """
    # Find all supported files
    supported_extensions = {".pdf", ".txt", ".text"}
    files = [
        f for f in input_dir.iterdir()
        if f.is_file() and f.suffix.lower() in supported_extensions
    ]

    if not files:
        print(f"No supported files found in {input_dir}")
        print(f"Supported formats: {', '.join(supported_extensions)}")
        return 0, 0

    print(f"Found {len(files)} contract(s) to process")
    print_header("", "-", 44)

    success_count = 0
    failure_count = 0

    for file_path in sorted(files):
        if process_single_file(file_path, output_dir, verbose):
            success_count += 1
        else:
            failure_count += 1

    return success_count, failure_count


def main(input_path: str, output_path: str, verbose: bool = False) -> int:
    """
    Main entry point for the contract analyzer.

    Args:
        input_path: Path to input file or directory
        output_path: Path to output directory
        verbose: Whether to print detailed output

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    input_path = Path(input_path)
    output_dir = Path(output_path)

    # Validate input
    if not input_path.exists():
        print(f"Error: Input path does not exist: {input_path}")
        return 1

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    print()
    print_header("DVS Legal Contract Clause Flagger", "=", 44)

    # Process single file or directory
    if input_path.is_file():
        success = process_single_file(input_path, output_dir, verbose)
        return 0 if success else 1

    elif input_path.is_dir():
        success_count, failure_count = process_directory(input_path, output_dir, verbose)

        print()
        print_header("BATCH PROCESSING COMPLETE", "=", 44)
        print(f"Processed: {success_count + failure_count} files")
        print(f"  Succeeded: {success_count}")
        print(f"  Failed: {failure_count}")

        return 0 if failure_count == 0 else 1

    else:
        print(f"Error: Invalid input path: {input_path}")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract obligations, deadlines, and risk indicators from legal contracts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --input contract.pdf --output results/
  %(prog)s --input contracts/ --output results/
  %(prog)s -i lease.txt -o ./output -v

Supported file formats: .pdf, .txt
        """
    )

    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Input contract file or directory containing contracts"
    )

    parser.add_argument(
        "--output", "-o",
        default="results/",
        help="Output directory for reports (default: results/)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed output including stack traces on errors"
    )

    args = parser.parse_args()

    try:
        exit_code = main(args.input, args.output, args.verbose)
        sys.exit(exit_code)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)

    except Exception as e:
        print(f"\nFatal error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
