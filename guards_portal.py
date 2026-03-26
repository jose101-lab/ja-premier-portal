from payslip_generator import generate_payslip_pdf
from incident_pdf import generate_incident_pdf
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import base64
import json
import re

# Philippine Standard Time
PST = ZoneInfo("Asia/Manila")
def now_pst():
    return datetime.now(PST)

# --- 1. PAGE CONFIG ---
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
GS_FILENAME   = "JA.PREMIER ATTENDANCE"
SYSTEM_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

base_path = os.path.dirname(os.path.abspath(__file__))
logo_path = os.path.join(base_path, "agency_logo.png")

# --- 4. LOAD CREDENTIALS ---
try:
    svc_info = dict(st.secrets["gcp_service_account"])
except Exception:
    try:
        creds_path = os.path.join(base_path, "credentials.json")
        with open(creds_path) as f:
            svc_info = json.load(f)
    except Exception as e:
        st.error(f"Could not load credentials: {e}")
        st.stop()

# ============================================================
# --- CACHING LAYER ---
# ============================================================

def _freeze_svc(svc_info: dict) -> frozenset:
    """Convert svc_info dict → frozenset so it works as a cache key."""
    return frozenset(svc_info.items())

_svc_frozen = _freeze_svc(svc_info)


@st.cache_resource
def build_gspread_client(svc_info_frozen: frozenset):
    """
    Cache the authenticated gspread client as a RESOURCE.
    OAuth handshake happens once per server process — never repeated
    across rerenders or tab switches.
    """
    creds = Credentials.from_service_account_info(
        dict(svc_info_frozen), scopes=SYSTEM_SCOPES
    )
    return gspread.authorize(creds)


@st.cache_data(ttl=60, show_spinner=False)
def get_data(sheet_name: str, svc_info_frozen: frozenset) -> pd.DataFrame:
    """
    Fetch a single sheet and cache it for 60 seconds.
    Reuses the cached gspread client — no redundant OAuth calls.
    All callers share the same cache entry for the same sheet_name.
    """
    try:
        client = build_gspread_client(svc_info_frozen)
        ws     = client.open(GS_FILENAME).worksheet(sheet_name)
        return pd.DataFrame(ws.get_all_records())
    except Exception as e:
        st.error(f"Error reading {sheet_name}: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def get_guard_balance(guard_name: str, svc_info_frozen: frozenset):
    """
    Fetch Cash Advance + Guards Payable for ONE guard, cached 5 min.
    Isolated so it can be invalidated independently from other sheets.
    Returns (unpaid_ca_df, unpaid_gp_df, total_ca, total_gp, grand_total).
    """
    try:
        ca_df     = get_data("Cash_Advance",   svc_info_frozen)
        gp_df     = get_data("Guards_Payable", svc_info_frozen)
        guard_upper = guard_name.strip().upper()

        unpaid_ca = pd.DataFrame()
        if not ca_df.empty:
            ca_df["_n"]    = ca_df["Security Guard"].astype(str).str.strip().str.upper()
            my_ca          = ca_df[ca_df["_n"] == guard_upper].copy()
            my_ca["_paid"] = my_ca["Remarks"].astype(str).str.strip().str.upper()
            unpaid_ca      = my_ca[my_ca["_paid"] != "PAID"].copy()
            unpaid_ca["_amount"] = pd.to_numeric(
                unpaid_ca["Amount"].astype(str).str.replace(",", "").str.strip(),
                errors="coerce"
            ).fillna(0)
            unpaid_ca["_date"] = pd.to_datetime(
                unpaid_ca["Date of CA"], errors="coerce"
            ).dt.strftime("%m/%d/%Y").fillna("")
            unpaid_ca["_remarks"] = unpaid_ca["Remarks"].astype(str).str.strip()
            unpaid_ca.loc[
                unpaid_ca["_remarks"].str.upper().isin(["NAN", "PAID", ""]), "_remarks"
            ] = "Cash Advance"

        unpaid_gp = pd.DataFrame()
        if not gp_df.empty:
            gp_df["_n"]    = gp_df["Security Guard"].apply(normalize_name)
            my_gp          = gp_df[gp_df["_n"] == normalize_name(guard_name)].copy()
            my_gp["_paid"] = my_gp["Status"].astype(str).str.strip().str.upper()
            unpaid_gp      = my_gp[my_gp["_paid"] != "PAID"].copy()
            unpaid_gp["_amount"] = pd.to_numeric(
                unpaid_gp["Amount"].astype(str).str.replace(",", "").str.strip(),
                errors="coerce"
            ).fillna(0)
            unpaid_gp["_date"] = pd.to_datetime(
                unpaid_gp["Date"], errors="coerce"
            ).dt.strftime("%m/%d/%Y").fillna("")
            unpaid_gp["_remarks"] = unpaid_gp["Remarks"].astype(str).str.strip()

        total_ca    = float(unpaid_ca["_amount"].sum()) if not unpaid_ca.empty else 0.0
        total_gp    = float(unpaid_gp["_amount"].sum()) if not unpaid_gp.empty else 0.0
        grand_total = total_ca + total_gp
        return unpaid_ca, unpaid_gp, total_ca, total_gp, grand_total

    except Exception as e:
        st.error(f"Balance error: {e}")
        return pd.DataFrame(), pd.DataFrame(), 0.0, 0.0, 0.0


@st.cache_data(ttl=120, show_spinner=False)
def get_guard_assignment(guard_name: str, svc_info_frozen: frozenset) -> str:
    """
    Resolve the latest site assignment for a guard, cached 2 min.
    Avoids re-fetching GUARDS sheet on every tab switch.
    """
    try:
        guards_df = get_data("GUARDS", svc_info_frozen)
        guard_upper = guard_name.strip().upper()
        assignments = guards_df[
            guards_df["Guard Name"].astype(str).str.strip().str.upper() == guard_upper
        ].copy()
        if assignments.empty:
            return "Floating / Unassigned"
        assignments["Effective Date"] = pd.to_datetime(
            assignments["Effective Date"], dayfirst=True, errors="coerce"
        )
        return str(
            assignments.sort_values("Effective Date", ascending=False).iloc[0]["Site"]
        ).strip()
    except Exception:
        return "Floating / Unassigned"


@st.cache_data(ttl=300, show_spinner=False)
def get_payroll_for_guard(guard_name: str, svc_info_frozen: frozenset):
    """
    Fetch PayrollControl + Payroll sheet, filter to one guard, cached 5 min.
    Returns (is_published, my_records_df).
    """
    try:
        ctrl_df = get_data("PayrollControl", svc_info_frozen)
        is_published = (
            not ctrl_df.empty and
            str(ctrl_df.iloc[0].get("Status", "")).upper() == "PUBLISHED"
        )
        if not is_published:
            return False, pd.DataFrame()

        payroll_df = get_data("Payroll", svc_info_frozen)
        if payroll_df.empty:
            return True, pd.DataFrame()

        payroll_df["_name_upper"] = (
            payroll_df["Employee Name"].astype(str).str.strip().str.upper()
        )
        my_records = payroll_df[
            payroll_df["_name_upper"] == guard_name.strip().upper()
        ].copy()
        return True, my_records
    except Exception:
        return False, pd.DataFrame()


# ============================================================
# --- 5. UTILITY FUNCTIONS ---
# ============================================================

def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()


def clean_to_digits(value):
    v      = str(value).replace('.0', '').strip()
    digits = "".join(filter(str.isdigit, v))
    if len(digits) == 10 and digits.startswith('9'):
        return "0" + digits
    return digits


def normalize_name(name):
    n = str(name).strip().upper()
    n = re.sub(r'^SG\s+', '', n)
    if ',' in n:
        parts = n.split(',', 1)
        n = f"{parts[1].strip()} {parts[0].strip()}"
    return ' '.join(n.split())


def update_sheet(sheet_name, df):
    """Full sheet overwrite. Reuses cached gspread client."""
    try:
        client = build_gspread_client(_svc_frozen)
        ws     = client.open(GS_FILENAME).worksheet(sheet_name)
        ws.clear()
        ws.update([df.columns.tolist()] + df.fillna("").values.tolist())
        return True
    except Exception as e:
        st.error(f"Update error: {e}")
        return False


def append_to_sheet(sheet_name, row_dict):
    """Append a single row; auto-creates sheet with headers if missing."""
    try:
        client = build_gspread_client(_svc_frozen)
        wb     = client.open(GS_FILENAME)
        try:
            ws = wb.worksheet(sheet_name)
        except Exception:
            ws = wb.add_worksheet(title=sheet_name, rows="1000", cols="20")
            ws.append_row(list(row_dict.keys()))
        ws.append_row(list(row_dict.values()))
        return True
    except Exception as e:
        st.error(f"Append error: {e}")
        return False


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
        mobile    = st.session_state.user_data.get('Mobile_Number', '')
        clean_mob = (
            clean_to_digits(mobile)
            if mobile and str(mobile) not in ['', 'nan', 'None']
            else ''
        )
        new_req = pd.DataFrame([{
            "Date":          now_pst().strftime("%Y-%m-%d %H:%M:%S"),
            "Mobile_Number": clean_mob,
            "Name":          st.session_state.user_data['Name'],
            "Type":          req_type,
            "Details":       details,
            "Status":        "PENDING"
        }])
        try:
            existing_reqs = get_data("Request", _svc_frozen)
            updated_reqs  = pd.concat([existing_reqs, new_req], ignore_index=True)
            update_sheet("Request", updated_reqs)
            st.success("Request sent!")
            st.cache_data.clear()
        except Exception as e:
            st.error(f"Error: {e}")


# --- 6. SESSION MANAGEMENT ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_data     = None

# ============================================================
# --- 7. LOGIN SCREEN ---
# ============================================================

if not st.session_state.authenticated:
    st.markdown("""
        <style>
        .force-center {
            display: flex; justify-content: center;
            align-items: center; width: 100%; margin-bottom: 10px;
        }
        .logo-img { width: 150px; height: auto; }
        .welcome-text {
            text-align: center; color: #001f3f;
            font-weight: bold; margin-bottom: 15px; font-size: 1.1rem;
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
        "<h1 style='text-align:center;color:#001f3f;margin-top:0px;'>JA.PREMIER Login</h1>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<p style='text-align:center;color:#666;font-size:13px;margin-bottom:4px;'>"
        "Use your name initials (e.g. Juan Dela Cruz = JDC)</p>",
        unsafe_allow_html=True
    )

    initials_input = st.text_input("Initials", placeholder="e.g. JDC").strip().upper()
    password_input = st.text_input("Password", type="password")

    if st.button("Login", use_container_width=True):
        if not initials_input:
            st.error("Please enter your initials.")
        else:
            with st.spinner("Verifying..."):
                try:
                    # Rosters is cached — fast on repeated logins within 60s
                    df = get_data("Rosters", _svc_frozen)
                    df.columns = [str(c).strip() for c in df.columns]
                    if 'Initials' not in df.columns:
                        st.error("Initials column not found in Rosters sheet. Please contact admin.")
                        st.stop()
                    df['Initials_Clean'] = df['Initials'].astype(str).str.strip().str.upper()
                    user_row = df[df['Initials_Clean'] == initials_input]
                    if not user_row.empty:
                        stored_password = str(user_row.iloc[0]['Password']).strip()
                        if str(password_input).strip() == stored_password:
                            st.session_state.authenticated = True
                            st.session_state.user_data     = user_row.iloc[0].to_dict()
                            st.rerun()
                        else:
                            st.error("Incorrect password.")
                    else:
                        st.error("Initials not found. Please contact admin.")
                except Exception as e:
                    st.error(f"Login System Error: {e}")

# ============================================================
# --- 8. LOGGED IN CONTENT ---
# ============================================================

else:
    user   = st.session_state.user_data
    raw_id = user.get('SECURITY_ID')

    clean_id = (
        "N/A"
        if raw_id is None or str(raw_id).strip().lower() in ['', 'nan', 'none']
        else str(raw_id).strip()
    )

    is_temp = str(user.get('Is_Temporary', 'False')).upper() == 'TRUE'

    # ── PASSWORD CHANGE SCREEN ───────────────────────────────────────────────
    if is_temp:
        st.title("Set Your Password")
        st.info("Welcome! Please set a new personal password to continue.")

        new_pass     = st.text_input("New Password",     type="password", help="Minimum 4 characters")
        confirm_pass = st.text_input("Confirm Password", type="password")

        if st.button("Save Password", use_container_width=True, type="primary"):
            if len(new_pass) < 4:
                st.error("Password must be at least 4 characters.")
            elif new_pass != confirm_pass:
                st.error("Passwords do not match.")
            else:
                with st.spinner("Saving..."):
                    try:
                        # Reuse cached client — no fresh OAuth
                        client      = build_gspread_client(_svc_frozen)
                        sheet       = client.open(GS_FILENAME).worksheet("Rosters")
                        data        = sheet.get_all_records()
                        headers     = sheet.row_values(1)
                        guard_name  = str(user.get('Name', '')).strip()

                        for i, row in enumerate(data):
                            if str(row.get('Name', '')).strip() == guard_name:
                                row_num = i + 2
                                pwd_col = headers.index('Password') + 1
                                sheet.update_cell(row_num, pwd_col, new_pass)
                                if 'Is_Temporary' in headers:
                                    tmp_col = headers.index('Is_Temporary') + 1
                                    sheet.update_cell(row_num, tmp_col, 'FALSE')
                                st.success("Password saved! Please log in again.")
                                st.cache_data.clear()
                                st.session_state.authenticated = False
                                st.session_state.user_data     = None
                                st.rerun()
                                break
                        else:
                            st.error("Could not find your record. Contact admin.")
                    except Exception as e:
                        st.error(f"Error saving password: {e}")

    # ── MAIN PORTAL ──────────────────────────────────────────────────────────
    else:
        st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())

        # Resolve site assignment from cache — no spinner blocking the UI
        assigned_site = get_guard_assignment(str(user['Name']), _svc_frozen)

        # ── GREETING HEADER ──────────────────────────────────────────────────
        col_title, col_refresh = st.columns([5, 1])
        with col_title:
            st.markdown(
                f"""
                <div style='padding-top:6px;'>
                    <div style='
                        font-size: clamp(14px, 6vw, 20px);
                        color: #7f8c8d; font-weight: 600;
                        letter-spacing: 2px; text-transform: uppercase;
                        text-align: center; margin-bottom: 2px;
                    '>Good day!</div>
                    <div style='
                        font-size: clamp(15px, 4.5vw, 24px);
                        font-weight: 900; color: #ffffff;
                        background: linear-gradient(135deg, #001f3f, #003f7f);
                        padding: 6px 14px; border-radius: 8px;
                        text-align: center; white-space: nowrap;
                        overflow: hidden; text-overflow: ellipsis;
                        letter-spacing: 0.5px;
                        box-shadow: 0 2px 8px rgba(0,31,63,0.18);
                    '>{user['Name']}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with col_refresh:
            st.markdown("<div style='padding-top:22px;'>", unsafe_allow_html=True)
            if st.button("↻", help="Refresh page"):
                st.cache_data.clear()
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        # ── TABS ─────────────────────────────────────────────────────────────
        tab1, tab_ir, tab2, tab3, tab4, tab5 = st.tabs([
            "Attendance", "🚨 Incident", "Requests", "Profile", "Payslip", "Balance"
        ])

        # ── TAB 1: ATTENDANCE ────────────────────────────────────────────────
        with tab1:
            st.subheader("Daily Time Record")
            st.info(f"Assigned to: **{assigned_site}**")

            st.markdown("### Post Orders")
            try:
                orders_df = get_data("PostOrders", _svc_frozen)
                orders_df['Site_Clean'] = orders_df['Site'].astype(str).str.strip().str.upper()
                site_orders = orders_df[orders_df['Site_Clean'] == assigned_site.upper()]
                if not site_orders.empty:
                    possible_cols = ['Orders', 'Order_Content', 'Instructions']
                    found_col     = next((c for c in possible_cols if c in site_orders.columns), None)
                    if found_col:
                        specific_order = site_orders.iloc[0][found_col]
                        st.warning(f"**Instructions:**\n\n{specific_order}")
                        if st.button("CONFIRM READ", use_container_width=True):
                            new_log = pd.DataFrame([{
                                "Timestamp":     now_pst().strftime("%Y-%m-%d %I:%M %p"),
                                "Guard_Name":    user['Name'],
                                "Site":          assigned_site,
                                "Order_Content": specific_order,
                                "Status":        "CONFIRMED READ"
                            }])
                            try:
                                existing_logs = get_data("PostOrderLogs", _svc_frozen)
                                updated_logs  = pd.concat([existing_logs, new_log], ignore_index=True)
                                update_sheet("PostOrderLogs", updated_logs)
                                st.success("Sent to Command Center!")
                                st.cache_data.clear()
                            except Exception:
                                st.error("Log error.")
                else:
                    st.success("Standard protocols apply today.")
            except Exception:
                st.caption("Post Orders ready.")

            st.divider()
            unified_url = f"{ATTENDANCE_SCRIPT_URL}?name={user['Name']}&site={assigned_site}"
            st.link_button("CLOCK IN / OUT", unified_url, use_container_width=True, type="primary")

        # ── TAB: INCIDENT REPORT ─────────────────────────────────────────────
        with tab_ir:
            st.markdown(
                """
                <div style="background:#dc3545;color:white;padding:12px 16px;
                border-radius:8px;margin-bottom:16px;text-align:center;">
                <div style="font-size:20px;font-weight:900;letter-spacing:1px;">
                🚨 INCIDENT REPORT FORM</div>
                <div style="font-size:11px;opacity:0.85;margin-top:4px;">
                Fill in all fields accurately. This will be forwarded to Command Center immediately.</div>
                </div>
                """,
                unsafe_allow_html=True
            )

            with st.form("incident_form", clear_on_submit=True):
                st.markdown(f"**Reported by:** {user['Name']}")
                st.markdown(f"**Site:** {assigned_site}")
                st.divider()

                st.markdown("#### 👤 WHO was involved?")
                who = st.text_area(
                    "who", label_visibility="collapsed",
                    placeholder="Persons involved — suspects, victims, witnesses...",
                    height=90
                )
                st.markdown("#### 📋 WHAT happened?")
                what = st.text_area(
                    "what", label_visibility="collapsed",
                    placeholder="Nature and description of the incident...",
                    height=100
                )
                st.markdown("#### 📅 WHEN did it happen?")
                col_date, col_time = st.columns(2)
                with col_date:
                    incident_date = st.date_input("Date", value=now_pst().date())
                with col_time:
                    incident_time = st.time_input("Time", value=now_pst().time())

                st.markdown("#### 📍 WHERE did it happen?")
                where = st.text_area(
                    "where", label_visibility="collapsed",
                    placeholder="Exact location within or near the site...",
                    height=80
                )
                st.markdown("#### ❓ HOW did it happen?")
                how = st.text_area(
                    "how", label_visibility="collapsed",
                    placeholder="Step-by-step sequence of events...",
                    height=100
                )
                st.markdown("#### 🔧 Action Taken")
                action_taken = st.text_area(
                    "action", label_visibility="collapsed",
                    placeholder="Immediate action taken by the guard on duty...",
                    height=80
                )

                st.divider()
                submitted = st.form_submit_button(
                    "📤 SUBMIT INCIDENT REPORT",
                    use_container_width=True, type="primary"
                )

                if submitted:
                    missing = []
                    if not who.strip():          missing.append("WHO")
                    if not what.strip():         missing.append("WHAT")
                    if not where.strip():        missing.append("WHERE")
                    if not how.strip():          missing.append("HOW")
                    if not action_taken.strip(): missing.append("Action Taken")

                    if missing:
                        st.error(f"Please fill in: {', '.join(missing)}")
                    else:
                        incident_dt = (
                            f"{incident_date.strftime('%B %d, %Y')} "
                            f"{incident_time.strftime('%I:%M %p')}"
                        )
                        report_row = {
                            "Submitted_At":      now_pst().strftime("%Y-%m-%d %H:%M:%S"),
                            "Reported_By":       user['Name'],
                            "Site":              assigned_site,
                            "Who":               who.strip(),
                            "What":              what.strip(),
                            "Incident_DateTime": incident_dt,
                            "Where":             where.strip(),
                            "How":               how.strip(),
                            "Action_Taken":      action_taken.strip(),
                            "Status":            "NEW"
                        }
                        with st.spinner("Submitting to Command Center..."):
                            success = append_to_sheet("Incident_Reports", report_row)
                        if success:
                            st.cache_data.clear()  # clears Incident_Reports cache so list refreshes instantly
                            st.success(
                                "✅ Incident Report submitted! "
                                "Command Center has been notified."
                            )
                        else:
                            st.error("⚠️ Submission failed. Try again or contact your supervisor.")

            # Guard's own previous reports
            st.divider()
            st.markdown("#### My Previous Reports")
            try:
                ir_df = get_data("Incident_Reports", _svc_frozen)
                if not ir_df.empty:
                    ir_df['_name'] = ir_df['Reported_By'].astype(str).str.strip().str.upper()
                    my_reports = ir_df[
                        ir_df['_name'] == user['Name'].strip().upper()
                    ].copy()
                    if not my_reports.empty:
                        display_cols = ['Submitted_At', 'Incident_DateTime', 'What', 'Status']
                        available    = [c for c in display_cols if c in my_reports.columns]
                        st.dataframe(
                            my_reports[available].sort_values('Submitted_At', ascending=False),
                            hide_index=True, use_container_width=True
                        )
                    else:
                        st.info("No previous incident reports filed.")
                else:
                    st.info("No incident reports on record yet.")
            except Exception:
                st.caption("Previous reports unavailable.")

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
                all_reqs       = get_data("Request", _svc_frozen)
                guard_name_req = str(user.get('Name', '')).strip()
                if 'Mobile_Number' in all_reqs.columns and user.get('Mobile_Number'):
                    user_mob = clean_to_digits(user['Mobile_Number'])
                    all_reqs['Mobile_Number_Clean'] = all_reqs['Mobile_Number'].apply(clean_to_digits)
                    my_reqs = all_reqs[all_reqs['Mobile_Number_Clean'] == user_mob].copy()
                else:
                    all_reqs['Name_Clean'] = all_reqs['Name'].astype(str).str.strip()
                    my_reqs = all_reqs[all_reqs['Name_Clean'] == guard_name_req].copy()
                if not my_reqs.empty:
                    display_reqs   = my_reqs[['Date', 'Type', 'Details', 'Status']].sort_values(
                        'Date', ascending=False
                    )
                    styled_display = display_reqs.style.map(style_status, subset=['Status'])
                    st.dataframe(styled_display, hide_index=True, use_container_width=True)
                else:
                    st.info("No requests.")
            except Exception:
                st.error("History Error.")

        # ── TAB 3: PROFILE ───────────────────────────────────────────────────
        with tab3:
            st.subheader("My Info")

            name_val        = str(user.get('Name', 'N/A'))
            initials_val    = str(user.get('Initials', '')).strip().upper() or 'N/A'
            mobile_val      = user.get('Mobile_Number', '')
            designation_val = str(user.get('Designation', '')).strip()

            def profile_card(label, value, color="#001f3f"):
                return (
                    f'<div style="background:#f8f9fa;border-radius:10px;padding:14px 18px;'
                    f'border-left:5px solid {color};margin-bottom:10px;">'
                    f'<div style="font-size:10px;color:#888;letter-spacing:1px;'
                    f'text-transform:uppercase;">{label}</div>'
                    f'<div style="font-size:16px;font-weight:700;color:#001f3f;'
                    f'margin-top:2px;">{value}</div>'
                    f'</div>'
                )

            st.markdown(profile_card("Full Name",       name_val,      "#001f3f"), unsafe_allow_html=True)
            st.markdown(profile_card("Security ID",     clean_id,      "#0074D9"), unsafe_allow_html=True)
            st.markdown(profile_card("Login Initials",  initials_val,  "#001f3f"), unsafe_allow_html=True)
            st.markdown(profile_card("Post Assignment", assigned_site, "#28a745"), unsafe_allow_html=True)

            if mobile_val and str(mobile_val) not in ['', 'nan', 'None']:
                st.markdown(
                    profile_card("Mobile Number", clean_to_digits(mobile_val), "#0074D9"),
                    unsafe_allow_html=True
                )
            if designation_val and designation_val.lower() not in ['', 'nan', 'none']:
                st.markdown(
                    profile_card("Designation", designation_val, "#6c757d"),
                    unsafe_allow_html=True
                )

        # ── TAB 4: PAYSLIP ───────────────────────────────────────────────────
        with tab4:
            st.subheader("My Payslip")
            try:
                # Single cached call — no separate PayrollControl + Payroll fetches
                is_published, my_records = get_payroll_for_guard(str(user['Name']), _svc_frozen)

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
                elif my_records.empty:
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

                    net    = row_data["NET PAY"]
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

        # ── TAB 5: BALANCE ───────────────────────────────────────────────────
        with tab5:
            st.subheader("My Balance")
            try:
                # Single cached call — no duplicate CA/GP fetches
                unpaid_ca, unpaid_gp, total_ca, total_gp, grand_total = \
                    get_guard_balance(str(user['Name']), _svc_frozen)

                if grand_total == 0:
                    st.markdown(
                        '<div style="background:#d4edda;border-left:6px solid #28a745;'
                        'padding:20px;border-radius:10px;text-align:center;margin-top:16px;">'
                        '<div style="font-size:36px;margin-bottom:8px;">&#10003;</div>'
                        '<div style="font-size:16px;font-weight:bold;color:#155724;">'
                        'No outstanding balance</div>'
                        '<div style="font-size:13px;color:#155724;margin-top:4px;">'
                        'You have no unpaid cash advance or payables on record.</div>'
                        '</div>',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f'<div style="background:#001f3f;color:white;padding:16px;'
                        f'border-radius:12px;text-align:center;margin-bottom:16px;">'
                        f'<div style="font-size:11px;opacity:0.7;letter-spacing:1px;">'
                        f'TOTAL OUTSTANDING BALANCE</div>'
                        f'<div style="font-size:32px;font-weight:800;">&#8369; {grand_total:,.2f}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

                    if not unpaid_ca.empty:
                        st.markdown(
                            f'<div style="background:#dc3545;color:white;padding:8px 16px;'
                            f'border-radius:8px 8px 0 0;font-weight:700;font-size:13px;">'
                            f'Cash Advance &nbsp;&nbsp; &#8369; {total_ca:,.2f}</div>',
                            unsafe_allow_html=True
                        )
                        for _, r in unpaid_ca.iterrows():
                            st.markdown(
                                f'<div style="background:#fff3cd;border-left:5px solid #ffc107;'
                                f'padding:10px 16px;margin-bottom:4px;">'
                                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                                f'<div><div style="font-weight:700;color:#856404;">&#8369; {r["_amount"]:,.2f}</div>'
                                f'<div style="font-size:12px;color:#856404;">{r["_remarks"]} &bull; {r["_date"]}</div>'
                                f'</div>'
                                f'<div style="background:#ffc107;color:#856404;font-size:11px;'
                                f'font-weight:700;padding:2px 10px;border-radius:20px;">Unpaid</div>'
                                f'</div></div>',
                                unsafe_allow_html=True
                            )
                        st.markdown("<div style='margin-bottom:12px;'></div>", unsafe_allow_html=True)

                    if not unpaid_gp.empty:
                        st.markdown(
                            f'<div style="background:#6c757d;color:white;padding:8px 16px;'
                            f'border-radius:8px 8px 0 0;font-weight:700;font-size:13px;">'
                            f'Others &nbsp;&nbsp; &#8369; {total_gp:,.2f}</div>',
                            unsafe_allow_html=True
                        )
                        for _, r in unpaid_gp.iterrows():
                            st.markdown(
                                f'<div style="background:#e2e3e5;border-left:5px solid #6c757d;'
                                f'padding:10px 16px;margin-bottom:4px;">'
                                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                                f'<div><div style="font-weight:700;color:#383d41;">&#8369; {r["_amount"]:,.2f}</div>'
                                f'<div style="font-size:12px;color:#383d41;">{r["_remarks"]} &bull; {r["_date"]}</div>'
                                f'</div>'
                                f'<div style="background:#6c757d;color:white;font-size:11px;'
                                f'font-weight:700;padding:2px 10px;border-radius:20px;">Unpaid</div>'
                                f'</div></div>',
                                unsafe_allow_html=True
                            )
                        st.markdown("<div style='margin-bottom:12px;'></div>", unsafe_allow_html=True)

                    st.caption("Contact admin if you have questions about your balance.")

            except Exception as e:
                st.error(f"Could not load balance: {e}")

st.caption("JA.PREMIER SECURITY AGENCY | 2026")
