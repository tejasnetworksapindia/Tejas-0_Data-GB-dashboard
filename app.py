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

# 2. Session State Storage (Monthly Data Memory)
if 'master_kpi' not in st.session_state:
    st.session_state['master_kpi'] = pd.DataFrame()

# 3. Helper Functions
def fetch_from_drive(file_id):
    if not file_id: return None
    url = f'https://google.com{file_id}'
    try:
        response = requests.get(url)
        if response.status_code == 200:
            content = io.BytesIO(response.content)
            try:
                return pd.read_csv(content)
            except:
                return pd.read_excel(content)
    except Exception as e:
        st.error(f"Drive Fetch Error ({file_id}): {e}")
    return None

# --- SIDEBAR: DATA MANAGEMENT ---
with st.sidebar:
    st.header("📂 Data Management")
    
    # KPI Monthly Sync Section
    st.subheader("📅 Monthly KPI Sync")
    kpi_history_ids = st.text_area("Paste Monthly KPI File IDs (One per line):", height=150)
    
    if st.button("🔄 Sync Historical KPI"):
        ids = kpi_history_ids.split('\n')
        all_dfs = []
        with st.spinner("Fetching Monthly Records..."):
            for f_id in ids:
                if f_id.strip():
                    df = fetch_from_drive(f_id.strip())
                    if df is not None:
                        all_dfs.append(df)
            if all_dfs:
                combined = pd.concat(all_dfs, ignore_index=True)
                # Date format handle
                combined['Date'] = pd.to_datetime(combined['Date']).dt.date
                st.session_state['master_kpi'] = combined.drop_duplicates()
                st.success("Monthly Data Loaded! 🚀")

    st.divider()
    
    # Recent Folder Alarms Section (Based on latest folder ID)
    st.subheader("🚨 Recent Folder Alarms")
    st.info("Paste IDs from Latest Folder (e.g., AP-05 MAY)")
    active_id = st.text_input("Active Alarm ID:")
    fm_id = st.text_input("FM Report ID:")
    vswr_id = st.text_input("VSWR Report ID:")

    if st.button("🗑️ Clear Dashboard"):
        st.session_state['master_kpi'] = pd.DataFrame()
        st.rerun()

# --- MAIN PAGE: SEARCH & FILTERS ---
df_main = st.session_state['master_kpi']

col_s, col_d = st.columns([2, 1])

with col_s:
    search_site = st.text_input("🔍 Search Site (e.g., AT2001)", "").strip().upper()

with col_d:
    if not df_main.empty:
        min_d = min(df_main['Date'])
        max_d = max(df_main['Date'])
        # Multi-day filter (From - To)
        date_range = st.date_input("📅 Select Date Range", [min_d, max_d])
    else:
        st.info("Sync data to enable Date Filter")

# --- ANALYSIS SECTION ---
if search_site and not df_main.empty:
    # 🟢 Smart Filtering Logic
    mask = (df_main['Site Id'].str.contains(search_site, case=False, na=False))
    if isinstance(date_range, list) or isinstance(date_range, tuple):
        if len(date_range) == 2:
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
            st.subheader(f"⚠️ Recent Alarms (Latest Folder)")
            alarm_results = []
            for lbl, f_id in [("Active", active_id), ("FM", fm_id), ("VSWR", vswr_id)]:
                if f_id:
                    df_al = fetch_from_drive(f_id)
                    if df_al is not None:
                        # Search within alarm file
                        res = df_al[df_al.astype(str).apply(lambda x: x.str.contains(search_site, case=False, na=False)).any(axis=1)].copy()
                        if not res.empty:
                            res['Source'] = lbl
                            alarm_results.append(res)
            
            if alarm_results:
                st.dataframe(pd.concat(alarm_results, ignore_index=True), use_container_width=True)
            else:
                st.success("No active alarms found in the Recent Folder! ✅")
    else:
        st.error(f"No data found for '{search_site}' in the selected date range.")

# --- 3. BOTTOM SECTION: LOW TRAFFIC TRACKER (<2GB) ---
st.divider()
st.markdown("### 🔍 Low Traffic Cell Tracker (OA Wise)")

if not df_main.empty:
    if 'OA' in df_main.columns:
        oa_list = sorted(df_main['OA'].dropna().unique())
        selected_oa = st.selectbox("🎯 Select Operational Area (OA):", ["All Areas"] + oa_list)
        
        # Current status (Latest Date) data
        latest_date = df_main['Date'].max()
        df_latest = df_main[df_main['Date'] == latest_date]
        
        # Filtering OA
        if selected_oa != "All Areas":
            df_filtered_oa = df_latest[df_latest['OA'] == selected_oa]
        else:
            df_filtered_oa = df_latest
            
        # Below 2GB Filter
        low_traffic_cells = df_filtered_oa[df_filtered_oa['Data Volume - Total (GB)'] < 2.0]
        
        if not low_traffic_cells.empty:
            st.warning(f"⚠️ Found {len(low_traffic_cells)} cells with traffic < 2GB on {latest_date}")
            cols_to_show = ['Site Id', 'LOCATION', 'Cell Id', '4G Cell Name', 'Data Volume - Total (GB)']
            valid_cols = [c for c in cols_to_show if c in low_traffic_cells.columns]
            st.dataframe(low_traffic_cells[valid_cols].sort_values(by='Data Volume - Total (GB)'), use_container_width=True)
        else:
            st.success(f"✅ Great! All cells in {selected_oa} are above 2GB.")
    else:
        st.error("Column 'OA' not found in data for Low Traffic Tracker.")
else:
    st.info("👈 Sync Historical KPI data to enable the Low Traffic Tracker section.")
