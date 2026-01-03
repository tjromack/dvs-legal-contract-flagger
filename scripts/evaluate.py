#!/usr/bin/env python3
"""
Evaluation Script

Compares system output against ground truth annotations to calculate:
- Precision: What fraction of system extractions are correct?
- Recall: What fraction of ground truth items did system find?
- F1 Score: Harmonic mean of precision and recall

Usage:
    python scripts/evaluate.py <contract_file>
    python scripts/evaluate.py data/sample_contracts/mutual_nda.txt
    python scripts/evaluate.py --all  # Evaluate all contracts with ground truth
"""

import argparse
import json
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extractor import extract_contract
from src.analyzer import analyze_contract
from src.risk_scorer import score_risks


@dataclass
class MatchResult:
    """Result of matching a system item to ground truth."""
    system_id: str
    ground_truth_id: Optional[str]
    match_type: str  # exact, partial, none
    similarity: float
    details: str


@dataclass
class EvaluationMetrics:
    """Precision/Recall metrics for a category."""
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float


@dataclass
class EvaluationReport:
    """Complete evaluation report."""
    contract_file: str
    obligations: EvaluationMetrics
    risk_flags: EvaluationMetrics
    parties: EvaluationMetrics
    metadata_accuracy: dict
    obligation_matches: list[MatchResult]
    risk_matches: list[MatchResult]


def load_ground_truth(contract_path: Path) -> Optional[dict]:
    """Load ground truth file for a contract."""
    ground_truth_dir = contract_path.parent.parent / "ground_truth"
    ground_truth_file = ground_truth_dir / f"{contract_path.stem}_ground_truth.json"

    if not ground_truth_file.exists():
        return None

    with open(ground_truth_file, "r", encoding="utf-8") as f:
        return json.load(f)


def text_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two text strings."""
    if not text1 or not text2:
        return 0.0

    # Normalize
    t1 = text1.lower().strip()
    t2 = text2.lower().strip()

    return SequenceMatcher(None, t1, t2).ratio()


def match_obligations(
    system_obligations: list[dict],
    ground_truth_obligations: list[dict],
    threshold: float = 0.6
) -> tuple[list[MatchResult], EvaluationMetrics]:
    """
    Match system obligations to ground truth obligations.

    Uses a combination of:
    - source_text similarity (weighted heavily)
    - description similarity
    - party match
    - type match
    """
    matches = []
    matched_gt_ids = set()

    for sys_obl in system_obligations:
        best_match = None
        best_score = 0.0
        best_gt_id = None

        for gt_obl in ground_truth_obligations:
            if gt_obl["id"] in matched_gt_ids:
                continue

            # Calculate match score
            source_sim = text_similarity(
                sys_obl.get("source_text", ""),
                gt_obl.get("source_text", "")
            )
            desc_sim = text_similarity(
                sys_obl.get("description", ""),
                gt_obl.get("description", "")
            )
            party_match = 1.0 if sys_obl.get("party", "").lower() == gt_obl.get("party", "").lower() else 0.0
            type_match = 1.0 if sys_obl.get("type", "").lower() == gt_obl.get("type", "").lower() else 0.5

            # Weighted score (source_text is most important)
            score = (source_sim * 0.5) + (desc_sim * 0.25) + (party_match * 0.15) + (type_match * 0.1)

            if score > best_score:
                best_score = score
                best_match = gt_obl
                best_gt_id = gt_obl["id"]

        if best_score >= threshold:
            match_type = "exact" if best_score >= 0.85 else "partial"
            matched_gt_ids.add(best_gt_id)
            matches.append(MatchResult(
                system_id=sys_obl["id"],
                ground_truth_id=best_gt_id,
                match_type=match_type,
                similarity=best_score,
                details=f"Matched to {best_gt_id} (score: {best_score:.2f})"
            ))
        else:
            matches.append(MatchResult(
                system_id=sys_obl["id"],
                ground_truth_id=None,
                match_type="none",
                similarity=best_score,
                details=f"No match found (best score: {best_score:.2f})"
            ))

    # Calculate metrics
    true_positives = sum(1 for m in matches if m.match_type != "none")
    false_positives = sum(1 for m in matches if m.match_type == "none")
    false_negatives = len(ground_truth_obligations) - len(matched_gt_ids)

    precision = true_positives / len(system_obligations) if system_obligations else 0.0
    recall = true_positives / len(ground_truth_obligations) if ground_truth_obligations else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    metrics = EvaluationMetrics(
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=precision,
        recall=recall,
        f1_score=f1
    )

    return matches, metrics


def match_risks(
    system_risks: list[dict],
    ground_truth_risks: list[dict],
    threshold: float = 0.5
) -> tuple[list[MatchResult], EvaluationMetrics]:
    """Match system risk flags to ground truth risk flags."""
    matches = []
    matched_gt_indices = set()

    for i, sys_risk in enumerate(system_risks):
        best_match = None
        best_score = 0.0
        best_idx = None

        for j, gt_risk in enumerate(ground_truth_risks):
            if j in matched_gt_indices:
                continue

            # Match on category, severity, and source text
            category_match = 1.0 if sys_risk.get("category") == gt_risk.get("category") else 0.0
            severity_match = 1.0 if sys_risk.get("severity") == gt_risk.get("severity") else 0.5
            source_sim = text_similarity(
                sys_risk.get("source_text", ""),
                gt_risk.get("source_text", "")
            )
            title_sim = text_similarity(
                sys_risk.get("title", ""),
                gt_risk.get("title", "")
            )

            score = (category_match * 0.3) + (source_sim * 0.3) + (title_sim * 0.25) + (severity_match * 0.15)

            if score > best_score:
                best_score = score
                best_match = gt_risk
                best_idx = j

        if best_score >= threshold:
            match_type = "exact" if best_score >= 0.8 else "partial"
            matched_gt_indices.add(best_idx)
            matches.append(MatchResult(
                system_id=f"RISK-{i+1}",
                ground_truth_id=f"GT-RISK-{best_idx+1}",
                match_type=match_type,
                similarity=best_score,
                details=f"Category: {sys_risk.get('category')} -> {best_match.get('category')}"
            ))
        else:
            matches.append(MatchResult(
                system_id=f"RISK-{i+1}",
                ground_truth_id=None,
                match_type="none",
                similarity=best_score,
                details=f"No match (category: {sys_risk.get('category')})"
            ))

    true_positives = sum(1 for m in matches if m.match_type != "none")
    false_positives = sum(1 for m in matches if m.match_type == "none")
    false_negatives = len(ground_truth_risks) - len(matched_gt_indices)

    precision = true_positives / len(system_risks) if system_risks else 0.0
    recall = true_positives / len(ground_truth_risks) if ground_truth_risks else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return matches, EvaluationMetrics(
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=precision,
        recall=recall,
        f1_score=f1
    )


def evaluate_parties(
    system_parties: list[dict],
    ground_truth_parties: list[dict]
) -> EvaluationMetrics:
    """Evaluate party extraction accuracy."""
    sys_names = {p["name"].lower() for p in system_parties}
    gt_names = {p["name"].lower() for p in ground_truth_parties}

    true_positives = len(sys_names & gt_names)
    false_positives = len(sys_names - gt_names)
    false_negatives = len(gt_names - sys_names)

    precision = true_positives / len(sys_names) if sys_names else 0.0
    recall = true_positives / len(gt_names) if gt_names else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return EvaluationMetrics(
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=precision,
        recall=recall,
        f1_score=f1
    )


def evaluate_metadata(system_result: dict, ground_truth: dict) -> dict:
    """Evaluate metadata extraction accuracy."""
    fields = ["effective_date", "term", "termination_notice_period"]
    results = {}

    for field in fields:
        sys_val = system_result.get(field)
        gt_val = ground_truth.get(field)

        if sys_val is None and gt_val is None:
            results[field] = {"match": True, "system": None, "ground_truth": None}
        elif sys_val and gt_val:
            similarity = text_similarity(str(sys_val), str(gt_val))
            results[field] = {
                "match": similarity > 0.8,
                "similarity": similarity,
                "system": sys_val,
                "ground_truth": gt_val
            }
        else:
            results[field] = {
                "match": False,
                "system": sys_val,
                "ground_truth": gt_val
            }

    # Auto-renewal
    sys_ar = system_result.get("auto_renewal", {})
    gt_ar = ground_truth.get("auto_renewal", {})
    results["auto_renewal_exists"] = {
        "match": sys_ar.get("exists") == gt_ar.get("exists"),
        "system": sys_ar.get("exists"),
        "ground_truth": gt_ar.get("exists")
    }

    return results


def run_evaluation(contract_path: Path, verbose: bool = True) -> Optional[EvaluationReport]:
    """Run full evaluation on a contract."""
    ground_truth = load_ground_truth(contract_path)

    if ground_truth is None:
        if verbose:
            print(f"No ground truth file found for {contract_path.name}")
            print(f"Expected: data/ground_truth/{contract_path.stem}_ground_truth.json")
        return None

    if verbose:
        print(f"Evaluating: {contract_path.name}")
        print("-" * 50)

    # Run system
    if verbose:
        print("Running system extraction...", end=" ", flush=True)

    try:
        analysis = analyze_contract(str(contract_path), verbose=False)
        risk_assessment = score_risks(analysis)
        if verbose:
            print("done")
    except Exception as e:
        print(f"Error: {e}")
        return None

    # Convert to dicts for comparison
    system_obligations = [
        {
            "id": o.id,
            "party": o.party,
            "type": o.type,
            "description": o.description,
            "deadline": o.deadline,
            "conditions": o.conditions,
            "source_text": o.source_text,
            "source_location": o.source_location
        }
        for o in analysis.obligations
    ]

    system_risks = [
        {
            "category": r.category.value,
            "severity": r.severity.value,
            "title": r.title,
            "source_text": r.source_text,
            "source_location": r.source_location
        }
        for r in risk_assessment.risks
    ]

    system_parties = [
        {"name": p.name, "role": p.role, "is_reader": p.is_reader}
        for p in analysis.parties
    ]

    # Run evaluations
    obl_matches, obl_metrics = match_obligations(
        system_obligations,
        ground_truth.get("obligations", [])
    )

    risk_matches, risk_metrics = match_risks(
        system_risks,
        ground_truth.get("risk_flags", [])
    )

    party_metrics = evaluate_parties(
        system_parties,
        ground_truth.get("parties", [])
    )

    metadata_accuracy = evaluate_metadata(
        {
            "effective_date": analysis.effective_date,
            "term": analysis.term,
            "termination_notice_period": analysis.termination_notice_period,
            "auto_renewal": {
                "exists": analysis.auto_renewal.exists,
                "period": analysis.auto_renewal.period,
                "notice_to_cancel": analysis.auto_renewal.notice_to_cancel
            }
        },
        ground_truth
    )

    return EvaluationReport(
        contract_file=str(contract_path),
        obligations=obl_metrics,
        risk_flags=risk_metrics,
        parties=party_metrics,
        metadata_accuracy=metadata_accuracy,
        obligation_matches=obl_matches,
        risk_matches=risk_matches
    )


def print_report(report: EvaluationReport):
    """Print evaluation report to console."""
    print("\n" + "=" * 60)
    print("EVALUATION REPORT")
    print("=" * 60)
    print(f"Contract: {Path(report.contract_file).name}")
    print()

    # Obligations
    print("OBLIGATIONS")
    print("-" * 40)
    m = report.obligations
    print(f"  Precision: {m.precision:.1%} ({m.true_positives}/{m.true_positives + m.false_positives})")
    print(f"  Recall:    {m.recall:.1%} ({m.true_positives}/{m.true_positives + m.false_negatives})")
    print(f"  F1 Score:  {m.f1_score:.1%}")
    print(f"  True Positives:  {m.true_positives}")
    print(f"  False Positives: {m.false_positives} (system extracted, not in ground truth)")
    print(f"  False Negatives: {m.false_negatives} (missed by system)")
    print()

    # Risk Flags
    print("RISK FLAGS")
    print("-" * 40)
    m = report.risk_flags
    print(f"  Precision: {m.precision:.1%} ({m.true_positives}/{m.true_positives + m.false_positives})")
    print(f"  Recall:    {m.recall:.1%} ({m.true_positives}/{m.true_positives + m.false_negatives})")
    print(f"  F1 Score:  {m.f1_score:.1%}")
    print()

    # Parties
    print("PARTIES")
    print("-" * 40)
    m = report.parties
    print(f"  Precision: {m.precision:.1%}")
    print(f"  Recall:    {m.recall:.1%}")
    print()

    # Metadata
    print("METADATA ACCURACY")
    print("-" * 40)
    for field, result in report.metadata_accuracy.items():
        status = "OK" if result.get("match") else "MISMATCH"
        print(f"  {field}: {status}")
        if not result.get("match"):
            print(f"    System: {result.get('system')}")
            print(f"    Ground Truth: {result.get('ground_truth')}")
    print()

    # Detailed obligation mismatches
    unmatched = [m for m in report.obligation_matches if m.match_type == "none"]
    if unmatched:
        print("UNMATCHED SYSTEM OBLIGATIONS (possible false positives)")
        print("-" * 40)
        for m in unmatched[:5]:  # Show first 5
            print(f"  {m.system_id}: {m.details}")
        if len(unmatched) > 5:
            print(f"  ... and {len(unmatched) - 5} more")
        print()

    # Summary
    print("=" * 60)
    overall_f1 = (report.obligations.f1_score + report.risk_flags.f1_score) / 2
    print(f"OVERALL F1 SCORE: {overall_f1:.1%}")
    print("=" * 60)


def save_report(report: EvaluationReport, output_path: Path):
    """Save evaluation report as JSON."""
    data = {
        "contract_file": report.contract_file,
        "obligations": {
            "precision": report.obligations.precision,
            "recall": report.obligations.recall,
            "f1_score": report.obligations.f1_score,
            "true_positives": report.obligations.true_positives,
            "false_positives": report.obligations.false_positives,
            "false_negatives": report.obligations.false_negatives
        },
        "risk_flags": {
            "precision": report.risk_flags.precision,
            "recall": report.risk_flags.recall,
            "f1_score": report.risk_flags.f1_score,
            "true_positives": report.risk_flags.true_positives,
            "false_positives": report.risk_flags.false_positives,
            "false_negatives": report.risk_flags.false_negatives
        },
        "parties": {
            "precision": report.parties.precision,
            "recall": report.parties.recall,
            "f1_score": report.parties.f1_score
        },
        "metadata_accuracy": report.metadata_accuracy,
        "obligation_matches": [
            {
                "system_id": m.system_id,
                "ground_truth_id": m.ground_truth_id,
                "match_type": m.match_type,
                "similarity": m.similarity
            }
            for m in report.obligation_matches
        ],
        "risk_matches": [
            {
                "system_id": m.system_id,
                "ground_truth_id": m.ground_truth_id,
                "match_type": m.match_type,
                "similarity": m.similarity
            }
            for m in report.risk_matches
        ]
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate system output against ground truth annotations"
    )
    parser.add_argument(
        "contract",
        nargs="?",
        help="Path to contract file (or --all to evaluate all)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Evaluate all contracts with ground truth files"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Save report to JSON file"
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Only print summary"
    )

    args = parser.parse_args()

    if args.all:
        # Find all ground truth files
        ground_truth_dir = Path("data/ground_truth")
        if not ground_truth_dir.exists():
            print("No ground_truth directory found")
            sys.exit(1)

        reports = []
        for gt_file in ground_truth_dir.glob("*_ground_truth.json"):
            contract_name = gt_file.stem.replace("_ground_truth", "")
            contract_path = Path("data/sample_contracts") / f"{contract_name}.txt"

            if not contract_path.exists():
                contract_path = Path("data/sample_contracts") / f"{contract_name}.pdf"

            if contract_path.exists():
                report = run_evaluation(contract_path, verbose=not args.quiet)
                if report:
                    reports.append(report)
                    if not args.quiet:
                        print_report(report)

        if reports:
            print("\n" + "=" * 60)
            print("AGGREGATE RESULTS")
            print("=" * 60)
            avg_obl_f1 = sum(r.obligations.f1_score for r in reports) / len(reports)
            avg_risk_f1 = sum(r.risk_flags.f1_score for r in reports) / len(reports)
            print(f"Contracts evaluated: {len(reports)}")
            print(f"Average Obligation F1: {avg_obl_f1:.1%}")
            print(f"Average Risk Flag F1:  {avg_risk_f1:.1%}")

    elif args.contract:
        contract_path = Path(args.contract)
        if not contract_path.exists():
            print(f"Contract file not found: {contract_path}")
            sys.exit(1)

        report = run_evaluation(contract_path)
        if report:
            print_report(report)

            if args.output:
                save_report(report, Path(args.output))
                print(f"\nReport saved to: {args.output}")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
