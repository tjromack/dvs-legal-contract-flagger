# DVS Legal Contract Clause Flagger

> An AI system that extracts obligations, deadlines, and risk indicators from legal contracts, with human-in-the-loop verification for high-stakes clauses.

[![Domain](https://img.shields.io/badge/Domain-Legal-blue)]()
[![Status](https://img.shields.io/badge/Status-In%20Progress-yellow)]()

---

## Problem Statement

### What problem does this solve?

Contracts are dense, lengthy, and written in language designed for lawyers—not the people who actually sign them. A typical apartment lease is 15-30 pages. Employment contracts bury non-competes in paragraph 47. Commercial agreements contain auto-renewal clauses that trigger unless you send written notice to a specific address 90 days in advance.

Most people sign contracts without fully understanding their obligations, deadlines, or exposure. Even professionals who *should* read contracts often skim them due to time pressure.

### Who has this problem?

- **Individuals** signing leases, employment agreements, or service contracts
- **Small business owners** reviewing vendor agreements without legal counsel
- **Paralegals and junior lawyers** doing first-pass contract review
- **Procurement teams** processing high volumes of vendor contracts

### Why does this matter?

Missed obligations lead to financial penalties, lost rights, and legal disputes. A single overlooked auto-renewal clause can lock a business into a bad vendor contract for another year. A missed deadline to exercise an option can cost thousands. The cost of a bad contract isn't just money—it's stress, time, and damaged relationships.

---

## Design Decisions

### Approaches Considered

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| **Rule-based regex extraction** | Fast, predictable, no API costs | Brittle; misses paraphrased language; high maintenance | ❌ Rejected |
| **Fine-tuned classification model** | High accuracy on trained categories | Requires labeled training data; expensive to build; narrow scope | ❌ Rejected |
| **LLM with structured prompting** | Handles varied language; generalizes well; fast to iterate | API costs; requires verification layer; potential hallucination | ✅ Selected |
| **Hybrid: LLM + rule-based validation** | Best of both; rules catch LLM errors | More complex architecture | ✅ Selected (enhancement) |

### Why This Architecture?

Contract language varies enormously. A non-compete might say "Employee agrees not to compete" or "During the Restricted Period, the Contractor shall refrain from engaging in any Competitive Activity." Rule-based systems break on this variation. LLMs handle semantic equivalence naturally.

However, LLMs can hallucinate clauses that don't exist or miss clauses that do. The hybrid approach uses the LLM for extraction and semantic understanding, then applies rule-based validation to verify extracted deadlines are actually present in the source text.

**Core constraint:** This system is for *flagging and summarizing*—not for legal advice. The supervision layer ensures humans make final decisions on anything high-stakes.

### Key Technical Choices

**LLM Selection: Claude 3.5 Sonnet (or GPT-4o)**

Optimizing for reasoning quality over speed. Contract analysis is not latency-sensitive—users can wait 30 seconds for a thorough analysis. Chose models with strong instruction-following to maintain structured output format.

**Extraction Strategy: Two-Pass Processing**

1. **Pass 1 — Obligation Extraction:** Identify all commitments, requirements, and restrictions for each party
2. **Pass 2 — Risk Analysis:** Evaluate extracted obligations against risk heuristics (see below)

Why two passes? Single-pass extraction conflates identification with evaluation. Separating them allows verification of extraction accuracy before risk scoring.

**Risk Heuristics (v1):**

| Risk Category | Trigger Patterns | Severity |
|---------------|------------------|----------|
| **Financial exposure** | Unlimited liability, indemnification without caps, liquidated damages | 🔴 High |
| **Time bombs** | Auto-renewal, notice periods < 30 days, retroactive effective dates | 🟠 Medium |
| **Asymmetric terms** | Unilateral amendment rights, one-sided termination, non-mutual NDAs | 🟠 Medium |
| **Competitive restrictions** | Non-compete, non-solicit, exclusivity, IP assignment beyond scope | 🔴 High |
| **Unclear obligations** | "Reasonable efforts," "as needed," undefined terms | 🟡 Low |

**Output Format: Structured JSON + Human-Readable Summary**

```json
{
  "parties": ["Party A (You)", "Party B (Landlord)"],
  "effective_date": "2025-01-01",
  "term": "12 months",
  "obligations": [
    {
      "party": "Party A",
      "description": "Pay monthly rent of $2,500",
      "deadline": "1st of each month",
      "source_text": "Tenant shall pay Base Rent... on the first day of each calendar month",
      "source_location": "Section 3.1, Page 4",
      "risk_level": "low",
      "risk_flags": []
    }
  ],
  "risk_flags": [
    {
      "category": "time_bomb",
      "description": "Lease auto-renews for 12 months unless 60-day written notice provided",
      "severity": "medium",
      "source_text": "...",
      "source_location": "Section 12.2, Page 11",
      "action_required": "Calendar reminder for [DATE - 60 days]"
    }
  ],
  "summary": "..."
}
```

---

## Verification Approach

### How do we know it works?

**Ground Truth Strategy:**

1. **Manual annotation:** Personally annotate 10 contracts of varying types (lease, employment, SaaS terms, vendor agreement) as the gold standard
2. **Clause-level verification:** For each extracted obligation, verify the `source_text` actually appears in the document
3. **Completeness check:** Compare AI-extracted obligations against manual annotation to measure recall

**Test Cases:**

| Test Case | Input | Expected Output | Result |
|-----------|-------|-----------------|--------|
| Standard residential lease | Sample_Lease_CA.pdf | 8-12 obligations, auto-renewal flag, security deposit terms | ⬜ |
| Employment agreement with non-compete | Employment_Template.pdf | Non-compete flagged as high risk, IP assignment identified | ⬜ |
| SaaS terms of service | Typical_SaaS_ToS.pdf | Limitation of liability flagged, auto-renewal identified | ⬜ |
| Clean/simple contract | Simple_NDA.pdf | Minimal flags, correctly identifies mutual vs. one-sided | ⬜ |
| Adversarial: no risky clauses | Benign_Contract.pdf | No false positives, returns "no significant risks found" | ⬜ |
| Adversarial: dense legalese | Complex_Commercial.pdf | Handles length and complexity without truncation errors | ⬜ |

**Failure Modes Tested:**

| Failure Mode | Test Method |
|--------------|-------------|
| **Hallucinated clauses** | Verify every `source_text` field exists verbatim in original document |
| **Missed obligations** | Compare against manually annotated contracts; measure recall |
| **Incorrect party attribution** | Test with contracts where Party A vs Party B naming is confusing |
| **Date parsing errors** | Include contracts with relative dates ("30 days after signing") and absolute dates |
| **Context window overflow** | Test with contracts > 50 pages to verify chunking strategy works |

**Accuracy Metrics:**

| Metric | Target | Definition |
|--------|--------|------------|
| **Extraction Precision** | > 90% | Of obligations extracted, % that actually exist in document |
| **Extraction Recall** | > 85% | Of actual obligations, % that were extracted |
| **Risk Flag Precision** | > 85% | Of flagged risks, % that are genuinely concerning |
| **Source Attribution Accuracy** | 100% | Every source_text must be verbatim from document |

Source attribution at 100% is non-negotiable. If the system cites text that isn't there, trust is destroyed.

---

## Supervision Layer

### Where does human judgment enter?

```
[Contract PDF] 
       │
       ▼
[Text Extraction & Chunking]
       │
       ▼
[LLM Pass 1: Obligation Extraction]
       │
       ▼
[Verification: Source Text Matching] ──── FAIL ──→ [Flag for Human Review]
       │                                              "Extraction uncertain"
       ▼ PASS
[LLM Pass 2: Risk Analysis]
       │
       ▼
[Confidence Scoring]
       │
       ├── High Confidence (>0.85) ──→ [Auto-include in report]
       │
       ├── Medium Confidence (0.6-0.85) ──→ [Include with "Verify" tag]
       │
       └── Low Confidence (<0.6) ──→ [Flag for Human Review]
                                        "AI uncertain about this clause"
```

### Escalation Triggers

The system routes to human review when:

| Trigger | Reason | Human Sees |
|---------|--------|------------|
| Source text not found in document | Possible hallucination | "Could not verify this extraction. Please review manually." |
| Risk severity = High | Stakes too high for automation | Full clause with context + why it was flagged |
| Confidence < 0.6 | Model uncertain | Clause + model's interpretation + "Please verify" |
| Contract type unrecognized | Out of distribution | "Unfamiliar contract type. Extraction may be incomplete." |
| Document length > 100 pages | Chunking may miss context | "Large document. Recommend section-by-section review." |

### What the human reviewer sees:

For each flagged item:

```
┌─────────────────────────────────────────────────────────────────┐
│ ⚠️  HUMAN REVIEW REQUIRED                                       │
├─────────────────────────────────────────────────────────────────┤
│ Reason: High-risk clause detected                               │
│                                                                 │
│ Category: Competitive Restriction                               │
│ Severity: 🔴 HIGH                                               │
│                                                                 │
│ AI Interpretation:                                              │
│ "Non-compete clause restricts employment in same industry       │
│  for 24 months within 50-mile radius after termination"         │
│                                                                 │
│ Source Text (Section 8.2, Page 12):                             │
│ "Employee agrees that for a period of twenty-four (24) months   │
│  following termination, Employee shall not engage in or         │
│  contribute to any Competing Business within fifty (50) miles   │
│  of any Company office location..."                             │
│                                                                 │
│ Suggested Action:                                               │
│ Negotiate shorter duration (6-12 months) or narrower geography  │
│                                                                 │
│ [✓ Confirm Flag] [✗ Dismiss] [✎ Edit Interpretation]            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Sources

| Source | Type | Access | Notes |
|--------|------|--------|-------|
| SEC EDGAR Filings | Public | https://www.sec.gov/cgi-bin/browse-edgar | 10-K exhibits contain real commercial contracts |
| Public contract templates | Public | Google "sample lease agreement PDF" | Good for common contract types |
| LegalZoom/Rocket Lawyer samples | Public | Various legal template sites | Standard templates |
| Personal contracts | Private | Your own lease, employment agreements | Best for realistic testing |
| Kaggle legal datasets | Public | https://www.kaggle.com/datasets | CUAD dataset has annotated contracts |

**CUAD Dataset (Recommended):**
The Contract Understanding Atticus Dataset contains 500+ contracts with 13,000+ expert annotations across 41 clause types. This is the gold standard for benchmarking.

https://www.atticusprojectai.org/cuad

---

## Limitations & Future Work

### What this system does NOT do:

- **Provide legal advice.** This is a summarization and flagging tool, not a lawyer.
- **Guarantee completeness.** It may miss unusual clause structures or domain-specific risks.
- **Handle scanned PDFs without OCR.** Requires text-extractable documents.
- **Understand jurisdiction-specific implications.** A non-compete enforceable in Texas may be void in California. System doesn't know this.
- **Negotiate on your behalf.** Identifies problems; solving them is human work.

### Known edge cases:

| Edge Case | System Behavior |
|-----------|-----------------|
| Exhibits/attachments referenced but not included | Flags as "Referenced document not available for review" |
| Defined terms with non-obvious meanings | May misinterpret if definition is far from usage |
| Multi-party contracts (>2 parties) | Handles but party attribution accuracy decreases |
| Non-English contracts | Not supported in v1 |
| Contracts with heavy redactions | Flags as "Document contains redactions; analysis incomplete" |

### If I had more time:

- [ ] Fine-tune extraction on CUAD dataset for higher accuracy
- [ ] Add jurisdiction-aware risk scoring (CA non-competes, NY tenant rights, etc.)
- [ ] Build web interface for drag-and-drop analysis
- [ ] Integrate calendar export for deadline tracking
- [ ] Support contract comparison (your version vs. their version)
- [ ] Add negotiation playbook suggestions per clause type

---

## Run It Yourself

### Prerequisites

```
python >= 3.10
Anthropic API key or OpenAI API key
```

### Setup

```bash
# Clone the repo
git clone https://github.com/[USERNAME]/dvs-legal-contract-flagger.git
cd dvs-legal-contract-flagger

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Add your API key to .env
```

### Usage

```bash
# Analyze a single contract
python main.py --input contracts/sample_lease.pdf --output results/

# Analyze multiple contracts
python main.py --input contracts/ --output results/
```

### Example Output

```bash
$ python main.py --input contracts/apartment_lease.pdf --output results/

Processing: apartment_lease.pdf
Extracting text... done (23 pages)
Pass 1: Extracting obligations... done (14 obligations found)
Verifying source attribution... done (14/14 verified)
Pass 2: Analyzing risks... done

============ SUMMARY ============
Document: apartment_lease.pdf
Parties: Tenant (You), Lakewood Properties LLC (Landlord)
Term: 12 months (Jan 1, 2025 - Dec 31, 2025)

🔴 HIGH RISK FLAGS (2):
  1. Unlimited liability for damages beyond security deposit (Section 9.3)
  2. Landlord may enter without notice "in emergencies" - undefined (Section 15.1)

🟠 MEDIUM RISK FLAGS (3):
  1. Auto-renewal for 12 months unless 60-day written notice (Section 22.4)
  2. Late fee of $150 if rent not received by 5th of month (Section 3.2)
  3. Tenant responsible for all repairs under $200 (Section 11.1)

⚠️  ITEMS NEEDING HUMAN REVIEW (1):
  1. Complex sublet clause - AI confidence low (Section 18.2)

Full report saved to: results/apartment_lease_analysis.json
```

---

## Project Structure

```
dvs-legal-contract-flagger/
├── README.md
├── requirements.txt
├── .env.example
├── main.py
├── src/
│   ├── __init__.py
│   ├── extractor.py        # PDF text extraction and chunking
│   ├── analyzer.py         # LLM-based obligation extraction
│   ├── risk_scorer.py      # Risk heuristics and scoring
│   ├── verifier.py         # Source text verification
│   └── reporter.py         # Output formatting
├── prompts/
│   ├── extraction.txt      # Prompt for obligation extraction
│   └── risk_analysis.txt   # Prompt for risk evaluation
├── data/
│   └── sample_contracts/   # Test contracts
├── tests/
│   ├── test_extractor.py
│   ├── test_analyzer.py
│   └── test_verifier.py
└── results/
```

---

## Lessons Learned

### What worked well:
- [To be filled after implementation]

### What I'd do differently:
- [To be filled after implementation]

### Unexpected challenges:
- [To be filled after implementation]

---

## Author

**[Trevor J. Romack]**
- GitHub: [@tjromack](https://github.com/tjromack)
- LinkedIn: [Profile](https://linkedin.com/in/tjromack)
- X: [@tjromack](https://x.com/tjromack)

---

*This project is part of a Design-Verify-Supervise portfolio demonstrating AI system architecture, verification methodology, and human-in-the-loop design.*
