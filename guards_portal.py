from payslip_generator import generate_payslip_pdf
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import os
import base64

# --- 1. INITIAL CONFIGURATION ---
LOGO_URL = "https://jose101-lab.github.io/ja-premier-portal/agency_logo.png"

st.set_page_config(
    page_title="JA.PREMIER",
    layout="centered",
    page_icon=LOGO_URL
)

# --- 2. UI CLEANUP ---
st.markdown("""
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="JA.PREMIER">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#001f3f">
    <style>
        #MainMenu  { display: none !important; }
        header     { display: none !important; }
        footer     { display: none !important; }
        .block-container { padding-top: 2rem; padding-bottom: 1rem; }
    </style>
""", unsafe_allow_html=True)

# --- 3. CONSTANTS ---
ATTENDANCE_SCRIPT_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbx5lpKgFFZe_f5D1_hQFeLrfwnQaMLmfJFqYt3s6PAhkyOTnFdT-sHYH-VoEXE6Bk5D/exec"
)

base_path = os.path.dirname(os.path.abspath(__file__))
logo_path = os.path.join(base_path, "agency_logo.png")

# --- 4. CONNECT TO GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 5. UTILITY FUNCTIONS ---
def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

def clean_to_digits(value):
    v = str(value).replace('.0', '').strip()
    digits = "".join(filter(str.isdigit, v))
    if len(digits) == 10 and digits.startswith('9'):
        return "0" + digits
    return digits

def get_data(sheet_name):
    return conn.read(worksheet=sheet_name, ttl=0)

def style_status(val):
    val_upper = str(val).upper().strip()
    if val_upper == 'APPROVED':
        return 'background-color: #28a745; color: white; font-weight: bold;'
    elif val_upper == 'PENDING':
        return 'background-color: #ffc107; color: black; font-weight: bold;'
    elif val_upper == 'DENIED':
        return 'background-color: #dc3545; color: white; font-weight: bold;'
    return ''

def submit_request(req_type, details):
    with st.spinner("Submitting request..."):
        clean_mob = clean_to_digits(st.session_state.user_data['Mobile_Number'])
        new_req = pd.DataFrame([{
            "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Mobile_Number": clean_mob,
            "Name": st.session_state.user_data['Name'],
            "Type": req_type,
            "Details": details,
            "Status": "PENDING"
        }])
        try:
            existing_reqs = get_data("Request")
            updated_reqs = pd.concat([existing_reqs, new_req], ignore_index=True)
            conn.update(worksheet="Request", data=updated_reqs)
            st.success("Request sent!")
            st.cache_data.clear()
        except Exception as e:
            st.error(f"Error: {e}")

# --- 6. SESSION MANAGEMENT ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_data = None

# --- 7. LOGIN SCREEN ---
if not st.session_state.authenticated:
    st.markdown("""
        <style>
        .force-center {
            display: flex;
            justify-content: center;
            align-items: center;
            width: 100%;
            margin-bottom: 10px;
        }
        .logo-img { width: 150px; height: auto; }
        .welcome-text {
            text-align: center;
            color: #001f3f;
            font-weight: bold;
            margin-bottom: 15px;
            font-size: 1.1rem;
        }
        </style>
    """, unsafe_allow_html=True)

    if os.path.exists(logo_path):
        binary_logo = get_base64_of_bin_file(logo_path)
        st.markdown(
            f'<div class="force-center">'
            f'<img src="data:image/png;base64,{binary_logo}" class="logo-img">'
            f'</div>',
            unsafe_allow_html=True
        )

    st.markdown(
        "<h1 style='text-align: center; color: #001f3f; margin-top: 0px;'>JA.PREMIER Login</h1>",
        unsafe_allow_html=True
    )

    mobile_input = st.text_input("Mobile Number", placeholder="09xxxxxxxxx")

    if mobile_input:
        try:
            roster_df = get_data("Rosters")
            roster_df['Mobile_Number_Clean'] = roster_df['Mobile_Number'].apply(clean_to_digits)
            search_mob = clean_to_digits(mobile_input)
            match = roster_df[roster_df['Mobile_Number_Clean'] == search_mob]
            if not match.empty:
                guard_name = match.iloc[0]['Name']
                st.markdown(
                    f'<p class="welcome-text">Welcome, {guard_name}!</p>',
                    unsafe_allow_html=True
                )
        except:
            pass

    password_input = st.text_input("Password", type="password")

    if st.button("Login", use_container_width=True):
        with st.spinner("Verifying..."):
            try:
                df = get_data("Rosters")
                df.columns = [str(c).strip() for c in df.columns]
                df['Mobile_Number_Clean'] = df['Mobile_Number'].apply(clean_to_digits)
                typed_mobile_clean = clean_to_digits(mobile_input)
                user_row = df[df['Mobile_Number_Clean'] == typed_mobile_clean]

                if not user_row.empty:
                    stored_password = str(user_row.iloc[0]['Password']).strip()
                    if str(password_input).strip() == stored_password:
                        st.session_state.authenticated = True
                        st.session_state.user_data = user_row.iloc[0].to_dict()
                        st.rerun()
                    else:
                        st.error("Incorrect password.")
                else:
                    st.error("Mobile number not found.")
            except Exception as e:
                st.error(f"Login System Error: {e}")

# --- 8. LOGGED IN CONTENT ---
else:
    user = st.session_state.user_data

    raw_id = user.get('Security_ID', 'N/A')
    try:
        clean_id = (
            str(int(float(raw_id)))
            if pd.notna(raw_id) and str(raw_id).lower() != 'nan'
            else "N/A"
        )
    except:
        clean_id = "N/A"

    is_temp = str(user.get('Is_Temporary', 'False')).upper() == 'TRUE'

    if is_temp:
        st.title("Update Password")
        new_pass     = st.text_input("New Password", type="password")
        confirm_pass = st.text_input("Confirm", type="password")
        if st.button("Update"):
            if new_pass == confirm_pass and len(new_pass) > 3:
                st.success("Updated!")
                st.session_state.authenticated = False
                st.rerun()
    else:
        st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())

        with st.spinner("Fetching Schedule..."):
            guards_tab_df      = get_data("GUARDS")
            current_guard_name = str(user['Name']).strip().upper()
            guard_assignments  = guards_tab_df[
                guards_tab_df['Guard Name'].astype(str).str.strip().str.upper() == current_guard_name
            ]

            if not guard_assignments.empty:
                guard_assignments['Effective Date'] = pd.to_datetime(
                    guard_assignments['Effective Date'], dayfirst=True, errors='coerce'
                )
                latest_assignment = guard_assignments.sort_values('Effective Date', ascending=False).iloc[0]
                assigned_site = str(latest_assignment['Site']).strip()
            else:
                assigned_site = "Floating / Unassigned"

        col_title, col_refresh = st.columns([5, 1])
        with col_title:
            st.title(f"Hello, {user['Name']}")
        with col_refresh:
            st.markdown("<div style='padding-top:18px;'>", unsafe_allow_html=True)
            if st.button("↻", help="Refresh page"):
                st.cache_data.clear()
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        # --- 4 TABS including new Payslip tab ---
        tab1, tab2, tab3, tab4 = st.tabs(["Attendance", "Requests", "Profile", "Payslip"])

        # ── TAB 1: ATTENDANCE ────────────────────────────────────────────────
        with tab1:
            st.subheader("Daily Time Record")
            st.info(f"Assigned to: **{assigned_site}**")

            st.markdown("### Post Orders")
            try:
                orders_df = get_data("PostOrders")
                orders_df['Site_Clean'] = orders_df['Site'].astype(str).str.strip().str.upper()
                site_orders = orders_df[orders_df['Site_Clean'] == assigned_site.upper()]

                if not site_orders.empty:
                    possible_cols = ['Orders', 'Order_Content', 'Instructions']
                    found_col = next((c for c in possible_cols if c in site_orders.columns), None)

                    if found_col:
                        specific_order = site_orders.iloc[0][found_col]
                        st.warning(f"**Instructions:**\n\n{specific_order}")

                        if st.button("CONFIRM READ", use_container_width=True):
                            new_log = pd.DataFrame([{
                                "Timestamp":     datetime.now().strftime("%Y-%m-%d %I:%M %p"),
                                "Guard_Name":    user['Name'],
                                "Site":          assigned_site,
                                "Order_Content": specific_order,
                                "Status":        "CONFIRMED READ"
                            }])
                            try:
                                existing_logs = get_data("PostOrderLogs")
                                updated_logs  = pd.concat([existing_logs, new_log], ignore_index=True)
                                conn.update(worksheet="PostOrderLogs", data=updated_logs)
                                st.success("Sent to Command Center!")
                            except:
                                st.error("Log error.")
                else:
                    st.success("Standard protocols apply today.")
            except Exception:
                st.caption("Post Orders ready.")

            st.divider()
            unified_url = f"{ATTENDANCE_SCRIPT_URL}?name={user['Name']}&site={assigned_site}"
            st.link_button("CLOCK IN / OUT", unified_url, use_container_width=True, type="primary")

        # ── TAB 2: REQUESTS ──────────────────────────────────────────────────
        with tab2:
            st.subheader("New Request")
            with st.form("request_form", clear_on_submit=True):
                req_type = st.selectbox("Type", ["Leave", "Cash Advance", "Equipment", "Schedule", "Other"])
                details  = st.text_area("Details")
                if st.form_submit_button("Submit"):
                    if details:
                        submit_request(req_type, details)

            st.divider()
            st.subheader("History")
            try:
                all_reqs = get_data("Request")
                user_mob = clean_to_digits(user['Mobile_Number'])
                all_reqs['Mobile_Number_Clean'] = all_reqs['Mobile_Number'].apply(clean_to_digits)
                my_reqs = all_reqs[all_reqs['Mobile_Number_Clean'] == user_mob].copy()

                if not my_reqs.empty:
                    display_reqs   = my_reqs[['Date', 'Type', 'Details', 'Status']].sort_values('Date', ascending=False)
                    styled_display = display_reqs.style.map(style_status, subset=['Status'])
                    st.dataframe(styled_display, hide_index=True, use_container_width=True)
                else:
                    st.info("No requests.")
            except:
                st.error("History Error.")

        # ── TAB 3: PROFILE ───────────────────────────────────────────────────
        with tab3:
            st.subheader("My Info")
            st.write(f"**Name:** {user['Name']}")
            st.write(f"**Mobile:** {clean_to_digits(user['Mobile_Number'])}")
            st.write(f"**Security ID:** {clean_id}")

        # ── TAB 4: PAYSLIP ───────────────────────────────────────────────────
        with tab4:
            st.subheader("My Payslip")
            try:
                # Check if admin has published payslips
                ctrl_df      = get_data("PayrollControl")
                is_published = (
                    not ctrl_df.empty and
                    str(ctrl_df.iloc[0].get("Status", "")).upper() == "PUBLISHED"
                )

                if not is_published:
                    st.markdown(
                        """<div style="background:#f8f9fa;border-left:6px solid #001f3f;"""
                        """padding:20px;border-radius:8px;text-align:center;margin-top:20px;">"""
                        """<div style="font-size:40px;margin-bottom:10px;">&#128203;</div>"""
                        """<div style="font-size:16px;font-weight:bold;color:#001f3f;">"""
                        """No payslip available yet</div>"""
                        """<div style="font-size:13px;color:#666;margin-top:6px;">"""
                        """Your payslip will appear here once admin releases it.</div>"""
                        """</div>""",
                        unsafe_allow_html=True
                    )
                else:
                    payroll_df = get_data("Payroll")

                    if payroll_df.empty:
                        st.info("No payroll data available yet.")
                    else:
                        guard_name_upper = str(user["Name"]).strip().upper()
                        payroll_df["_name_upper"] = payroll_df["Employee Name"].astype(str).str.strip().str.upper()
                        my_records = payroll_df[payroll_df["_name_upper"] == guard_name_upper].copy()

                        if my_records.empty:
                            st.warning("No payslip found for your account. Contact admin.")
                        else:
                            if len(my_records) > 1:
                                periods  = my_records["Date Covered"].tolist()
                                chosen   = st.selectbox("Select Pay Period", periods)
                                row_data = my_records[my_records["Date Covered"] == chosen].iloc[0].to_dict()
                            else:
                                row_data = my_records.iloc[0].to_dict()
                                st.caption(f"Pay Period: **{row_data.get('Date Covered', '')}**")

                            numeric_cols = [
                                "Daily Rate", "Basic Salary", "Holiday", "Overtime pay",
                                "Night Differential", "5 days Incentives", "Uniform Allowance",
                                "Gross Pay", "SSS", "Pag-Ibig", "PhilHealth", "Loans",
                                "FA Bonds", "Cash Advance", "Total Deduction", "NET PAY"
                            ]
                            for col in numeric_cols:
                                try:    row_data[col] = float(str(row_data.get(col, 0) or 0).replace(",", ""))
                                except: row_data[col] = 0.0

                            net = row_data["NET PAY"]
                            period = row_data.get("Date Covered", "")
                            st.markdown(
                                f"""<div style="background:#001f3f;color:white;padding:16px;"""
                                f"""border-radius:12px;text-align:center;margin-bottom:12px;">"""
                                f"""<div style="font-size:12px;opacity:0.7;">NET PAY</div>"""
                                f"""<div style="font-size:28px;font-weight:bold;">&#8369; {net:,.2f}</div>"""
                                f"""<div style="font-size:11px;opacity:0.6;">{period}</div></div>""",
                                unsafe_allow_html=True
                            )

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

                            pdf_bytes = generate_payslip_pdf(row_data)
                            filename  = (
                                f"Payslip_{str(user['Name']).replace(' ', '_')}_"
                                f"{str(row_data.get('Date Covered', '')).replace('/', '_')}.pdf"
                            )
                            st.download_button(
                                label="Download My Payslip PDF",
                                data=pdf_bytes,
                                file_name=filename,
                                mime="application/pdf",
                                use_container_width=True,
                                type="primary"
                            )

            except Exception as e:
                st.error(f"Could not load payslip: {e}")

st.caption("JA.PREMIER SECURITY AGENCY | 2026")
