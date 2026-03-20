import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import os
import base64

# --- 1. INITIAL CONFIGURATION ---
st.set_page_config(
    page_title="JA.PREMIER Guard Portal", 
    layout="centered", 
    page_icon="🛡️"
)

# --- 1.1. APP ICON & SPLASH SCREEN METADATA ---
# These tags control the "Home Screen" icon and the loading splash screen color
LOGO_URL = "https://jose101-lab.github.io/ja-premier-portal/agency_logo.png"
AGENCY_BLUE = "#001f3f"

st.markdown(f"""
    <head>
        <link rel="apple-touch-icon" href="{LOGO_URL}">
        <link rel="icon" type="image/png" sizes="192x192" href="{LOGO_URL}">
        <link rel="icon" type="image/png" sizes="32x32" href="{LOGO_URL}">
        
        <meta name="mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
        <meta name="theme-color" content="{AGENCY_BLUE}">
        <meta name="msapplication-navbutton-color" content="{AGENCY_BLUE}">
    </head>
""", unsafe_allow_html=True)

ATTENDANCE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbx5lpKgFFZe_f5D1_hQFeLrfwnQaMLmfJFqYt3s6PAhkyOTnFdT-sHYH-VoEXE6Bk5D/exec"

base_path = os.path.dirname(os.path.abspath(__file__))
logo_path = os.path.join(base_path, "agency_logo.png")

# --- 2. CONNECT TO GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. UTILITY FUNCTIONS ---
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
            st.success("✅ Request sent!")
            st.cache_data.clear() 
        except Exception as e:
            st.error(f"Error: {e}")

# --- 4. SESSION MANAGEMENT ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_data = None

# --- 5. LOGIN SCREEN ---
if not st.session_state.authenticated:
    st.markdown(
        f"""
        <style>
        .force-center {{
            display: flex;
            justify-content: center;
            align-items: center;
            width: 100%;
            margin-bottom: 10px;
        }}
        .logo-img {{
            width: 150px;
            height: auto;
        }}
        .welcome-text {{
            text-align: center;
            color: {AGENCY_BLUE};
            font-weight: bold;
            margin-bottom: 15px;
            font-size: 1.1rem;
        }}
        </style>
        """, unsafe_allow_html=True
    )

    if os.path.exists(logo_path):
        binary_logo = get_base64_of_bin_file(logo_path)
        st.markdown(
            f'<div class="force-center"><img src="data:image/png;base64,{binary_logo}" class="logo-img"></div>',
            unsafe_allow_html=True
        )
    
    st.markdown(f"<h1 style='text-align: center; color: {AGENCY_BLUE}; margin-top: 0px;'>JA.PREMIER Login</h1>", unsafe_allow_html=True)
    
    mobile_input = st.text_input("Mobile Number", placeholder="09xxxxxxxxx")
    
    if mobile_input:
        try:
            roster_df = get_data("Rosters")
            roster_df['Mobile_Number_Clean'] = roster_df['Mobile_Number'].apply(clean_to_digits)
            search_mob = clean_to_digits(mobile_input)
            match = roster_df[roster_df['Mobile_Number_Clean'] == search_mob]
            
            if not match.empty:
                guard_name = match.iloc[0]['Name']
                st.markdown(f'<p class="welcome-text">Welcome, {guard_name}!</p>', unsafe_allow_html=True)
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

# --- 6. LOGGED IN CONTENT ---
else:
    user = st.session_state.user_data
    
    raw_id = user.get('Security_ID', 'N/A')
    try:
        clean_id = str(int(float(raw_id))) if pd.notna(raw_id) and str(raw_id).lower() != 'nan' else "N/A"
    except:
        clean_id = "N/A"

    is_temp = str(user.get('Is_Temporary', 'False')).upper() == 'TRUE'
    
    if is_temp:
        st.title("🔐 Update Password")
        new_pass = st.text_input("New Password", type="password")
        confirm_pass = st.text_input("Confirm", type="password")
        if st.button("Update"):
            if new_pass == confirm_pass and len(new_pass) > 3:
                st.success("Updated!")
                st.session_state.authenticated = False 
                st.rerun()
    else:
        st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())
        
        with st.spinner("Fetching Schedule..."):
            guards_tab_df = get_data("GUARDS")
            current_guard_name = str(user['Name']).strip().upper()
            guard_assignments = guards_tab_df[guards_tab_df['Guard Name'].astype(str).str.strip().str.upper() == current_guard_name]
            
            if not guard_assignments.empty:
                guard_assignments['Effective Date'] = pd.to_datetime(guard_assignments['Effective Date'], dayfirst=True, errors='coerce')
                latest_assignment = guard_assignments.sort_values('Effective Date', ascending=False).iloc[0]
                assigned_site = str(latest_assignment['Site']).strip()
            else:
                assigned_site = "Floating / Unassigned"

        st.title(f"Hello, {user['Name']}")
        tab1, tab2, tab3 = st.tabs(["🕒 Attendance", "📩 Requests", "👤 Profile"])
        
        with tab1:
            st.subheader("Daily Time Record")
            st.info(f"📍 Assigned to: **{assigned_site}**")
            
            st.markdown("### 📋 Post Orders")
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
                        
                        if st.button("✔️ CONFIRM READ", use_container_width=True):
                            new_log = pd.DataFrame([{
                                "Timestamp": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
                                "Guard_Name": user['Name'],
                                "Site": assigned_site,
                                "Order_Content": specific_order,
                                "Status": "CONFIRMED READ"
                            }])
                            try:
                                existing_logs = get_data("PostOrderLogs")
                                updated_logs = pd.concat([existing_logs, new_log], ignore_index=True)
                                conn.update(worksheet="PostOrderLogs", data=updated_logs)
                                st.success("Sent to Command Center!")
                            except:
                                st.error("Log error.")
                else:
                    st.success("✅ Standard protocols apply today.")
            except Exception as e:
                st.caption("Post Orders ready.")
            
            st.divider()
            unified_url = f"{ATTENDANCE_SCRIPT_URL}?name={user['Name']}&site={assigned_site}"
            st.link_button("🚀 CLOCK IN / OUT", unified_url, use_container_width=True, type="primary")
            
        with tab2:
            st.subheader("New Request")
            with st.form("request_form", clear_on_submit=True):
                req_type = st.selectbox("Type", ["Leave", "Cash Advance", "Equipment", "Schedule", "Other"])
                details = st.text_area("Details")
                if st.form_submit_button("Submit"):
                    if details: submit_request(req_type, details)
            
            st.divider()
            st.subheader("History")
            try:
                all_reqs = get_data("Request")
                user_mob = clean_to_digits(user['Mobile_Number'])
                all_reqs['Mobile_Number_Clean'] = all_reqs['Mobile_Number'].apply(clean_to_digits)
                my_reqs = all_reqs[all_reqs['Mobile_Number_Clean'] == user_mob].copy()
                
                if not my_reqs.empty:
                    display_reqs = my_reqs[['Date', 'Type', 'Details', 'Status']].sort_values('Date', ascending=False)
                    styled_display = display_reqs.style.map(style_status, subset=['Status'])
                    st.dataframe(styled_display, hide_index=True, use_container_width=True)
                else:
                    st.info("No requests.")
            except:
                st.error("History Error.")

        with tab3:
            st.subheader("My Info")
            st.write(f"**Name:** {user['Name']}")
            st.write(f"**Mobile:** {clean_to_digits(user['Mobile_Number'])}")
            st.write(f"**Security ID:** {clean_id}")

st.caption("JA.PREMIER SECURITY AGENCY | 2026")
