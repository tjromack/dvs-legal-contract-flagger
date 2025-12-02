"""
Create a sample PDF contract for testing the extractor.

Requires: pip install fpdf2
"""

import sys
from pathlib import Path

try:
    from fpdf import FPDF
except ImportError:
    print("fpdf2 not installed. Install with: pip install fpdf2")
    print("Alternatively, use the .txt sample contracts for testing.")
    sys.exit(1)


def create_sample_contract_pdf(output_path: Path):
    """Create a multi-page sample contract PDF."""

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Page 1 - Title and Parties
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "SAMPLE SERVICES AGREEMENT", ln=True, align="C")
    pdf.ln(10)

    pdf.set_font("Helvetica", "", 11)
    content_page1 = """
This Services Agreement ("Agreement") is entered into as of January 1, 2025 (the "Effective Date"), by and between:

SERVICE PROVIDER: Acme Solutions Inc., a Delaware corporation, with its principal place of business at 100 Main Street, New York, NY 10001 ("Provider")

CLIENT: Example Corp., a California corporation, with its principal place of business at 500 Market Street, San Francisco, CA 94105 ("Client")

RECITALS

WHEREAS, Provider is engaged in the business of providing software development and consulting services; and

WHEREAS, Client desires to engage Provider to perform certain services as described herein;

NOW, THEREFORE, in consideration of the mutual covenants and agreements contained herein, and for other good and valuable consideration, the receipt and sufficiency of which are hereby acknowledged, the parties agree as follows:
"""
    pdf.multi_cell(0, 6, content_page1.strip())

    # Page 2 - Definitions and Services
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, "ARTICLE I: DEFINITIONS", ln=True)
    pdf.set_font("Helvetica", "", 11)

    content_page2 = """
1.1 "Confidential Information" means any and all information, data, or materials that are proprietary to either party, including but not limited to trade secrets, technical data, business information, and customer information.

1.2 "Deliverables" means the work product, software, documentation, and other materials to be provided by Provider as specified in the Statement of Work.

1.3 "Services" means the professional services to be performed by Provider as described in the Statement of Work attached hereto as Exhibit A.

1.4 "Statement of Work" or "SOW" means a document describing the specific services, deliverables, timeline, and fees for a particular project.

ARTICLE II: SERVICES

2.1 Engagement. Client hereby engages Provider to perform the Services described in each Statement of Work executed by the parties.

2.2 Standard of Performance. Provider shall perform the Services in a professional and workmanlike manner, consistent with industry standards.

2.3 Personnel. Provider shall assign qualified personnel to perform the Services. Provider may substitute personnel upon notice to Client, provided that replacement personnel have substantially equivalent qualifications.

2.4 Client Cooperation. Client shall provide Provider with timely access to information, personnel, and resources reasonably necessary for Provider to perform the Services.
"""
    pdf.multi_cell(0, 6, content_page2.strip())

    # Page 3 - Compensation
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, "ARTICLE III: COMPENSATION", ln=True)
    pdf.set_font("Helvetica", "", 11)

    content_page3 = """
3.1 Fees. Client shall pay Provider the fees specified in each Statement of Work. Unless otherwise specified, fees shall be based on time and materials at Provider's then-current hourly rates.

3.2 Expenses. Client shall reimburse Provider for reasonable, pre-approved expenses incurred in performing the Services, including travel, lodging, and materials.

3.3 Invoicing. Provider shall invoice Client monthly for Services performed and expenses incurred during the preceding month. Invoices shall include reasonable detail of work performed.

3.4 Payment Terms. Payment is due within thirty (30) days of invoice date. Late payments shall accrue interest at the rate of 1.5% per month, or the maximum rate permitted by law, whichever is less.

3.5 Taxes. Fees do not include taxes. Client is responsible for all applicable sales, use, and other taxes, excluding taxes based on Provider's income.

ARTICLE IV: TERM AND TERMINATION

4.1 Term. This Agreement shall commence on the Effective Date and continue for an initial term of one (1) year, unless earlier terminated as provided herein. Thereafter, this Agreement shall automatically renew for successive one-year periods unless either party provides written notice of non-renewal at least sixty (60) days prior to the end of the then-current term.

4.2 Termination for Convenience. Either party may terminate this Agreement upon thirty (30) days' prior written notice to the other party.

4.3 Termination for Cause. Either party may terminate this Agreement immediately upon written notice if the other party materially breaches this Agreement and fails to cure such breach within fifteen (15) days after receiving written notice thereof.
"""
    pdf.multi_cell(0, 6, content_page3.strip())

    # Page 4 - Confidentiality and IP
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, "ARTICLE V: CONFIDENTIALITY", ln=True)
    pdf.set_font("Helvetica", "", 11)

    content_page4 = """
5.1 Protection of Confidential Information. Each party agrees to hold the other party's Confidential Information in strict confidence and not to disclose such information to any third party without prior written consent.

5.2 Permitted Disclosures. A party may disclose Confidential Information to its employees, contractors, and advisors who need to know such information and who are bound by confidentiality obligations at least as protective as those contained herein.

5.3 Exceptions. Confidential Information does not include information that: (a) is or becomes publicly available through no fault of the receiving party; (b) was known to the receiving party prior to disclosure; (c) is independently developed by the receiving party; or (d) is rightfully obtained from a third party without restriction.

ARTICLE VI: INTELLECTUAL PROPERTY

6.1 Pre-Existing IP. Each party retains all right, title, and interest in and to its pre-existing intellectual property.

6.2 Work Product. All Deliverables created by Provider specifically for Client under this Agreement shall be owned by Client upon full payment.

6.3 Provider Tools. Notwithstanding the foregoing, Provider shall retain all rights in and to any tools, methodologies, or know-how developed or used by Provider in performing the Services, including any improvements thereto.

6.4 License. To the extent any Provider Tools are incorporated into Deliverables, Provider hereby grants Client a non-exclusive, perpetual, royalty-free license to use such Provider Tools solely in connection with the Deliverables.
"""
    pdf.multi_cell(0, 6, content_page4.strip())

    # Page 5 - Liability and Indemnification
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, "ARTICLE VII: LIMITATION OF LIABILITY", ln=True)
    pdf.set_font("Helvetica", "", 11)

    content_page5 = """
7.1 Limitation of Liability. EXCEPT FOR BREACHES OF CONFIDENTIALITY OR INDEMNIFICATION OBLIGATIONS, IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING LOST PROFITS, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.

7.2 Cap on Liability. EXCEPT FOR BREACHES OF CONFIDENTIALITY OR INDEMNIFICATION OBLIGATIONS, EACH PARTY'S TOTAL CUMULATIVE LIABILITY ARISING OUT OF OR RELATING TO THIS AGREEMENT SHALL NOT EXCEED THE TOTAL FEES PAID OR PAYABLE BY CLIENT DURING THE TWELVE (12) MONTHS PRECEDING THE EVENT GIVING RISE TO THE CLAIM.

ARTICLE VIII: INDEMNIFICATION

8.1 Indemnification by Provider. Provider shall indemnify, defend, and hold harmless Client from and against any claims, damages, and expenses (including reasonable attorneys' fees) arising from: (a) Provider's gross negligence or willful misconduct; or (b) any claim that the Deliverables infringe any third-party intellectual property rights.

8.2 Indemnification by Client. Client shall indemnify, defend, and hold harmless Provider from and against any claims, damages, and expenses arising from: (a) Client's gross negligence or willful misconduct; or (b) any claim arising from Client's use of the Deliverables in violation of this Agreement.

ARTICLE IX: GENERAL PROVISIONS

9.1 Governing Law. This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware, without regard to its conflicts of law principles.

9.2 Dispute Resolution. Any dispute arising out of this Agreement shall be resolved through binding arbitration administered by the American Arbitration Association in accordance with its Commercial Arbitration Rules.

9.3 Entire Agreement. This Agreement constitutes the entire agreement between the parties and supersedes all prior negotiations and understandings.

9.4 Amendment. This Agreement may only be amended by written instrument signed by both parties.
"""
    pdf.multi_cell(0, 6, content_page5.strip())

    # Page 6 - Signature
    pdf.add_page()
    pdf.set_font("Helvetica", "", 11)

    content_page6 = """
9.5 Assignment. Neither party may assign this Agreement without the other party's prior written consent, except that either party may assign this Agreement to an affiliate or in connection with a merger or sale of substantially all of its assets.

9.6 Notices. All notices shall be in writing and delivered to the addresses set forth above.

9.7 Severability. If any provision of this Agreement is held to be invalid or unenforceable, the remaining provisions shall continue in full force and effect.

9.8 Waiver. The failure of either party to enforce any provision shall not constitute a waiver of such provision.

IN WITNESS WHEREOF, the parties have executed this Agreement as of the Effective Date.


ACME SOLUTIONS INC.                    EXAMPLE CORP.

By: _________________________          By: _________________________
Name: John Smith                       Name: Jane Doe
Title: Chief Executive Officer         Title: Chief Operating Officer
Date: January 1, 2025                  Date: January 1, 2025


EXHIBIT A: STATEMENT OF WORK
[To be attached separately]
"""
    pdf.multi_cell(0, 6, content_page6.strip())

    # Save PDF
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    print(f"Created: {output_path}")


if __name__ == "__main__":
    output_dir = Path(__file__).parent.parent / "data" / "sample_contracts"
    output_path = output_dir / "sample_services_agreement.pdf"

    create_sample_contract_pdf(output_path)
    print(f"\nPDF created with 6 pages at: {output_path}")
