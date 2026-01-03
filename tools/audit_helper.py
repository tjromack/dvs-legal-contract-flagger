#!/usr/bin/env python3
"""
Audit Helper Tool

Helps audit AI-generated ground truth annotations against actual contract text.
Automates tedious verification tasks: checking source text existence, finding
potentially missed clauses, and generating audit checklists.

Usage:
    python tools/audit_helper.py --contract <path> --ground-truth <path> [options]

Options:
    --output: Path for generated audit.md file (default: alongside contract)
    --prepare: Update ground truth JSON with audit fields if missing
    --threshold: Fuzzy match threshold (default: 0.85)
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional


# Obligation indicator keywords for coverage scanning
OBLIGATION_KEYWORDS = {
    "SHALL": r"\bshall\b",
    "MUST": r"\bmust\b",
    "AGREES": r"\bagrees?\b",
    "WARRANTS": r"\bwarrants?\b",
    "COVENANTS": r"\bcovenants?\b",
    "WILL NOT": r"\bwill\s+not\b",
    "MAY NOT": r"\bmay\s+not\b",
    "IS RESPONSIBLE": r"\bis\s+responsible\b",
    "IS REQUIRED": r"\bis\s+required\b",
    "UNDERTAKES": r"\bundertakes?\b",
    "COMMITS": r"\bcommits?\b",
    "OBLIGATED": r"\bobligated\b",
    "PROHIBITED": r"\bprohibited\b",
}


@dataclass
class VerificationResult:
    """Result of verifying a single source text against the contract."""
    item_id: str
    item_type: str  # "obligation" or "risk_flag"
    source_text: str
    description: str
    source_location: str
    match_ratio: float
    status: str  # "VERIFIED", "LIKELY_OK", "FLAGGED"
    best_match_text: Optional[str] = None


@dataclass
class PotentialMiss:
    """A sentence in the contract that might be a missed obligation."""
    keyword: str
    line_number: int
    sentence: str
    similarity_to_existing: float


def load_contract(path: Path) -> str:
    """Load contract text from file, handling encoding issues."""
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

    for encoding in encodings:
        try:
            with open(path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue

    raise ValueError(f"Could not decode contract file: {path}")


def load_ground_truth(path: Path) -> dict:
    """Load ground truth JSON file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in ground truth file: {e}")


def save_ground_truth(path: Path, data: dict) -> None:
    """Save ground truth JSON file with proper formatting."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def normalize_text(text: str) -> str:
    """Normalize text for comparison (lowercase, collapse whitespace)."""
    # Collapse multiple whitespace to single space
    text = re.sub(r"\s+", " ", text)
    # Remove leading/trailing whitespace
    text = text.strip()
    # Lowercase for comparison
    text = text.lower()
    return text


def fuzzy_match(source_text: str, contract_text: str) -> tuple[float, Optional[str]]:
    """
    Find the best fuzzy match for source_text within contract_text.
    Returns (match_ratio, best_match_substring).
    """
    source_normalized = normalize_text(source_text)
    contract_normalized = normalize_text(contract_text)

    # If source text is short, do exact substring search first
    if source_normalized in contract_normalized:
        return 1.0, source_text

    # Sliding window approach for longer texts
    source_len = len(source_normalized)
    best_ratio = 0.0
    best_match = None

    # Try different window sizes around the source length
    for window_size in [source_len, int(source_len * 1.2), int(source_len * 0.8)]:
        if window_size <= 0:
            continue

        for i in range(0, len(contract_normalized) - window_size + 1, max(1, window_size // 4)):
            window = contract_normalized[i:i + window_size]
            ratio = SequenceMatcher(None, source_normalized, window).ratio()

            if ratio > best_ratio:
                best_ratio = ratio
                # Get the original (non-normalized) text for display
                best_match = contract_text[i:i + window_size]

    return best_ratio, best_match


def verify_source_texts(
    ground_truth: dict,
    contract_text: str,
    threshold: float = 0.85
) -> list[VerificationResult]:
    """Verify all source_text fields against the contract."""
    results = []

    # Verify obligations
    for obl in ground_truth.get("obligations", []):
        source_text = obl.get("source_text", "")
        if not source_text:
            results.append(VerificationResult(
                item_id=obl.get("id", "UNKNOWN"),
                item_type="obligation",
                source_text="",
                description=obl.get("description", ""),
                source_location=obl.get("source_location", ""),
                match_ratio=0.0,
                status="FLAGGED",
                best_match_text=None
            ))
            continue

        ratio, best_match = fuzzy_match(source_text, contract_text)

        if ratio >= 0.95:
            status = "VERIFIED"
        elif ratio >= threshold:
            status = "LIKELY_OK"
        else:
            status = "FLAGGED"

        results.append(VerificationResult(
            item_id=obl.get("id", "UNKNOWN"),
            item_type="obligation",
            source_text=source_text,
            description=obl.get("description", ""),
            source_location=obl.get("source_location", ""),
            match_ratio=ratio,
            status=status,
            best_match_text=best_match
        ))

    # Verify risk flags
    for i, risk in enumerate(ground_truth.get("risk_flags", [])):
        source_text = risk.get("source_text", "")
        if not source_text:
            results.append(VerificationResult(
                item_id=f"FLAG-{i+1:03d}",
                item_type="risk_flag",
                source_text="",
                description=risk.get("title", risk.get("description", "")),
                source_location=risk.get("source_location", ""),
                match_ratio=0.0,
                status="FLAGGED",
                best_match_text=None
            ))
            continue

        ratio, best_match = fuzzy_match(source_text, contract_text)

        if ratio >= 0.95:
            status = "VERIFIED"
        elif ratio >= threshold:
            status = "LIKELY_OK"
        else:
            status = "FLAGGED"

        results.append(VerificationResult(
            item_id=f"FLAG-{i+1:03d}",
            item_type="risk_flag",
            source_text=source_text,
            description=risk.get("title", risk.get("description", "")),
            source_location=risk.get("source_location", ""),
            match_ratio=ratio,
            status=status,
            best_match_text=best_match
        ))

    return results


def extract_sentences_with_keywords(contract_text: str) -> list[tuple[str, int, str]]:
    """
    Extract sentences containing obligation keywords.
    Returns list of (keyword, line_number, sentence).
    """
    results = []
    lines = contract_text.split("\n")

    for line_num, line in enumerate(lines, 1):
        # Split line into sentences (simple approach)
        sentences = re.split(r"(?<=[.;])\s+", line)

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:  # Skip very short fragments
                continue

            for keyword, pattern in OBLIGATION_KEYWORDS.items():
                if re.search(pattern, sentence, re.IGNORECASE):
                    results.append((keyword, line_num, sentence))
                    break  # Only count each sentence once

    return results


def find_potential_misses(
    contract_text: str,
    ground_truth: dict,
    threshold: float = 0.7
) -> list[PotentialMiss]:
    """
    Find sentences with obligation keywords that aren't in ground truth.
    """
    # Collect all existing source texts
    existing_sources = []
    for obl in ground_truth.get("obligations", []):
        if obl.get("source_text"):
            existing_sources.append(normalize_text(obl["source_text"]))
    for risk in ground_truth.get("risk_flags", []):
        if risk.get("source_text"):
            existing_sources.append(normalize_text(risk["source_text"]))

    # Find sentences with keywords
    keyword_sentences = extract_sentences_with_keywords(contract_text)

    potential_misses = []
    for keyword, line_num, sentence in keyword_sentences:
        sentence_normalized = normalize_text(sentence)

        # Check if this sentence is similar to any existing source text
        max_similarity = 0.0
        for existing in existing_sources:
            ratio = SequenceMatcher(None, sentence_normalized, existing).ratio()
            max_similarity = max(max_similarity, ratio)

        # If not similar to existing sources, it's a potential miss
        if max_similarity < threshold:
            potential_misses.append(PotentialMiss(
                keyword=keyword,
                line_number=line_num,
                sentence=sentence,
                similarity_to_existing=max_similarity
            ))

    return potential_misses


def prepare_ground_truth(ground_truth: dict) -> dict:
    """Add audit fields to ground truth if they don't exist."""
    # Top-level audit fields
    if "_audited" not in ground_truth:
        ground_truth["_audited"] = False
    if "_audit_date" not in ground_truth:
        ground_truth["_audit_date"] = None
    if "_audit_notes" not in ground_truth:
        ground_truth["_audit_notes"] = ""
    if "_missed_obligations" not in ground_truth:
        ground_truth["_missed_obligations"] = []
    if "_false_positives" not in ground_truth:
        ground_truth["_false_positives"] = []

    # Add audit fields to each obligation
    for obl in ground_truth.get("obligations", []):
        if "_audit_status" not in obl:
            obl["_audit_status"] = "pending"
        if "_audit_notes" not in obl:
            obl["_audit_notes"] = ""

    # Add audit fields to each risk flag
    for risk in ground_truth.get("risk_flags", []):
        if "_audit_status" not in risk:
            risk["_audit_status"] = "pending"
        if "_audit_notes" not in risk:
            risk["_audit_notes"] = ""

    return ground_truth


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text with ellipsis if too long."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def generate_audit_markdown(
    contract_name: str,
    verification_results: list[VerificationResult],
    potential_misses: list[PotentialMiss],
    ground_truth: dict
) -> str:
    """Generate the audit checklist markdown file matching ground_truth format."""
    now = datetime.now().strftime("%Y-%m-%d")

    # Separate obligations and risk flags
    obligations = [r for r in verification_results if r.item_type == "obligation"]
    risk_flags = [r for r in verification_results if r.item_type == "risk_flag"]

    lines = []
    lines.append(f"# Audit: {contract_name}")
    lines.append("")
    lines.append("**Audited:** Not yet")
    lines.append("**Audit Date:** -")
    lines.append("**Time Spent:** -")
    lines.append("**Auditor:** -")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Verified section with checkboxes
    lines.append("## Verified")
    lines.append("")
    lines.append("_Mark each obligation/risk as you verify it against the source contract_")
    lines.append("")

    # Obligations subsection
    lines.append("### Obligations")
    for r in obligations:
        # Use [X] for verified, [LIKELY] for likely, [ ] for flagged
        if r.status == "VERIFIED":
            checkbox = "[X]"
        elif r.status == "LIKELY_OK":
            checkbox = "[LIKELY]"
        else:
            checkbox = "[FLAG]"
        lines.append(f"- {checkbox} {r.item_id}: {r.description}")
    lines.append("")

    # Risk Flags subsection
    lines.append("### Risk Flags")
    for i, r in enumerate(risk_flags):
        # Get severity from ground truth if available
        risk_data = ground_truth.get("risk_flags", [])
        severity = ""
        if i < len(risk_data):
            sev = risk_data[i].get("severity", "")
            if sev and sev.upper() == "HIGH":
                severity = " (HIGH)"

        if r.status == "VERIFIED":
            checkbox = "[X]"
        elif r.status == "LIKELY_OK":
            checkbox = "[LIKELY]"
        else:
            checkbox = "[FLAG]"
        lines.append(f"- {checkbox} RISK-{i+1:03d}: {r.description}{severity}")
    lines.append("")

    lines.append("---")
    lines.append("")

    # Issues Found section
    lines.append("## Issues Found")
    lines.append("")
    lines.append("_Document any problems with the ground truth annotations_")
    lines.append("")
    lines.append("| ID | Issue | Resolution |")
    lines.append("|----|-------|------------|")
    lines.append("| - | - | - |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Missed by AI section - populated with potential misses
    lines.append("## Missed by AI")
    lines.append("")
    lines.append("_Obligations or risks present in contract but not captured by system_")
    lines.append("")
    lines.append("| Section | Description | Suggested Obligation/Risk |")
    lines.append("|---------|-------------|---------------------------|")

    if potential_misses:
        # Show top potential misses (prioritize by keyword importance)
        priority_keywords = ["SHALL", "MUST", "AGREES", "WARRANTS", "COVENANTS"]
        shown = 0
        for keyword in priority_keywords:
            for miss in potential_misses:
                if miss.keyword == keyword and shown < 10:
                    desc = truncate_text(miss.sentence, 60)
                    lines.append(f"| Line {miss.line_number} | {desc} | Review: contains '{keyword.lower()}' |")
                    shown += 1
        if shown == 0:
            lines.append("| - | - | - |")
    else:
        lines.append("| - | - | - |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Hallucinated section
    lines.append("## Hallucinated (Remove)")
    lines.append("")
    lines.append("_Items AI extracted that don't exist or are incorrect_")
    lines.append("")
    lines.append("| System ID | Issue | Action |")
    lines.append("|-----------|-------|--------|")

    # Flag any items that didn't match well
    flagged_items = [r for r in verification_results if r.status == "FLAGGED"]
    if flagged_items:
        for r in flagged_items:
            pct = f"{r.match_ratio * 100:.0f}%"
            lines.append(f"| {r.item_id} | Only {pct} match - verify source text | Review |")
    else:
        lines.append("| - | - | - |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Risk Flag Adjustments section
    lines.append("## Risk Flag Adjustments")
    lines.append("")
    lines.append("_Changes to severity or category_")
    lines.append("")
    lines.append("| Risk ID | Current | Recommended | Reason |")
    lines.append("|---------|---------|-------------|--------|")
    lines.append("| - | - | - | - |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Notes section
    lines.append("## Notes")
    lines.append("")
    lines.append("_Additional observations for lessons learned_")
    lines.append("")
    lines.append(f"- Auto-generated on {now}")
    lines.append(f"- {len(obligations)} obligations verified: " +
                f"{sum(1 for r in obligations if r.status == 'VERIFIED')} exact, " +
                f"{sum(1 for r in obligations if r.status == 'LIKELY_OK')} likely, " +
                f"{sum(1 for r in obligations if r.status == 'FLAGGED')} flagged")
    lines.append(f"- {len(risk_flags)} risk flags verified: " +
                f"{sum(1 for r in risk_flags if r.status == 'VERIFIED')} exact, " +
                f"{sum(1 for r in risk_flags if r.status == 'LIKELY_OK')} likely, " +
                f"{sum(1 for r in risk_flags if r.status == 'FLAGGED')} flagged")
    lines.append(f"- {len(potential_misses)} potential missed clauses found for review")
    lines.append("")

    return "\n".join(lines)


def print_status_icon(status: str) -> str:
    """Return status icon for console output."""
    if status == "VERIFIED":
        return "OK"
    elif status == "LIKELY_OK":
        return "~"
    else:
        return "X"


def main():
    parser = argparse.ArgumentParser(
        description="Audit AI-generated ground truth annotations against contract text"
    )
    parser.add_argument(
        "--contract",
        required=True,
        help="Path to the contract .txt file"
    )
    parser.add_argument(
        "--ground-truth",
        required=True,
        help="Path to the ground truth .json file"
    )
    parser.add_argument(
        "--output",
        help="Path for the generated audit.md file (default: alongside contract)"
    )
    parser.add_argument(
        "--prepare",
        action="store_true",
        help="Update ground truth JSON to add audit fields"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Fuzzy match threshold (default: 0.85)"
    )

    args = parser.parse_args()

    # Validate paths
    contract_path = Path(args.contract)
    ground_truth_path = Path(args.ground_truth)

    if not contract_path.exists():
        print(f"Error: Contract file not found: {contract_path}")
        sys.exit(1)

    if not ground_truth_path.exists():
        print(f"Error: Ground truth file not found: {ground_truth_path}")
        sys.exit(1)

    # Determine output path - default to ground_truth directory
    if args.output:
        output_path = Path(args.output)
    else:
        # Put audit file in same directory as ground truth file
        output_path = ground_truth_path.parent / f"{contract_path.stem}_audit.md"

    # Load files
    print("=" * 80)
    print("CONTRACT AUDIT HELPER")
    print(f"Contract: {contract_path.name}")
    print(f"Ground Truth: {ground_truth_path.name}")
    print()

    try:
        contract_text = load_contract(contract_path)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    try:
        ground_truth = load_ground_truth(ground_truth_path)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Check for obligations
    obligations = ground_truth.get("obligations", [])
    risk_flags = ground_truth.get("risk_flags", [])

    if not obligations and not risk_flags:
        print("Warning: Ground truth has no obligations or risk flags")

    # 1. Verify source texts
    verification_results = verify_source_texts(ground_truth, contract_text, args.threshold)

    obl_results = [r for r in verification_results if r.item_type == "obligation"]
    risk_results = [r for r in verification_results if r.item_type == "risk_flag"]

    # Print obligation verification results
    if obl_results:
        print(f"SOURCE TEXT VERIFICATION ({len(obl_results)} obligations)")
        verified = 0
        likely = 0
        flagged = 0

        for r in obl_results:
            icon = print_status_icon(r.status)
            match_pct = f"{r.match_ratio * 100:.1f}%"

            if r.status == "VERIFIED":
                verified += 1
                print(f"  {icon} {r.item_id}: VERIFIED ({match_pct} match)")
            elif r.status == "LIKELY_OK":
                likely += 1
                print(f"  {icon} {r.item_id}: LIKELY OK ({match_pct} match)")
            else:
                flagged += 1
                print(f"  {icon} {r.item_id}: FLAGGED ({match_pct} match) <- NEEDS REVIEW")

            print(f"     \"{truncate_text(r.source_text, 60)}\"")

        print(f"  Summary: {verified} verified, {likely} likely ok, {flagged} flagged")
        print()

    # Print risk flag verification results
    if risk_results:
        print(f"RISK FLAG VERIFICATION ({len(risk_results)} flags)")
        verified = 0
        likely = 0
        flagged = 0

        for r in risk_results:
            icon = print_status_icon(r.status)
            match_pct = f"{r.match_ratio * 100:.1f}%"

            if r.status == "VERIFIED":
                verified += 1
                print(f"  {icon} {r.item_id}: VERIFIED ({match_pct} match)")
            elif r.status == "LIKELY_OK":
                likely += 1
                print(f"  {icon} {r.item_id}: LIKELY OK ({match_pct} match)")
            else:
                flagged += 1
                print(f"  {icon} {r.item_id}: FLAGGED ({match_pct} match) <- NEEDS REVIEW")

        print(f"  Summary: {verified} verified, {likely} likely ok, {flagged} flagged")
        print()

    # 2. Find potential misses
    potential_misses = find_potential_misses(contract_text, ground_truth)

    if potential_misses:
        print(f"POTENTIALLY MISSED CLAUSES ({len(potential_misses)} found)")
        print("  Review these sentences - they contain obligation keywords but aren't in ground truth:")

        # Group by keyword and show first few
        by_keyword = {}
        for miss in potential_misses:
            if miss.keyword not in by_keyword:
                by_keyword[miss.keyword] = []
            by_keyword[miss.keyword].append(miss)

        for keyword in sorted(by_keyword.keys()):
            print(f"  [{keyword}]")
            for miss in by_keyword[keyword][:3]:  # Show first 3 per keyword
                print(f"    Line {miss.line_number}: \"{truncate_text(miss.sentence, 70)}\"")
            if len(by_keyword[keyword]) > 3:
                print(f"    ... and {len(by_keyword[keyword]) - 3} more")
        print()
    else:
        print("POTENTIALLY MISSED CLAUSES: None found")
        print()

    # 3. Generate audit markdown
    markdown_content = generate_audit_markdown(
        contract_path.name,
        verification_results,
        potential_misses,
        ground_truth
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    # 4. Optionally update ground truth with audit fields
    if args.prepare:
        ground_truth = prepare_ground_truth(ground_truth)
        save_ground_truth(ground_truth_path, ground_truth)

    # Print summary
    print("GENERATED FILES")
    print(f"  OK Audit checklist: {output_path}")
    if args.prepare:
        print(f"  OK Ground truth updated with audit fields")

    print()
    print("NEXT STEPS:")
    print(f"  1. Open {output_path.name}")
    print("  2. Review each FLAGGED item against the actual contract")
    print("  3. Review potentially missed clauses")
    print("  4. Update _audit_status fields in the JSON")
    print("  5. Set _audited: true when complete")


if __name__ == "__main__":
    main()
