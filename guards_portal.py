import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import os

# --- 1. INITIAL CONFIGURATION ---
st.set_page_config(page_title="JA.PREMIER Guard Portal", layout="centered", page_icon="🛡️")

ATTENDANCE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbx5lpKgFFZe_f5D1_hQFeLrfwnQaMLmfJFqYt3s6PAhkyOTnFdT-sHYH-VoEXE6Bk5D/exec"

base_path = os.path.dirname(os.path.abspath(__file__))
logo_path = os.path.join(base_path, "agency_logo.png")

# --- 2. CONNECT TO GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. UTILITY FUNCTIONS ---
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
    if os.path.exists(logo_path):
        col1, col2, col3 = st.columns([3, 2, 3])
        with col2: st.image(logo_path, use_container_width=True)
    
    st.markdown("<h1 style='text-align: center;'>JA.PREMIER Login</h1>", unsafe_allow_html=True)
    mobile_input = st.text_input("Mobile Number", placeholder="09xxxxxxxxx")
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
    
    # Clean Security ID
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
                # Ensure Effective Date is handled for latest assignment
                guard_assignments['Effective Date'] = pd.to_datetime(guard_assignments['Effective Date'], dayfirst=True, errors='coerce')
                latest_assignment = guard_assignments.sort_values('Effective Date', ascending=False).iloc[0]
                assigned_site = str(latest_assignment['Site']).strip()
            else:
                assigned_site = "Floating / Unassigned"

        st.title(f"Welcome, {user['Name']}")
        tab1, tab2, tab3 = st.tabs(["🕒 Attendance", "📩 Requests", "👤 My Profile"])
        
        with tab1:
            st.subheader("Daily Time Record")
            st.info(f"📍 Currently Assigned to: **{assigned_site}**")
            
            # --- DIGITAL POST ORDERS SECTION (FIXED) ---
            st.markdown("### 📋 Digital Post Orders")
            try:
                orders_df = get_data("PostOrders")
                # Normalize Site column for matching
                orders_df['Site_Clean'] = orders_df['Site'].astype(str).str.strip().str.upper()
                site_orders = orders_df[orders_df['Site_Clean'] == assigned_site.upper()]
                
                if not site_orders.empty:
                    # Look for 'Orders' or 'Order_Content' column
                    possible_cols = ['Orders', 'Order_Content', 'Instructions']
                    found_col = next((c for c in possible_cols if c in site_orders.columns), None)
                    
                    if found_col:
                        specific_order = site_orders.iloc[0][found_col]
                        st.warning(f"**Instructions for {assigned_site}:**\n\n{specific_order}")
                        
                        # --- ACKNOWLEDGEMENT LOGIC ---
                        if st.button("✔️ I HAVE READ & UNDERSTOOD", use_container_width=True):
                            new_log = pd.DataFrame([{
                                "Timestamp": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
                                "Guard_Name": user['Name'],
                                "Site": assigned_site,
                                "Order_Content": specific_order, # Sent back to Command Center
                                "Status": "CONFIRMED READ"
                            }])
                            try:
                                existing_logs = get_data("PostOrderLogs")
                                updated_logs = pd.concat([existing_logs, new_log], ignore_index=True)
                                conn.update(worksheet="PostOrderLogs", data=updated_logs)
                                st.success("Acknowledgement sent to JA.PREMIER Command Center!")
                            except Exception as log_err:
                                st.error("Could not save log. Ensure 'PostOrderLogs' tab exists.")
                    else:
                        st.error("Sheet Error: Column 'Orders' not found in PostOrders tab.")
                else:
                    st.success("✅ No special instructions for this site today.")
            except Exception as e:
                st.caption("Standard Post Orders apply.")
            
            st.divider()
            # Generate Clock URL
            unified_url = f"{ATTENDANCE_SCRIPT_URL}?name={user['Name']}&site={assigned_site}"
            st.link_button("🚀 CLOCK IN / OUT", unified_url, use_container_width=True, type="primary")
            
        with tab2:
            st.subheader("New Request")
            with st.form("request_form", clear_on_submit=True):
                req_type = st.selectbox("Category", ["Leave of Absence", "Cash Advance", "Uniform/Equipment", "Schedule Change", "Medical", "Other"])
                details = st.text_area("Details")
                if st.form_submit_button("Submit"):
                    if details: submit_request(req_type, details)
            
            st.divider()
            st.subheader("My Request History")
            try:
                all_reqs = get_data("Request")
                user_mob = clean_to_digits(user['Mobile_Number'])
                all_reqs['Mobile_Number_Clean'] = all_reqs['Mobile_Number'].apply(clean_to_digits)
                my_reqs = all_reqs[all_reqs['Mobile_Number_Clean'] == user_mob].copy()
                
                if not my_reqs.empty:
                    display_reqs = my_reqs[['Date', 'Type', 'Details', 'Status']].sort_values('Date', ascending=False)
                    # Use style.map for modern Pandas
                    styled_display = display_reqs.style.map(style_status, subset=['Status'])

                    st.dataframe(styled_display, hide_index=True, use_container_width=True)
                    st.caption("🟡 PENDING | 🟢 APPROVED | 🔴 DENIED")
                else:
                    st.info("No previous requests found.")
            except Exception as e:
                st.error(f"History Error: {e}")

        with tab3:
            st.subheader("Employment Details")
            st.write(f"**Full Name:** {user['Name']}")
            st.write(f"**Current Site:** {assigned_site}")
            st.write(f"**Mobile:** {clean_to_digits(user['Mobile_Number'])}")
            st.write(f"**Security ID:** {clean_id}")

st.caption("JA.PREMIER SECURITY AGENCY | 2026")