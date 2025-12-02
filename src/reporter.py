"""
Report Generation Module

Generates final output reports combining:
- Extracted obligations from analyzer
- Risk flags from risk_scorer
- Verification results from verifier

Outputs:
- JSON report (machine-readable, matches README schema)
- Text summary (human-readable CLI output)
- Markdown report (for documentation/sharing)
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .analyzer import AnalysisResult
from .risk_scorer import RiskAssessment, Severity
from .verifier import DocumentVerificationReport, VerificationStatus


@dataclass
class ContractReport:
    """Complete contract analysis report."""

    # Source info
    file_path: str
    file_name: str
    generated_at: str

    # Contract metadata
    parties: list[dict]
    effective_date: Optional[str]
    term: Optional[str]
    termination_notice_period: Optional[str]
    auto_renewal: dict

    # Obligations with risk levels
    obligations: list[dict]

    # Risk flags
    risk_flags: list[dict]
    risk_summary: dict

    # Verification
    verification_rate: float
    has_hallucinations: bool
    items_needing_review: list[dict]

    # Summary
    summary: str

    def to_dict(self) -> dict:
        """Convert to dictionary matching README schema."""
        return {
            "file_path": self.file_path,
            "file_name": self.file_name,
            "generated_at": self.generated_at,
            "parties": self.parties,
            "effective_date": self.effective_date,
            "term": self.term,
            "termination_notice_period": self.termination_notice_period,
            "auto_renewal": self.auto_renewal,
            "obligations": self.obligations,
            "risk_flags": self.risk_flags,
            "risk_summary": self.risk_summary,
            "verification": {
                "rate": self.verification_rate,
                "has_hallucinations": self.has_hallucinations,
                "items_needing_review": self.items_needing_review,
            },
            "summary": self.summary,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class ContractReporter:
    """
    Generates reports from contract analysis results.

    Combines outputs from analyzer, risk_scorer, and verifier
    into unified JSON and human-readable formats.
    """

    def __init__(self, output_dir: str | Path = "results"):
        """
        Initialize the reporter.

        Args:
            output_dir: Directory to save output files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(
        self,
        analysis: AnalysisResult,
        risk_assessment: RiskAssessment,
        verification: DocumentVerificationReport,
    ) -> ContractReport:
        """
        Generate a complete contract report.

        Args:
            analysis: AnalysisResult from analyzer
            risk_assessment: RiskAssessment from risk_scorer
            verification: DocumentVerificationReport from verifier

        Returns:
            ContractReport with all combined data
        """
        file_name = Path(analysis.file_path).name

        # Build parties list
        parties = [
            {
                "name": p.name,
                "role": p.role,
                "is_reader": p.is_reader,
            }
            for p in analysis.parties
        ]

        # Build obligations with risk info
        obligations = self._build_obligations(analysis, risk_assessment, verification)

        # Build risk flags
        risk_flags = [
            {
                "obligation_id": r.obligation_id,
                "category": r.category.value,
                "severity": r.severity.value,
                "title": r.title,
                "description": r.description,
                "source_text": r.source_text,
                "source_location": r.source_location,
                "action_required": r.action_required,
                "negotiation_suggestion": r.negotiation_suggestion,
            }
            for r in risk_assessment.risks
        ]

        # Build items needing human review
        items_needing_review = self._build_review_items(
            analysis, risk_assessment, verification
        )

        # Generate summary text
        summary = self._generate_summary(
            analysis, risk_assessment, verification
        )

        return ContractReport(
            file_path=analysis.file_path,
            file_name=file_name,
            generated_at=datetime.now().isoformat(),
            parties=parties,
            effective_date=analysis.effective_date,
            term=analysis.term,
            termination_notice_period=analysis.termination_notice_period,
            auto_renewal={
                "exists": analysis.auto_renewal.exists,
                "period": analysis.auto_renewal.period,
                "notice_to_cancel": analysis.auto_renewal.notice_to_cancel,
            },
            obligations=obligations,
            risk_flags=risk_flags,
            risk_summary=risk_assessment.summary.to_dict(),
            verification_rate=verification.verification_rate,
            has_hallucinations=verification.has_hallucinations,
            items_needing_review=items_needing_review,
            summary=summary,
        )

    def _build_obligations(
        self,
        analysis: AnalysisResult,
        risk_assessment: RiskAssessment,
        verification: DocumentVerificationReport,
    ) -> list[dict]:
        """Build obligations list with risk and verification info."""
        # Create lookup maps
        risk_by_obligation = {}
        for risk in risk_assessment.risks:
            if risk.obligation_id not in risk_by_obligation:
                risk_by_obligation[risk.obligation_id] = []
            risk_by_obligation[risk.obligation_id].append(risk)

        verification_by_id = {
            v.obligation_id: v for v in verification.results
        }

        obligations = []
        for obl in analysis.obligations:
            # Get risks for this obligation
            obl_risks = risk_by_obligation.get(obl.id, [])

            # Determine highest risk level
            if obl_risks:
                severities = [r.severity for r in obl_risks]
                if Severity.HIGH in severities:
                    risk_level = "high"
                elif Severity.MEDIUM in severities:
                    risk_level = "medium"
                else:
                    risk_level = "low"
            else:
                risk_level = "low"

            # Get verification status
            ver = verification_by_id.get(obl.id)
            verified = ver.status in (
                VerificationStatus.VERIFIED,
                VerificationStatus.PARTIAL
            ) if ver else True

            obligations.append({
                "id": obl.id,
                "party": obl.party,
                "type": obl.type,
                "description": obl.description,
                "deadline": obl.deadline,
                "conditions": obl.conditions,
                "source_text": obl.source_text,
                "source_location": obl.source_location,
                "risk_level": risk_level,
                "risk_flags": [r.title for r in obl_risks],
                "verified": verified,
            })

        return obligations

    def _build_review_items(
        self,
        analysis: AnalysisResult,
        risk_assessment: RiskAssessment,
        verification: DocumentVerificationReport,
    ) -> list[dict]:
        """Build list of items needing human review."""
        items = []

        # Add unverified obligations (possible hallucinations)
        for ver_result in verification.results:
            if ver_result.status == VerificationStatus.UNVERIFIED:
                items.append({
                    "obligation_id": ver_result.obligation_id,
                    "reason": "Source text could not be verified",
                    "type": "possible_hallucination",
                    "confidence": ver_result.confidence,
                    "details": ver_result.issues,
                })

        # Add partial matches that need confirmation
        for ver_result in verification.results:
            if ver_result.status == VerificationStatus.PARTIAL:
                items.append({
                    "obligation_id": ver_result.obligation_id,
                    "reason": "Partial match - verify source text",
                    "type": "partial_match",
                    "confidence": ver_result.confidence,
                    "details": ver_result.issues,
                })

        # Add high-risk items for mandatory review
        for risk in risk_assessment.risks:
            if risk.severity == Severity.HIGH:
                items.append({
                    "obligation_id": risk.obligation_id,
                    "reason": f"High-risk clause: {risk.title}",
                    "type": "high_risk",
                    "category": risk.category.value,
                    "action_required": risk.action_required,
                })

        return items

    def _generate_summary(
        self,
        analysis: AnalysisResult,
        risk_assessment: RiskAssessment,
        verification: DocumentVerificationReport,
    ) -> str:
        """Generate a text summary of the analysis."""
        lines = []

        # Parties
        if analysis.parties:
            party_strs = []
            for p in analysis.parties:
                tag = " (You)" if p.is_reader else ""
                party_strs.append(f"{p.name} ({p.role}){tag}")
            lines.append(f"Parties: {', '.join(party_strs)}")

        # Term
        term_parts = []
        if analysis.term:
            term_parts.append(analysis.term)
        if analysis.effective_date:
            term_parts.append(f"starting {analysis.effective_date}")
        if term_parts:
            lines.append(f"Term: {' '.join(term_parts)}")

        # Auto-renewal warning
        if analysis.auto_renewal.exists:
            ar = analysis.auto_renewal
            lines.append(
                f"Auto-Renewal: {ar.period or 'Yes'}, "
                f"notice required: {ar.notice_to_cancel or 'unspecified'}"
            )

        # Obligation count
        lines.append(f"Total Obligations: {len(analysis.obligations)}")

        # Verification status
        lines.append(
            f"Verification: {verification.verified_count}/{verification.total_obligations} "
            f"verified ({verification.verification_rate:.0%})"
        )

        # Risk summary
        rs = risk_assessment.summary
        lines.append(f"Overall Risk: {rs.overall_risk_level.value.upper()}")

        if rs.high_risk_count:
            lines.append(f"High-Risk Flags: {rs.high_risk_count}")
        if rs.medium_risk_count:
            lines.append(f"Medium-Risk Flags: {rs.medium_risk_count}")

        if rs.most_concerning:
            lines.append(f"Most Concerning: {rs.most_concerning}")

        return "\n".join(lines)

    def save_json(
        self,
        report: ContractReport,
        filename: Optional[str] = None,
    ) -> Path:
        """Save report as JSON file."""
        if filename is None:
            filename = Path(report.file_name).stem + "_analysis.json"

        output_path = self.output_dir / filename

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report.to_json())

        return output_path

    def save_text(
        self,
        report: ContractReport,
        filename: Optional[str] = None,
    ) -> Path:
        """Save human-readable text summary."""
        if filename is None:
            filename = Path(report.file_name).stem + "_summary.txt"

        output_path = self.output_dir / filename
        text = self.format_text_report(report)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)

        return output_path

    def save_markdown(
        self,
        report: ContractReport,
        filename: Optional[str] = None,
    ) -> Path:
        """Save markdown report."""
        if filename is None:
            filename = Path(report.file_name).stem + "_report.md"

        output_path = self.output_dir / filename
        md = self.format_markdown_report(report)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md)

        return output_path

    def format_text_report(self, report: ContractReport) -> str:
        """Format report as human-readable text (CLI output style)."""
        lines = []
        w = 60  # Width

        lines.append("=" * w)
        lines.append("CONTRACT ANALYSIS SUMMARY")
        lines.append("=" * w)
        lines.append("")

        lines.append(f"Document: {report.file_name}")
        lines.append(f"Generated: {report.generated_at}")
        lines.append("")

        # Parties
        if report.parties:
            lines.append("Parties:")
            for p in report.parties:
                tag = " [YOU]" if p.get("is_reader") else ""
                lines.append(f"  - {p['name']} ({p['role']}){tag}")
            lines.append("")

        # Term info
        lines.append("Contract Terms:")
        lines.append(f"  Effective Date: {report.effective_date or 'Not specified'}")
        lines.append(f"  Term: {report.term or 'Not specified'}")
        lines.append(f"  Termination Notice: {report.termination_notice_period or 'Not specified'}")

        if report.auto_renewal.get("exists"):
            ar = report.auto_renewal
            lines.append("")
            lines.append("  [!] AUTO-RENEWAL DETECTED")
            lines.append(f"      Period: {ar.get('period', 'Unspecified')}")
            lines.append(f"      Notice to Cancel: {ar.get('notice_to_cancel', 'Unspecified')}")

        lines.append("")

        # Risk summary
        rs = report.risk_summary
        lines.append("=" * w)
        lines.append(f"RISK ASSESSMENT: {rs['overall_risk_level'].upper()}")
        lines.append("=" * w)
        lines.append("")

        # High risks
        high_risks = [r for r in report.risk_flags if r["severity"] == "high"]
        if high_risks:
            lines.append("[HIGH RISK] Critical Issues:")
            for i, risk in enumerate(high_risks, 1):
                lines.append(f"  {i}. {risk['title']}")
                lines.append(f"     {risk['description'][:80]}...")
                lines.append(f"     Location: {risk['source_location']}")
                lines.append(f"     Action: {risk['action_required']}")
                lines.append("")

        # Medium risks
        medium_risks = [r for r in report.risk_flags if r["severity"] == "medium"]
        if medium_risks:
            lines.append("[MEDIUM RISK] Notable Concerns:")
            for i, risk in enumerate(medium_risks, 1):
                lines.append(f"  {i}. {risk['title']} ({risk['source_location']})")
            lines.append("")

        # Low risks (just count)
        low_risks = [r for r in report.risk_flags if r["severity"] == "low"]
        if low_risks:
            lines.append(f"[LOW RISK] Minor Items: {len(low_risks)} found")
            lines.append("")

        # Items needing review
        if report.items_needing_review:
            lines.append("=" * w)
            lines.append("ITEMS NEEDING HUMAN REVIEW")
            lines.append("=" * w)
            lines.append("")

            for item in report.items_needing_review:
                if item["type"] == "possible_hallucination":
                    lines.append(f"  [?] {item['obligation_id']}: {item['reason']}")
                elif item["type"] == "high_risk":
                    lines.append(f"  [!] {item['obligation_id']}: {item['reason']}")
                else:
                    lines.append(f"  [-] {item['obligation_id']}: {item['reason']}")
            lines.append("")

        # Verification
        lines.append("=" * w)
        lines.append("VERIFICATION STATUS")
        lines.append("=" * w)
        lines.append(f"  Verification Rate: {report.verification_rate:.1%}")
        if report.has_hallucinations:
            lines.append("  [WARNING] Possible hallucinations detected - review flagged items")
        else:
            lines.append("  All source text verified against original document")
        lines.append("")

        # Obligations summary
        lines.append("=" * w)
        lines.append(f"OBLIGATIONS ({len(report.obligations)} total)")
        lines.append("=" * w)
        lines.append("")

        for obl in report.obligations[:10]:  # Show first 10
            risk_tag = ""
            if obl["risk_level"] == "high":
                risk_tag = " [HIGH RISK]"
            elif obl["risk_level"] == "medium":
                risk_tag = " [MEDIUM]"

            lines.append(f"  [{obl['id']}] {obl['party']}{risk_tag}")
            lines.append(f"    {obl['description'][:70]}...")
            if obl["deadline"]:
                lines.append(f"    Deadline: {obl['deadline']}")
            lines.append("")

        if len(report.obligations) > 10:
            lines.append(f"  ... and {len(report.obligations) - 10} more obligations")
            lines.append("")

        lines.append("=" * w)
        lines.append("END OF REPORT")
        lines.append("=" * w)

        return "\n".join(lines)

    def format_markdown_report(self, report: ContractReport) -> str:
        """Format report as Markdown."""
        lines = []

        lines.append(f"# Contract Analysis: {report.file_name}")
        lines.append("")
        lines.append(f"*Generated: {report.generated_at}*")
        lines.append("")

        # Summary box
        lines.append("## Summary")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")

        if report.parties:
            parties_str = ", ".join(
                f"{p['name']} ({p['role']})" for p in report.parties
            )
            lines.append(f"| Parties | {parties_str} |")

        lines.append(f"| Effective Date | {report.effective_date or 'Not specified'} |")
        lines.append(f"| Term | {report.term or 'Not specified'} |")
        lines.append(f"| Overall Risk | **{report.risk_summary['overall_risk_level'].upper()}** |")
        lines.append(f"| Obligations | {len(report.obligations)} |")
        lines.append(f"| Verification Rate | {report.verification_rate:.1%} |")
        lines.append("")

        # Auto-renewal warning
        if report.auto_renewal.get("exists"):
            ar = report.auto_renewal
            lines.append("> **Auto-Renewal Warning**")
            lines.append(f"> Period: {ar.get('period', 'Unspecified')}")
            lines.append(f"> Notice to Cancel: {ar.get('notice_to_cancel', 'Unspecified')}")
            lines.append("")

        # Risk Flags
        lines.append("## Risk Flags")
        lines.append("")

        high_risks = [r for r in report.risk_flags if r["severity"] == "high"]
        if high_risks:
            lines.append("### High Risk (Immediate Attention Required)")
            lines.append("")
            for risk in high_risks:
                lines.append(f"#### {risk['title']}")
                lines.append("")
                lines.append(f"- **Category:** {risk['category']}")
                lines.append(f"- **Location:** {risk['source_location']}")
                lines.append(f"- **Description:** {risk['description']}")
                lines.append(f"- **Action Required:** {risk['action_required']}")
                if risk.get('negotiation_suggestion'):
                    lines.append(f"- **Negotiation Tip:** {risk['negotiation_suggestion']}")
                lines.append("")

        medium_risks = [r for r in report.risk_flags if r["severity"] == "medium"]
        if medium_risks:
            lines.append("### Medium Risk (Review Recommended)")
            lines.append("")
            lines.append("| Risk | Category | Location |")
            lines.append("|------|----------|----------|")
            for risk in medium_risks:
                lines.append(f"| {risk['title']} | {risk['category']} | {risk['source_location']} |")
            lines.append("")

        low_risks = [r for r in report.risk_flags if r["severity"] == "low"]
        if low_risks:
            lines.append(f"### Low Risk ({len(low_risks)} items)")
            lines.append("")
            lines.append("Minor issues that may warrant attention but are generally acceptable.")
            lines.append("")

        # Items needing review
        if report.items_needing_review:
            lines.append("## Items Needing Human Review")
            lines.append("")
            for item in report.items_needing_review:
                lines.append(f"- **{item['obligation_id']}**: {item['reason']}")
            lines.append("")

        # Obligations
        lines.append("## Obligations")
        lines.append("")
        lines.append("| ID | Party | Type | Description | Risk |")
        lines.append("|----|-------|------|-------------|------|")

        for obl in report.obligations:
            desc = obl["description"][:50] + "..." if len(obl["description"]) > 50 else obl["description"]
            risk_badge = f"**{obl['risk_level'].upper()}**" if obl["risk_level"] != "low" else obl["risk_level"]
            lines.append(f"| {obl['id']} | {obl['party']} | {obl['type']} | {desc} | {risk_badge} |")

        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("*This report was generated by DVS Legal Contract Flagger.*")

        return "\n".join(lines)

    def print_cli_summary(self, report: ContractReport) -> None:
        """Print CLI-style summary to stdout."""
        print(self.format_text_report(report))


def generate_report(
    analysis: AnalysisResult,
    risk_assessment: RiskAssessment,
    verification: DocumentVerificationReport,
    output_dir: str | Path = "results",
    save_json: bool = True,
    save_text: bool = True,
    save_markdown: bool = False,
) -> ContractReport:
    """
    Convenience function to generate and save all reports.

    Args:
        analysis: AnalysisResult from analyzer
        risk_assessment: RiskAssessment from risk_scorer
        verification: DocumentVerificationReport from verifier
        output_dir: Directory to save outputs
        save_json: Whether to save JSON report
        save_text: Whether to save text summary
        save_markdown: Whether to save markdown report

    Returns:
        ContractReport object
    """
    reporter = ContractReporter(output_dir)
    report = reporter.generate_report(analysis, risk_assessment, verification)

    saved_files = []

    if save_json:
        json_path = reporter.save_json(report)
        saved_files.append(str(json_path))

    if save_text:
        text_path = reporter.save_text(report)
        saved_files.append(str(text_path))

    if save_markdown:
        md_path = reporter.save_markdown(report)
        saved_files.append(str(md_path))

    if saved_files:
        print(f"Reports saved to: {', '.join(saved_files)}")

    return report


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))

    from src.analyzer import analyze_contract
    from src.extractor import extract_contract
    from src.risk_scorer import score_risks
    from src.verifier import verify_analysis

    if len(sys.argv) < 2:
        print("Usage: python -m src.reporter <contract_file>")
        print("Set ANTHROPIC_API_KEY environment variable first.")
        sys.exit(1)

    file_path = sys.argv[1]

    try:
        print(f"Processing: {file_path}")

        print("Extracting text...", end=" ", flush=True)
        extraction = extract_contract(file_path)
        print(f"done ({extraction.total_pages} pages)")

        print("Pass 1: Extracting obligations...", end=" ", flush=True)
        analysis = analyze_contract(file_path, verbose=False)
        print(f"done ({len(analysis.obligations)} obligations found)")

        print("Verifying source attribution...", end=" ", flush=True)
        verification = verify_analysis(analysis, extraction)
        print(f"done ({verification.verified_count}/{verification.total_obligations} verified)")

        print("Pass 2: Analyzing risks...", end=" ", flush=True)
        risk_assessment = score_risks(analysis)
        print("done")

        print()

        # Generate and display report
        reporter = ContractReporter("results")
        report = reporter.generate_report(analysis, risk_assessment, verification)

        # Print CLI summary
        reporter.print_cli_summary(report)

        # Save all formats
        json_path = reporter.save_json(report)
        text_path = reporter.save_text(report)
        md_path = reporter.save_markdown(report)

        print(f"\nReports saved:")
        print(f"  JSON:     {json_path}")
        print(f"  Text:     {text_path}")
        print(f"  Markdown: {md_path}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
