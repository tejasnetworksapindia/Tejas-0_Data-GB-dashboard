import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io

# 1. Webpage Configuration
st.set_page_config(layout="wide", page_title="Tejas Smart RAN Dashboard")

# Custom Styling
st.markdown("""
    <style>
    .report-title { font-size:28px !important; font-weight: bold; color: #1E3A8A; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="report-title">📡 Tejas RAN Performance & Historical Master Dashboard</p>', unsafe_allow_html=True)

# 2. Session State Storage
if 'master_kpi' not in st.session_state:
    st.session_state['master_kpi'] = pd.DataFrame()

# 3. Helper Function - 🟢 URL SLASH ERROR FIXED
def fetch_from_drive(file_id):
    if not file_id: return None
    
    # Correct format for Google Drive Direct Downloads - MAAMA EKKADA FIX CHESA
    url = f"https://google.com{file_id.strip()}"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return pd.read_excel(io.BytesIO(response.content))
        else:
            st.error(f"Download Error (ID: {file_id}): Drive file access 'Anyone with the link' lo undha check chey maama!")
    except Exception as e:
        st.error(f"Fetch Error: {e}")
    return None

# --- SIDEBAR: DATA MANAGEMENT ---
with st.sidebar:
    st.header("📂 Data Management")
    
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
                combined['Date'] = pd.to_datetime(combined['Date']).dt.date
                st.session_state['master_kpi'] = combined.drop_duplicates()
                st.success("4-Day Data Loaded! 🚀")

    st.divider()
    st.subheader("🚨 Recent Folder Alarms")
    active_id = st.text_input("Active Alarm ID:")
    fm_id = st.text_input("FM Report ID:")
    vswr_id = st.text_input("VSWR Report ID:")

    if st.button("🗑️ Clear Dashboard"):
        st.session_state['master_kpi'] = pd.DataFrame()
        st.rerun()

# --- MAIN PAGE: SEARCH & FILTERS ---
df_main = st.session_state['master_kpi']

col_search, col_date = st.columns(2)

with col_search:
    search_site = st.text_input("🔍 Search Site ID (e.g., AT2001)", "").strip().upper()

with col_date:
    if not df_main.empty:
        min_d = df_main['Date'].min()
        max_d = df_main['Date'].max()
        date_range = st.date_input("📅 Date Range Filter", [min_d, max_d])
    else:
        st.info("Sync data to enable Date Filter")
        date_range = []

# --- ANALYSIS SECTION ---
if search_site and not df_main.empty:
    mask = (df_main['Site Id'].str.contains(search_site, case=False, na=False))
    
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        mask &= (df_main['Date'] >= date_range[0]) & (df_main['Date'] <= date_range[1])
    
    site_data = df_main[mask].sort_values(by='Date')

    if not site_data.empty:
        st.subheader(f"📊 Traffic Analysis for {search_site}")
        fig = px.bar(site_data, x='Date', y='Data Volume - Total (GB)', 
                     color='4G Cell Name', barmode='group', height=450, text_auto='.2f')
        st.plotly_chart(fig, use_container_width=True)

        st.divider()
        col_kpi, col_alarm = st.columns(2)
        with col_kpi:
            st.subheader("📉 RF KPI Parameters")
            kpi_cols = ['Date', '4G Cell Name', 'CSSR', 'RRC Connection Success Rate(All) (%)', 'ERAB Drop Rate - PS (%)']
            available_cols = [c for c in kpi_cols if c in site_data.columns]
            st.dataframe(site_data[available_cols].sort_values(by='Date', ascending=False), use_container_width=True)
            
        with col_alarm:
            st.subheader(f"⚠️ Recent Alarms")
            alarm_results = []
            for lbl, f_id in [("Active", active_id), ("FM", fm_id), ("VSWR", vswr_id)]:
                if f_id:
                    df_al = fetch_from_drive(f_id)
                    if df_al is not None:
                        res = df_al[df_al.astype(str).apply(lambda x: x.str.contains(search_site, case=False, na=False)).any(axis=1)].copy()
                        if not res.empty:
                            res['Source'] = lbl
                            alarm_results.append(res)
            if alarm_results:
                st.dataframe(pd.concat(alarm_results, ignore_index=True), use_container_width=True)
            else:
                st.success("No active alarms found! ✅")

# --- BOTTOM SECTION: OA TRACKER ---
st.divider()
st.markdown("### 🔍 Low Traffic Cell Tracker (OA Wise)")
if not df_main.empty:
    if 'OA' in df_main.columns:
        oa_list = sorted(df_main['OA'].dropna().unique())
        selected_oa = st.selectbox("🎯 Filter by Operational Area (OA):", ["Select Area"] + oa_list)
        latest_date = df_main['Date'].max()
        df_latest = df_main[df_main['Date'] == latest_date]
        if selected_oa != "Select Area":
            df_filtered_oa = df_latest[df_latest['OA'] == selected_oa]
            low_cells = df_filtered_oa[df_filtered_oa['Data Volume - Total (GB)'] < 2.0]
            if not low_cells.empty:
                st.warning(f"⚠️ {len(low_cells)} cells below 2GB on {latest_date}")
                st.dataframe(low_cells[['Site Id', 'LOCATION', '4G Cell Name', 'Data Volume - Total (GB)']], use_container_width=True)
            else:
                st.success(f"✅ All cells in {selected_oa} are above 2GB.")
else:
    st.info("👈 Please click 'Sync Fixed 4-Day KPI' to enable Tracker.")
