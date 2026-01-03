# Audit: employment_agreement.txt

**Audited:** Not yet
**Audit Date:** -
**Time Spent:** -
**Auditor:** -

---

## Verified

_Mark each obligation/risk as you verify it against the source contract_

### Obligations
- [X] OBL-001: Devote full working time, attention, and best efforts to job duties
- [X] OBL-002: Comply with all Company policies, procedures, rules, and regulations
- [X] OBL-003: Relocate to any Company location domestic or international as business needs dictate
- [X] OBL-004: Submit PTO requests at least 2 weeks in advance
- [X] OBL-005: Submit expense reports within 30 days of incurring expense
- [X] OBL-006: Hold all Confidential Information in strict confidence and not disclose to third parties
- [X] OBL-007: Not use Confidential Information for any purpose other than job duties
- [X] OBL-008: Return all Company property and materials containing Confidential Information upon termination
- [X] OBL-009: Assign all Work Product and IP rights to Company
- [X] OBL-010: Waive all moral rights in Work Product
- [X] OBL-011: Non-compete: Cannot work for competitors for 24 months post-termination, worldwide
- [FLAG] OBL-012: Cannot provide services to named competitors (Microsoft, Google, Amazon, Apple, Meta, etc.)
- [X] OBL-013: Non-solicitation: Cannot solicit or hire Company employees for 24 months post-termination
- [X] OBL-014: Cannot solicit Company customers or interfere with business relationships for 24 months
- [LIKELY] OBL-015: Non-disparagement: Cannot make negative statements about Company indefinitely
- [X] OBL-016: Provide 4 weeks written notice to resign
- [X] OBL-017: Upon termination, immediately return all Company property and resign from positions
- [X] OBL-018: Execute general release of claims to receive severance
- [X] OBL-019: Pay Company's attorneys' fees if Company must enforce agreement
- [X] OBL-020: Grant Company perpetual exclusive license to Prior Inventions if incorporated into products
- [X] OBL-021: Pay base salary of $175,000 annually

### Risk Flags
- [X] RISK-001: 24-month worldwide non-compete (HIGH)
- [LIKELY] RISK-002: Named competitors include all major tech companies (HIGH)
- [FLAG] RISK-003: 24-month employee non-solicitation
- [FLAG] RISK-004: Perpetual one-sided non-disparagement
- [X] RISK-005: At-will with no employee protections (HIGH)
- [FLAG] RISK-006: Extremely broad definition of 'Cause' (HIGH)
- [X] RISK-007: Mandatory relocation without additional compensation (HIGH)
- [X] RISK-008: No PTO payout on termination
- [X] RISK-009: Bonus requires employment on payment date
- [LIKELY] RISK-010: Broad IP assignment including personal projects
- [X] RISK-011: Exclusive license to Prior Inventions (HIGH)
- [X] RISK-012: Mandatory arbitration for all claims
- [X] RISK-013: Class action waiver
- [X] RISK-014: Employee pays Company's enforcement costs
- [X] RISK-015: Non-compete extended by duration of violation

---

## Issues Found

_Document any problems with the ground truth annotations_

| ID | Issue | Resolution |
|----|-------|------------|
| - | - | - |

---

## Missed by AI

_Obligations or risks present in contract but not captured by system_

| Section | Description | Suggested Obligation/Risk |
|---------|-------------|---------------------------|
| Line 19 | Employee shall perform all duties and responsibilities cu... | Review: contains 'shall' |
| Line 23 | Employee's primary work location shall be the Company's A... | Review: contains 'shall' |
| Line 29 | Nothing in this Agreement shall be construed as a guarant... | Review: contains 'shall' |
| Line 35 | Any adjustment to salary shall be at the Company's sole d... | Review: contains 'shall' |
| Line 37 | Any bonus payment shall be determined in the Company's so... | Review: contains 'shall' |
| Line 39 | Subject to approval by the Company's Board of Directors, ... | Review: contains 'shall' |
| Line 39 | Such options shall vest over four (4) years with a one-ye... | Review: contains 'shall' |
| Line 43 | 4.1 Employee shall be eligible to participate in the Comp... | Review: contains 'shall' |
| Line 49 | 5.1 Employee shall be entitled to twenty (20) days of pai... | Review: contains 'shall' |
| Line 55 | 5.4 Employee shall not be entitled to any additional comp... | Review: contains 'shall' |

---

## Hallucinated (Remove)

_Items AI extracted that don't exist or are incorrect_

| System ID | Issue | Action |
|-----------|-------|--------|
| OBL-012 | Only 78% match - verify source text | Review |
| FLAG-003 | Only 70% match - verify source text | Review |
| FLAG-004 | Only 69% match - verify source text | Review |
| FLAG-006 | Only 68% match - verify source text | Review |

---

## Risk Flag Adjustments

_Changes to severity or category_

| Risk ID | Current | Recommended | Reason |
|---------|---------|-------------|--------|
| - | - | - | - |

---

## Notes

_Additional observations for lessons learned_

- Auto-generated on 2026-01-03
- 21 obligations verified: 19 exact, 1 likely, 1 flagged
- 15 risk flags verified: 10 exact, 2 likely, 3 flagged
- 35 potential missed clauses found for review
