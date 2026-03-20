import streamlit as st
import pandas as pd
from payslip_generator import generate_payslip_pdf

# tab_payslip content starts here:
st.subheader("My Payslip")

try:
    # Fetch payroll sheet — guards only see their own record
    payroll_df = get_data("Payroll")   # uses existing get_data() from app.py

    if payroll_df.empty:
        st.info("No payroll data available yet.")
    else:
        # Match by Employee Name (same as guard Name in roster)
        guard_name  = str(user['Name']).strip().upper()
        payroll_df['_name_upper'] = payroll_df['Employee Name'].astype(str).str.strip().str.upper()
        my_records  = payroll_df[payroll_df['_name_upper'] == guard_name].copy()

        if my_records.empty:
            st.warning("No payslip found for your account. Contact admin.")
        else:
            # If multiple periods, let guard pick which one
            if len(my_records) > 1:
                periods = my_records['Date Covered'].tolist()
                chosen  = st.selectbox("Select Pay Period", periods)
                row_data = my_records[my_records['Date Covered'] == chosen].iloc[0].to_dict()
            else:
                row_data = my_records.iloc[0].to_dict()
                st.caption(f"Pay Period: **{row_data.get('Date Covered', '')}**")

            # Numeric safety
            numeric_cols = [
                "Daily Rate", "Basic Salary", "Holiday", "Overtime pay",
                "Night Differential", "5 days Incentives", "Uniform Allowance",
                "Gross Pay", "SSS", "Pag-Ibig", "PhilHealth", "Loans",
                "FA Bonds", "Cash Advance", "Total Deduction", "NET PAY"
            ]
            for col in numeric_cols:
                try:    row_data[col] = float(row_data.get(col, 0) or 0)
                except: row_data[col] = 0.0

            # ── Summary cards ─────────────────────────────────────────────────
            st.markdown(f"""
                <div style="background:#001f3f;color:white;padding:16px;border-radius:12px;text-align:center;margin-bottom:12px;">
                    <div style="font-size:12px;opacity:0.7;">NET PAY</div>
                    <div style="font-size:28px;font-weight:bold;">₱ {row_data['NET PAY']:,.2f}</div>
                    <div style="font-size:11px;opacity:0.6;">{row_data.get('Date Covered','')}</div>
                </div>
            """, unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Earnings**")
                st.write(f"Basic Salary: ₱{row_data['Basic Salary']:,.2f}")
                st.write(f"Holiday: ₱{row_data['Holiday']:,.2f}")
                st.write(f"Overtime: ₱{row_data['Overtime pay']:,.2f}")
                st.write(f"Night Diff: ₱{row_data['Night Differential']:,.2f}")
                st.write(f"5-Day Incentive: ₱{row_data['5 days Incentives']:,.2f}")
                st.write(f"Uniform Allow.: ₱{row_data['Uniform Allowance']:,.2f}")
                st.markdown(f"**Gross Pay: ₱{row_data['Gross Pay']:,.2f}**")

            with c2:
                st.markdown("**Deductions**")
                st.write(f"SSS: ₱{row_data['SSS']:,.2f}")
                st.write(f"Pag-Ibig: ₱{row_data['Pag-Ibig']:,.2f}")
                st.write(f"PhilHealth: ₱{row_data['PhilHealth']:,.2f}")
                st.write(f"Loans: ₱{row_data['Loans']:,.2f}")
                st.write(f"FA Bonds: ₱{row_data['FA Bonds']:,.2f}")
                st.write(f"Cash Advance: ₱{row_data['Cash Advance']:,.2f}")
                st.markdown(f"**Total Deduction: ₱{row_data['Total Deduction']:,.2f}**")

            st.divider()

            # ── Download PDF ──────────────────────────────────────────────────
            if st.button("📄 Download My Payslip PDF", type="primary", use_container_width=True):
                pdf_bytes = generate_payslip_pdf(row_data)
                filename  = f"Payslip_{str(user['Name']).replace(' ','_')}_{str(row_data.get('Date Covered','')).replace('/','_')}.pdf"
                st.download_button(
                    label="⬇️ Save PDF",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    use_container_width=True
                )

except Exception as e:
    st.error(f"Could not load payslip: {e}")
