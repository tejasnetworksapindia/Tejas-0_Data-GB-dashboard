import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob

# 1. Webpage Configuration
st.set_page_config(layout="wide", page_title="Tejas Smart RAN Dashboard")

# Custom Styling for Professional Look
st.markdown("""
    <style>
    .report-title { font-size:28px !important; font-weight: bold; color: #1E3A8A; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #1E3A8A; color: white; }
    .stDataFrame { border: 1px solid #1E3A8A; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="report-title">📡 Tejas RAN Smart Performance & Historical Dashboard</p>', unsafe_allow_html=True)

# 2. Session State Storage to keep data after interaction
if 'master_kpi' not in st.session_state:
    st.session_state['master_kpi'] = pd.DataFrame()
if 'alarm_data' not in st.session_state:
    st.session_state['alarm_data'] = pd.DataFrame()

# 3. Helper Functions for Cloud Data Loading
def load_kpi_data():
    files = glob.glob("data/*.csv")
    if not files: return pd.DataFrame()
    df_list = []
    for f in files:
        try:
            df_temp = pd.read_csv(f)
            df_list.append(df_temp)
        except Exception as e:
            st.error(f"Error reading KPI file {f}: {e}")
    combined = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()
    if 'Data Volume - Total (GB)' in combined.columns:
        combined['Data Volume - Total (GB)'] = pd.to_numeric(combined['Data Volume - Total (GB)'], errors='coerce').fillna(0)
    return combined

def load_alarm_data():
    # Searching for both Excel and CSV files in alarms folder
    files = glob.glob("alarms/*.xlsx") + glob.glob("alarms/*.csv")
    if not files: return pd.DataFrame()
    df_list = []
    
    # Filter keywords for Service Affecting Alarms
    keywords = ['Critical', 'Major', 'Service Affecting', 'Outage', 'Down', 'VSWR', 'Link Down', 'Loss of']
    pattern = '|'.join(keywords)
    
    for f in files:
        try:
            # Using openpyxl for Excel files
            df_temp = pd.read_excel(f, engine='openpyxl') if f.endswith('.xlsx') else pd.read_csv(f)
            
            # Filtering only Critical/Major Alarms to reduce noise
            mask = df_temp.astype(str).apply(lambda x: x.str.contains(pattern, case=False)).any(axis=1)
            df_list.append(df_temp[mask])
        except Exception as e:
            st.error(f"Error reading alarm file {f}: {e}")
            
    return pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()

# --- SIDEBAR: DATA SYNC MANAGEMENT ---
with st.sidebar:
    st.header("📂 Data Sync Center")
    st.info("Syncs data from GitHub 'data/' and 'alarms/' folders.")
    
    if st.button("🔄 Sync All Smart Data"):
        with st.spinner("Fetching and Filtering Cloud Data..."):
            # KPI Loading and Processing
            kpi_df = load_kpi_data()
            if not kpi_df.empty:
                kpi_df['Date'] = pd.to_datetime(kpi_df['Date']).dt.date
                # Extracting Cell ID (Cell 0, 1, 2) from last character of Cell Name
                kpi_df['Cell ID'] = "Cell " + kpi_df['4G Cell Name'].str[-1]
                # Extracting Band (First 6 chars e.g., T4AP41)
                kpi_df['Band'] = kpi_df['4G Cell Name'].str[:6]
                st.session_state['master_kpi'] = kpi_df.drop_duplicates()
            
            # Alarm Loading
            st.session_state['alarm_data'] = load_alarm_data()
            
            total_alarms = len(st.session_state['alarm_data'])
            st.success(f"Sync Complete! Found {total_alarms} Critical Alarms. 🚀")

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
        min_d, max_d = df_main['Date'].min(), df_main['Date'].max()
        date_range = st.date_input("📅 Date Range Filter", [min_d, max_d])

    if search_site:
        mask = (df_main['Site Id'].str.contains(search_site, case=False, na=False))
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            mask &= (df_main['Date'] >= date_range[0]) & (df_main['Date'] <= date_range[1])
        
        site_data = df_main[mask].sort_values(by=['Date', 'Band', 'Cell ID'])

        if not site_data.empty:
            # --- 📊 IMPROVED BAND & CELL-WISE GRAPH ---
            st.subheader(f"📊 Traffic Analysis for {search_site} (Band & Cell-wise)")
            
            fig = px.bar(site_data, 
                         x='Date', 
                         y='Data Volume - Total (GB)', 
                         color='Cell ID', 
                         facet_col='Band', # Groups data by Band side-by-side
                         barmode='group',  # Groups Cells (0,1,2) side-by-side
                         height=500, 
                         text_auto='.1f',
                         color_discrete_map={"Cell 0": "#1E3A8A", "Cell 1": "#3B82F6", "Cell 2": "#EF4444"},
                         hover_data=['4G Cell Name'])

            # Fixing X-axis to show dates clearly and cleaning facet labels
            fig.update_xaxes(type='category', tickangle=45)
            fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
            
            st.plotly_chart(fig, use_container_width=True)

            # --- 🚨 CRITICAL ALARMS & KPI ISSUES SECTION ---
            st.divider()
            col_left, col_right = st.columns(2)
            
            with col_left:
                st.subheader("🚨 Critical/Major Alarms")
                if not df_alarm.empty:
                    # Searching for Site ID across all alarm columns
                    site_alarms = df_alarm[df_alarm.astype(str).apply(lambda x: x.str.contains(search_site, case=False)).any(axis=1)]
                    if not site_alarms.empty:
                        st.error(f"Found {len(site_alarms)} Service-Affecting issues!")
                        st.dataframe(site_alarms, use_container_width=True)
                    else:
                        st.success("No critical alarms found for this site. ✅")
                else:
                    st.info("No alarm data available. Please sync.")

            with col_right:
                st.subheader("📉 Traffic Trouble Tracker (< 2GB)")
                low_traf = site_data[site_data['Data Volume - Total (GB)'] < 2.0]
                if not low_traf.empty:
                    st.warning(f"Found {len(low_traf)} bands with low traffic!")
                    st.dataframe(low_traf[['Date', '4G Cell Name', 'Data Volume - Total (GB)']], use_container_width=True)
                else:
                    st.success("All cells performing healthy! ✅")
            
            # --- FULL DATA TABLE ---
            st.divider()
            st.subheader("📋 Detailed Performance Records")
            st.dataframe(site_data, use_container_width=True)
        else:
            st.warning(f"No records found for Site ID: {search_site}")

    # --- OA TRACKER SECTION ---
    st.divider()
    st.markdown("### 🔍 OA Wise Low Traffic Cell Tracker (Current)")
    if 'OA' in df_main.columns:
        oa_list = sorted(df_main['OA'].dropna().unique())
        sel_oa = st.selectbox("🎯 Filter by Operational Area (OA):", ["Select Area"] + oa_list)
        if sel_oa != "Select Area":
            df_oa = df_main[df_main['OA'] == sel_oa]
            latest_d = df_oa['Date'].max()
            low_cells = df_oa[(df_oa['Date'] == latest_d) & (df_oa['Data Volume - Total (GB)'] < 2.0)]
            if not low_cells.empty:
                st.error(f"⚠️ {len(low_cells)} cells below 2GB on {latest_d}")
                st.dataframe(low_cells[['Site Id', '4G Cell Name', 'Data Volume - Total (GB)', 'LOCATION']], use_container_width=True)
            else:
                st.success(f"All cells in {sel_oa} are healthy on {latest_d}. ✅")
else:
    st.info("👈 Please click 'Sync All Smart Data' in the sidebar to load files from GitHub.")
