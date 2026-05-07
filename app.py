import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob
import io

# 1. Webpage Configuration
st.set_page_config(layout="wide", page_title="Tejas Smart RAN Dashboard")

# Custom Styling (Nuvvu pampina style + Big Font tweak)
st.markdown("""
    <style>
    .report-title { font-size:32px !important; font-weight: bold; color: #1E3A8A; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #1E3A8A; color: white; }
    .stDataFrame { border: 1px solid #1E3A8A; border-radius: 5px; font-size: 18px !important; }
    /* Metric Card Look */
    [data-testid="stMetricValue"] { font-size: 24px !important; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="report-title">📡 Tejas RAN Smart Performance & Historical Dashboard</p>', unsafe_allow_html=True)

# 2. Session State Storage
if 'master_kpi' not in st.session_state:
    st.session_state['master_kpi'] = pd.DataFrame()
if 'alarm_data' not in st.session_state:
    st.session_state['alarm_data'] = pd.DataFrame()

# 3. Targeted Columns for RF KPI Analysis
TARGET_RF_COLS = [
    'Date', 'Site Id', '4G Cell Name', 'Data Volume - Total (GB)',
    'RRC Connection Success Rate(%)', 'Cell Availability(%)', 'RRC Connection Max Users'
]

# 4. Optimized Data Loading (CSV + Parquet Support)
def load_kpi_data():
    # Parquet and CSV files renditini ethukuthundi
    files = glob.glob("data/*.parquet") + glob.glob("data/*.csv")
    if not files: return pd.DataFrame()
    df_list = []
    for f in files:
        try:
            if f.endswith('.parquet'):
                temp_df = pd.read_parquet(f, engine='pyarrow')
            else:
                temp_df = pd.read_csv(f)
            
            if '4G Cell Name' in temp_df.columns:
                temp_df['Cell ID'] = "Cell " + temp_df['4G Cell Name'].astype(str).str[-1]
                temp_df['Band'] = temp_df['4G Cell Name'].astype(str).str[:6]
            df_list.append(temp_df)
        except Exception as e:
            st.warning(f"Error reading file {f}")
    
    if not df_list: return pd.DataFrame()
    combined = pd.concat(df_list, ignore_index=True)
    
    vol_col = 'Data Volume - Total (GB)'
    if vol_col in combined.columns:
        combined[vol_col] = pd.to_numeric(combined[vol_col], errors='coerce').fillna(0)
    return combined

def load_alarm_data():
    files = glob.glob("alarms/*.xlsx") + glob.glob("alarms/*.csv") + glob.glob("alarms/*.parquet")
    if not files: return pd.DataFrame()
    df_list = []
    keywords = ['Critical', 'Major', 'Service Affecting', 'Outage', 'Down', 'VSWR', 'Link Down']
    pattern = '|'.join(keywords)
    
    for f in files:
        try:
            if f.endswith('.parquet'): temp_df = pd.read_parquet(f)
            elif f.endswith('.xlsx'): temp_df = pd.read_excel(f, engine='openpyxl')
            else: temp_df = pd.read_csv(f)
            
            mask = temp_df.astype(str).apply(lambda x: x.str.contains(pattern, case=False)).any(axis=1)
            df_list.append(temp_df[mask])
        except: continue
    return pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()

# --- SIDEBAR: DATA SYNC MANAGEMENT ---
with st.sidebar:
    st.header("📂 Data Sync Center")
    st.info("Files should be in 'data/' and 'alarms/' folders.")
    
    if st.button("🔄 Sync All Smart Data"):
        with st.spinner("Fetching and Filtering Cloud Data..."):
            kpi_df = load_kpi_data()
            if not kpi_df.empty:
                if 'Date' in kpi_df.columns:
                    kpi_df['Date'] = pd.to_datetime(kpi_df['Date']).dt.date
                st.session_state['master_kpi'] = kpi_df.drop_duplicates()
            st.session_state['alarm_data'] = load_alarm_data()
            st.success("Sync Complete! 🚀")

    st.divider()
    if st.button("🗑️ Clear Cache"):
        st.session_state['master_kpi'] = pd.DataFrame()
        st.session_state['alarm_data'] = pd.DataFrame()
        st.rerun()

# --- MAIN PAGE: SEARCH & ANALYSIS ---
df_main = st.session_state['master_kpi']
df_alarm = st.session_state['alarm_data']

if not df_main.empty:
    col_s, col_d = st.columns(2)
    with col_s:
        search_site = st.text_input("🔍 Search Site ID (e.g., AT2001):", "").strip().upper()
    with col_d:
        min_d = df_main['Date'].min()
        max_d = df_main['Date'].max()
        date_range = st.date_input("📅 Date Range Filter", [min_d, max_d])

    if search_site:
        mask = (df_main['Site Id'].str.contains(search_site, case=False, na=False))
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            mask &= (df_main['Date'] >= date_range[0]) & (df_main['Date'] <= date_range[1])
        
        site_data = df_main[mask].sort_values(by=['Date', 'Band', 'Cell ID'])

        if not site_data.empty:
            # --- 📊 TRAFFIC GRAPH (AS PER YOUR UI) ---
            st.subheader(f"📊 Traffic Analysis for {search_site}")
            fig = px.bar(site_data, x='Date', y='Data Volume - Total (GB)', color='Cell ID', 
                         facet_col='Band', barmode='group', height=500, text_auto='.1f',
                         color_discrete_map={"Cell 0": "#1E3A8A", "Cell 1": "#3B82F6", "Cell 2": "#EF4444"})
            fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
            st.plotly_chart(fig, use_container_width=True)

            st.divider()
            col_l, col_r = st.columns(2)
            
            # --- 🚨 RCA & ALARM SECTION (IMPROVED) ---
            with col_l:
                st.subheader("🚨 Site Status & Alarms")
                if not df_alarm.empty:
                    site_alarms = df_alarm[df_alarm.astype(str).apply(lambda x: x.str.contains(search_site, case=False)).any(axis=1)]
                    if not site_alarms.empty:
                        st.error(f"Critical Issues Found!")
                        st.dataframe(site_alarms, use_container_width=True)
                    else:
                        st.success("No active critical alarms! ✅")
                else:
                    st.info("No alarm data found.")

            with col_r:
                st.subheader("📉 RCA: Low Traffic Analysis (< 2GB)")
                low_traf = site_data[site_data['Data Volume - Total (GB)'] < 2.0]
                if not low_traf.empty:
                    sel_low_cell = st.selectbox("Analyze Cell Why Traffic is < 2GB:", low_traf['4G Cell Name'].unique())
                    c_info = site_data[site_data['4G Cell Name'] == sel_low_cell].iloc[-1]
                    
                    # Logic-based Final Output
                    if c_info.get('Cell Availability(%)', 100) < 90:
                        st.error("RCA: Cell Down Time (Availability Issue)")
                    elif c_info.get('RRC Connection Success Rate(%)', 100) < 85:
                        st.warning("RCA: Signaling Failure (RRC Issue)")
                    else:
                        st.info("RCA: Healthy Cell - Low User Footfall")
                    
                    st.dataframe(low_traf[['Date', '4G Cell Name', 'Data Volume - Total (GB)']], use_container_width=True)
                else:
                    st.success("All cells performing healthy! ✅")
            
            st.divider()
            st.subheader("📋 Key RF KPI Records")
            # Showing only targeted columns as requested
            show_cols = [c for c in TARGET_RF_COLS if c in site_data.columns]
            st.dataframe(site_data[show_cols], use_container_width=True)
        else:
            st.warning(f"No data found for Site: {search_site}")

    # --- OA Wise Tracker ---
    st.divider()
    st.markdown("### 🔍 OA Wise Tracker (Latest Status)")
    if 'OA' in df_main.columns:
        oa_list = sorted(df_main['OA'].dropna().unique())
        sel_oa = st.selectbox("🎯 Filter by OA:", ["Select Area"] + oa_list)
        if sel_oa != "Select Area":
            df_oa = df_main[df_main['OA'] == sel_oa]
            latest_d = df_oa['Date'].max()
            low_cells = df_oa[(df_oa['Date'] == latest_d) & (df_oa['Data Volume - Total (GB)'] < 2.0)]
            st.dataframe(low_cells[['Site Id', '4G Cell Name', 'Data Volume - Total (GB)']], use_container_width=True)

else:
    st.info("👈 Please click 'Sync All Smart Data' in the sidebar to load files.")
