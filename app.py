import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io

# 1. Webpage Configuration
st.set_page_config(layout="wide", page_title="Tejas Smart RAN Master Dashboard")

# Custom Styling
st.markdown("""
    <style>
    .report-title { font-size:28px !important; font-weight: bold; color: #1E3A8A; }
    .stDataFrame { border: 1px solid #e6e9ef; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="report-title">📡 Tejas RAN Performance & Historical Master Dashboard</p>', unsafe_allow_html=True)

# 2. Session State Storage (Memory Storage)
if 'master_kpi' not in st.session_state:
    st.session_state['master_kpi'] = pd.DataFrame()

# 3. Helper Functions
def fetch_from_drive(file_id):
    if not file_id: return None
    # Correct direct download URL
    url = f'https://google.com{file_id.strip()}'
    try:
        response = requests.get(url)
        if response.status_code == 200:
            content = io.BytesIO(response.content)
            try:
                # First try Excel, then CSV
                return pd.read_excel(content)
            except:
                return pd.read_csv(content)
    except Exception as e:
        st.error(f"Drive Fetch Error ({file_id}): {e}")
    return None

# --- SIDEBAR: DATA MANAGEMENT ---
with st.sidebar:
    st.header("📂 Data Management")
    
    # 🟢 FIXED GOOGLE DRIVE IDs (Nuvvu pampinavi ikkada fix chesa maama)
    FIXED_KPI_IDS = [
        "1o1a7QX47BGUlwZ1Vm6DrDhM1Uh62wVPB",
        "1wvh8AAWhuj_ZDkiHKhIKU0YiFtf8CoJS",
        "10KzzznYIUHitWMSEnKG2KoQnySkoPnQG",
        "136xNGW0_EghLz8sGw8AGJPVnp5y9rR0L"
    ]

    st.subheader("📅 KPI Auto-Sync")
    if st.button("🔄 Sync Fixed 4-Day KPI"):
        all_dfs = []
        with st.spinner("Fetching KPI Records from Drive..."):
            for f_id in FIXED_KPI_IDS:
                df = fetch_from_drive(f_id)
                if df is not None:
                    all_dfs.append(df)
            if all_dfs:
                combined = pd.concat(all_dfs, ignore_index=True)
                # Date format handling
                combined['Date'] = pd.to_datetime(combined['Date']).dt.date
                st.session_state['master_kpi'] = combined.drop_duplicates()
                st.success("4-Day Data Loaded! 🚀")

    st.divider()
    
    # Historical KPI ID (Optional for additional files)
    st.subheader("➕ Add More KPI History")
    extra_kpi_id = st.text_input("Paste Extra KPI File ID:")
    if st.button("➕ Append to Dashboard"):
        if extra_kpi_id:
            extra_df = fetch_from_drive(extra_kpi_id)
            if extra_df is not None:
                extra_df['Date'] = pd.to_datetime(extra_df['Date']).dt.date
                combined = pd.concat([st.session_state['master_kpi'], extra_df], ignore_index=True)
                st.session_state['master_kpi'] = combined.drop_duplicates()
                st.success("Extra data added!")

    st.divider()
    
    # Recent Folder Alarms Section
    st.subheader("🚨 Recent Folder Alarms")
    st.info("Paste IDs from Latest Folder (e.g., AP-05 MAY)")
    active_id = st.text_input("Active Alarm ID:")
    fm_id = st.text_input("FM Report ID:")
    vswr_id = st.text_input("VSWR Report ID:")

    if st.button("🗑️ Clear All Data"):
        st.session_state['master_kpi'] = pd.DataFrame()
        st.rerun()

# --- MAIN PAGE: SEARCH & FILTERS ---
df_main = st.session_state['master_kpi']

col_search, col_date = st.columns([2, 1])

with col_search:
    search_site = st.text_input("🔍 Search Site ID (e.g., AT2001)", "").strip().upper()

with col_date:
    if not df_main.empty:
        min_d = min(df_main['Date'])
        max_d = max(df_main['Date'])
        # Date Range Filter
        date_range = st.date_input("📅 Date Range Filter", [min_d, max_d])
    else:
        st.info("Sync data to enable Date Filter")

# --- ANALYSIS SECTION ---
if search_site and not df_main.empty:
    # Smart Site Filter
    mask = (df_main['Site Id'].str.contains(search_site, case=False, na=False))
    
    # Apply Date Range Filter if selected correctly
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        mask &= (df_main['Date'] >= date_range[0]) & (df_main['Date'] <= date_range[1])
    
    site_data = df_main[mask].sort_values(by='Date')

    if not site_data.empty:
        # --- 1. TRAFFIC GRAPH (50% Area) ---
        st.subheader(f"📊 Traffic Analysis for {search_site}")
        fig = px.bar(site_data, x='Date', y='Data Volume - Total (GB)', 
                     color='4G Cell Name', barmode='group', height=500, text_auto='.2f')
        st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # --- 2. BOTTOM SECTION: KPI (25%) & ALARMS (25%) ---
        col_kpi, col_alarm = st.columns(2)
        
        with col_kpi:
            st.subheader("📉 RF KPI Parameters")
            kpi_cols = ['Date', '4G Cell Name', 'CSSR', 'RRC Connection Success Rate(All) (%)', 'ERAB Drop Rate - PS (%)']
            available_cols = [c for c in kpi_cols if c in site_data.columns]
            st.dataframe(site_data[available_cols].sort_values(by='Date', ascending=False), use_container_width=True)
            
        with col_alarm:
            st.subheader(f"⚠️ Recent Alarms (Today's Folder)")
            alarm_results = []
            for lbl, f_id in [("Active", active_id), ("FM", fm_id), ("VSWR", vswr_id)]:
                if f_id:
                    df_al = fetch_from_drive(f_id)
                    if df_al is not None:
                        # Smart search within alarm report
                        res = df_al[df_al.astype(str).apply(lambda x: x.str.contains(search_site, case=False, na=False)).any(axis=1)].copy()
                        if not res.empty:
                            res['Source'] = lbl
                            alarm_results.append(res)
            
            if alarm_results:
                st.dataframe(pd.concat(alarm_results, ignore_index=True), use_container_width=True)
            else:
                st.success("No active alarms found for this site in the latest folder! ✅")
    else:
        st.error(f"No records found for '{search_site}' in the selected date range.")

# --- 3. BOTTOM SECTION: LOW TRAFFIC TRACKER (<2GB) ---
st.divider()
st.markdown("### 🔍 Low Traffic Cell Tracker (OA Wise Analysis)")

if not df_main.empty:
    if 'OA' in df_main.columns:
        # Extract unique OAs for the dropdown
        oa_list = sorted(df_main['OA'].dropna().unique())
        selected_oa = st.selectbox("🎯 Filter by Operational Area (OA):", ["Select Area"] + oa_list)
        
        # Latest data check
        latest_date = df_main['Date'].max()
        df_latest = df_main[df_main['Date'] == latest_date]
        
        if selected_oa != "Select Area":
            df_filtered_oa = df_latest[df_latest['OA'] == selected_oa]
            low_traffic_cells = df_filtered_oa[df_filtered_oa['Data Volume - Total (GB)'] < 2.0]
            
            if not low_traffic_cells.empty:
                st.warning(f"⚠️ Warning: {len(low_traffic_cells)} cells below 2GB on {latest_date} in {selected_oa}")
                # Important columns only
                tracker_cols = ['Site Id', 'LOCATION', 'Cell Id', '4G Cell Name', 'Data Volume - Total (GB)']
                valid_tracker_cols = [c for c in tracker_cols if c in low_traffic_cells.columns]
                st.dataframe(low_traffic_cells[valid_tracker_cols].sort_values(by='Data Volume - Total (GB)'), use_container_width=True)
            else:
                st.success(f"✅ Performance Check: All cells in {selected_oa} are above 2GB.")
    else:
        st.error("Header 'OA' not found in KPI data. Tracker disabled.")
else:
    st.info("👈 Please click 'Sync Fixed 4-Day KPI' in the sidebar to enable the OA Tracker.")
