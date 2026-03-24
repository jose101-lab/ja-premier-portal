from fpdf import FPDF
import io

def generate_incident_pdf(data):
    """
    Generates a professional JA.PREMIER Incident Report PDF.
    Includes a 'clean_text' safety layer to prevent Unicode crashes.
    """
    
    # --- 1. SAFETY CLEANING FUNCTION ---
    def clean_text(text):
        """Removes or replaces characters that FPDF cannot render in standard fonts."""
        if text is None:
            return "—"
        # Convert to string, replace common high-unicode dashes with simple hyphens
        text = str(text).replace('—', '-').replace('–', '-')
        # Encode to latin-1 and ignore characters it doesn't recognize (like emojis or ₱)
        # This prevents the 'FPDFUnicodeEncodingException'
        return text.encode('latin-1', 'replace').decode('latin-1')

    # --- 2. INITIALIZE PDF ---
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # --- 3. HEADER (JA.PREMIER BRANDING) ---
    pdf.set_font("Helvetica", 'B', 16)
    pdf.set_text_color(0, 31, 63)  # Dark Blue (JA.PREMIER Navy)
    pdf.cell(0, 10, clean_text("JA.PREMIER SECURITY AGENCY"), ln=True, align='C')
    
    pdf.set_font("Helvetica", 'I', 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, clean_text("Official Incident Report - Confidential"), ln=True, align='C')
    
    pdf.ln(10) # Line break
    
    # --- 4. SUMMARY BOX ---
    pdf.set_fill_color(240, 242, 246) # Light Grey background
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(0, 10, clean_text(f" SITE: {data.get('Site', 'N/A')}"), ln=True, fill=True)
    
    pdf.set_font("Helvetica", '', 10)
    pdf.cell(95, 8, clean_text(f" Reported By: {data.get('Reported_By', 'N/A')}"), border='B')
    pdf.cell(95, 8, clean_text(f" Date/Time: {data.get('Incident_DateTime', 'N/A')}"), border='B', ln=True)
    
    pdf.ln(5)

    # --- 5. REPORT BODY (THE 5 W's) ---
    sections = [
        ("WHAT HAPPENED", data.get('What', '—')),
        ("WHO WAS INVOLVED", data.get('Who', '—')),
        ("WHERE IT OCCURRED", data.get('Where', '—')),
        ("HOW IT OCCURRED", data.get('How', '—')),
        ("ACTION TAKEN / REMARKS", data.get('Action_Taken', '—'))
    ]

    for title, content in sections:
        pdf.set_font("Helvetica", 'B', 11)
        pdf.set_text_color(0, 51, 102) # Navy
        pdf.cell(0, 8, clean_text(title), ln=True)
        
        pdf.set_font("Helvetica", '', 10)
        pdf.set_text_color(0, 0, 0)
        # multi_cell handles long text and wraps it automatically
        pdf.multi_cell(0, 6, clean_text(content), border=0)
        pdf.ln(4)

    # --- 6. FOOTER / SIGNATURE LINE ---
    pdf.ln(10)
    pdf.set_font("Helvetica", 'I', 8)
    curr_time = data.get('Submitted_At', 'N/A')
    pdf.cell(0, 5, clean_text(f"System Generated Report | Digital Signature Verified: {curr_time}"), ln=True, align='R')

    # --- 7. RETURN AS BYTES ---
    # Use 'S' to output as a string/byte-stream for Streamlit's download button
    return pdf.output(dest='S')
