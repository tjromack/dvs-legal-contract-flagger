# Audit: saas_terms_of_service.txt

**Audited:** Not yet
**Audit Date:** -
**Time Spent:** -
**Auditor:** -

---

## Verified

_Mark each obligation/risk as you verify it against the source contract_

### Obligations
- [ ] OBL-001: Responsible for Authorized Users' actions
- [ ] OBL-002: Ensure Authorized Users comply
- [ ] OBL-003: Maintain login credential confidentiality
- [ ] OBL-004: Immediately notify of unauthorized access
- [ ] OBL-005: No reverse engineering
- [ ] OBL-006: No competitive product building
- [ ] OBL-007: No automated tools without consent
- [ ] OBL-008: Grant Company license to Customer Data
- [ ] OBL-009: Responsible for data accuracy and consents
- [ ] OBL-010: Pay fees annually in advance
- [ ] OBL-011: Pay invoices within 30 days
- [ ] OBL-012: Pay all taxes
- [ ] OBL-013: 60 days notice to prevent auto-renewal
- [ ] OBL-014: Pay through end of term even if terminating
- [ ] OBL-015: Pay outstanding fees upon termination
- [ ] OBL-016: Assign all Feedback to Company
- [ ] OBL-017: Indemnify Company
- [ ] OBL-018: Consent to cross-border data transfer
- [ ] OBL-019: Agree to subprocessors
- [ ] OBL-020: Comply with export control laws
- [ ] OBL-021: File claims within 1 year
- [ ] OBL-022: Company provides 99.5% uptime target

### Risk Flags
- [ ] RISK-001: Auto-renewal with 60-day notice (HIGH)
- [ ] RISK-002: No refunds under any circumstances (HIGH)
- [ ] RISK-003: Fee increases with 30 days notice (HIGH)
- [ ] RISK-004: Suspension after 15 days past due (HIGH)
- [ ] RISK-005: Company can terminate for any reason (HIGH)
- [ ] RISK-006: Must pay through end of term (HIGH)
- [ ] RISK-007: No service credits for downtime
- [ ] RISK-008: Can modify/discontinue features anytime (HIGH)
- [ ] RISK-009: Broad Customer Data usage rights (HIGH)
- [ ] RISK-010: Liability capped at 3 months fees (HIGH)
- [ ] RISK-011: No liability for data loss (HIGH)
- [ ] RISK-012: No liability for data breaches
- [ ] RISK-013: 1-year statute of limitations (HIGH)
- [ ] RISK-014: Mandatory arbitration in Delaware
- [ ] RISK-015: Class action and jury waivers
- [ ] RISK-016: Unilateral Agreement modification
- [ ] RISK-017: Cross-border data transfer consent
- [ ] RISK-018: 1.5% monthly late fee (18% APR)
- [ ] RISK-019: Vague breach notification timing

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
| - | - | - |

---

## Hallucinated (Remove)

_Items AI extracted that don't exist or are incorrect_

| System ID | Issue | Action |
|-----------|-------|--------|
| - | - | - |

---

## Risk Flag Adjustments

_Changes to severity or category_

| Risk ID | Current | Recommended | Reason |
|---------|---------|-------------|--------|
| - | - | - | - |

---

## Notes

_Additional observations for lessons learned_

- This is a click-wrap agreement with very provider-favorable terms
- 3-month liability cap combined with no data loss liability is a significant risk
- Section 3.3 data usage rights for "aggregated data" effectively never expire
- No SLA remedies despite uptime target - makes the 99.5% target meaningless
- May have GDPR compliance issues for EU customers (data transfer, processing)
