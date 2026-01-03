# Ground Truth Annotation Guide

This directory contains manually annotated ground truth files for evaluating system accuracy.

## Audit Workflow

Each ground truth file has a companion markdown audit file for tracking verification progress:

```
mutual_nda_ground_truth.json     <- Annotations
mutual_nda_audit.md              <- Audit checklist and notes
```

### JSON Audit Fields

Each ground truth JSON includes:
- `_audited`: boolean - Has this been manually verified?
- `_audit_date`: When the audit was completed
- `_missed_obligations`: Array of obligations the AI missed
- `_false_positives`: Array of incorrect extractions to remove

Each obligation and risk_flag includes:
- `_audit_status`: "pending" | "verified" | "incorrect" | "needs_revision"
- `_audit_notes`: Notes about the item (e.g., "Source text is paraphrased")

### Audit Process

1. Open the contract and its `_ground_truth.json` side by side
2. Use the `_audit.md` checklist to track progress
3. For each obligation/risk:
   - Verify source_text appears verbatim in contract
   - Confirm section reference is correct
   - Update `_audit_status` in JSON
4. Document missed items in `_missed_obligations`
5. Document hallucinations in `_false_positives`
6. Set `_audited: true` and `_audit_date` when complete

## File Naming Convention

For each contract, create a matching ground truth file:
```
sample_contracts/
  residential_lease_agreement.txt
ground_truth/
  residential_lease_agreement_ground_truth.json
```

## How to Annotate

1. Read the entire contract carefully
2. Copy `_template.json` and rename to `<contract_name>_ground_truth.json`
3. Fill in each section following the schema below
4. Be exhaustive - capture ALL obligations, not just obvious ones

## Schema Reference

### Parties
```json
{
  "name": "Acme Corp",           // Exact name as written in contract
  "role": "Landlord",            // Landlord, Tenant, Employer, Employee, etc.
  "is_reader": false             // true if this is "you" (the reviewing party)
}
```

### Obligations
Types: `payment`, `deadline`, `restriction`, `requirement`, `notification`, `consent`

```json
{
  "id": "OBL-001",               // Sequential ID
  "party": "Tenant",             // Who is obligated
  "type": "payment",             // One of the types above
  "description": "Monthly rent", // Plain English description
  "deadline": "1st of month",    // null if no deadline
  "conditions": null,            // Conditions that trigger this obligation
  "source_text": "Tenant shall pay...",  // EXACT quote from contract
  "source_location": "Section 3"         // Where in contract
}
```

### Risk Flags
Categories: `financial_exposure`, `time_bomb`, `asymmetric_terms`, `competitive_restriction`, `unclear_obligation`, `consent_risk`, `dispute_resolution`

Severities: `high`, `medium`, `low`

```json
{
  "obligation_id": "OBL-005",    // Links to obligation
  "category": "time_bomb",
  "severity": "high",
  "title": "Short auto-renewal notice",
  "description": "Only 30 days notice required...",
  "source_text": "Contract renews automatically unless...",
  "source_location": "Section 12"
}
```

## Annotation Tips

### What to Capture as Obligations
- Payment requirements (amounts, due dates)
- Deadlines (notice periods, response times)
- Restrictions (non-compete, confidentiality, exclusivity)
- Requirements (insurance, maintenance, reporting)
- Notification duties (changes, breaches, events)
- Consent requirements (approvals needed)

### What Makes Something High Risk
- Unlimited liability or uncapped damages
- Very short notice periods (< 30 days)
- Auto-renewal with penalty for missing notice
- Unilateral change rights
- Non-compete beyond 1 year or broad geographic scope
- Mandatory arbitration in unfavorable venue
- Assignment without consent

### Source Text Rules
- Copy EXACT text from the contract
- Include enough context to verify (typically 1-3 sentences)
- Don't paraphrase or summarize
- If clause spans multiple sentences, include all relevant text

## Running Evaluation

After creating ground truth files:
```bash
python scripts/evaluate.py data/sample_contracts/mutual_nda.txt
```

This compares system output against your ground truth annotations.
