import streamlit as st
import pandas as pd
import plotly.express as px
import glob
import os

# 1. PAGE CONFIG & PROFESSIONAL STYLING (Big Fonts & RCA Look)
st.set_page_config(layout="wide", page_title="Tejas Smart RAN Dashboard")

st.markdown("""
    <style>
    .report-title { font-size:32px !important; font-weight: bold; color: #1E3A8A; text-align: center; }
    /* Table letters peddaga clear ga kanipinchadaniki */
    .stDataFrame div[data-testid="stTable"] { font-size: 18px !important; }
    .stMetric { background-color: #f1f3f9; border-radius: 10px; padding: 15px; border: 1px solid #1E3A8A; }
    .rca-card { background-color: #ffffff; padding: 20px; border-radius: 15px; border-left: 8px solid #ff4b4b; box-shadow: 2px 2px 10px rgba(0,0,0,0.1); }
    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #1E3A8A; color: white; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="report-title">📡 Tejas RAN Smart Performance & RCA Dashboard</p>', unsafe_allow_html=True)

# 2. TARGETED KPI COLUMNS (Kevalam Traffic Impacting Columns mathrame)
TARGET_COLS = [
    'Date', 'Site Id', '4G Cell Name', 'Data Volume - Total (GB)',
    'RRC Connection Success Rate(%)', 'ERAB Setup Success Rate(%)',
    'RRC Connection Max Users', 'Cell Availability(%)'
]

# SESSION STATE
if 'master_kpi' not in st.session_state: st.session_state['master_kpi'] = pd.DataFrame()
if 'alarm_data' not in st.session_state: st.session_state['alarm_data'] = pd.DataFrame()

# 3. SMART DATA LOADING (Supports Parquet, CSV, and Excel)
def load_all_data():
    kpi_files = glob.glob("data/*")
    alarm_files = glob.glob("alarms/*")
    
    k_list = []
    for f in kpi_files:
        try:
            if f.endswith('.parquet'): df = pd.read_parquet(f, engine='pyarrow')
            else: df = pd.read_csv(f)
            
            if '4G Cell Name' in df.columns:
                df['Cell ID'] = "Cell " + df['4G Cell Name'].astype(str).str[-1]
                df['Band'] = df['4G Cell Name'].astype(str).str[:6]
            k_list.append(df)
        except: continue

    a_list = []
    pattern = 'Critical|Major|Service Affecting|Outage|Down|VSWR|Link Down'
    for f in alarm_files:
        try:
            if f.endswith('.parquet'): df = pd.read_parquet(f, engine='pyarrow')
            elif f.endswith('.xlsx'): df = pd.read_excel(f, engine='openpyxl')
            else: df = pd.read_csv(f)
            mask = df.astype(str).apply(lambda x: x.str.contains(pattern, case=False)).any(axis=1)
            a_list.append(df[mask])
        except: continue
            
    final_kpi = pd.concat(k_list, ignore_index=True) if k_list else pd.DataFrame()
    if not final_kpi.empty and 'Data Volume - Total (GB)' in final_kpi.columns:
        final_kpi['Data Volume - Total (GB)'] = pd.to_numeric(final_kpi['Data Volume - Total (GB)'], errors='coerce').fillna(0)
    
    return final_kpi, (pd.concat(a_list, ignore_index=True) if a_list else pd.DataFrame())

# --- SIDEBAR ---
with st.sidebar:
    st.header("📂 Data Sync Center")
    if st.button("🔄 Sync All Data (Smart Load)"):
        with st.spinner("Processing Files..."):
            k, a = load_all_data()
            if not k.empty and 'Date' in k.columns:
                k['Date'] = pd.to_datetime(k['Date']).dt.date
            st.session_state['master_kpi'] = k.drop_duplicates()
            st.session_state['alarm_data'] = a
            st.success(f"Sync Done! Records: {len(k)}")

    st.divider()
    if st.button("🗑️ Reset Dashboard"):
        st.session_state['master_kpi'] = pd.DataFrame()
        st.session_state['alarm_data'] = pd.DataFrame()
        st.rerun()

# --- MAIN DASHBOARD LOGIC ---
df_main = st.session_state['master_kpi']
df_alarm = st.session_state['alarm_data']

if not df_main.empty:
    # 4. FILTERED PERFORMANCE TABLE (Big Fonts & Clear View)
    st.subheader("📋 Performance Overview (Key Columns Only)")
    display_cols = [c for c in TARGET_COLS if c in df_main.columns]
    st.dataframe(df_main[display_cols].sort_values('Date', ascending=False), use_container_width=True, height=400)

    st.divider()

    # 5. SMART INVESTIGATION: WHY IS TRAFFIC < 2GB?
    st.subheader("🔍 Investigation: Click a Low Traffic Cell to Analyze")
    low_traf_cells = df_main[df_main['Data Volume - Total (GB)'] < 2.0]

    if not low_traf_cells.empty:
        selected_cell = st.selectbox("🎯 Select a Cell to Diagnose Why Traffic is Low:", 
                                   options=low_traf_cells['4G Cell Name'].unique())
        
        if selected_cell:
            c_data = df_main[df_main['4G Cell Name'] == selected_cell].iloc[0]
            site_id = c_data['Site Id']

            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.markdown("### 📊 RF KPI Status")
                st.metric("Total Traffic", f"{c_data.get('Data Volume - Total (GB)', 0)} GB", delta="- LOW", delta_color="inverse")
                st.metric("RRC Success %", f"{c_data.get('RRC Connection Success Rate(%)', 0)}%")
                st.metric("Availability %", f"{c_data.get('Cell Availability(%)', 0)}%")
                st.metric("Active Users (Max)", f"{c_data.get('RRC Connection Max Users', 0)}")

            with col2:
                st.markdown("### 🚨 Root Cause Analysis (RCA)")
                site_alarms = pd.DataFrame()
                if not df_alarm.empty:
                    site_alarms = df_alarm[df_alarm.astype(str).apply(lambda x: x.str.contains(site_id, case=False)).any(axis=1)]
                
                st.markdown('<div class="rca-card">', unsafe_allow_html=True)
                # RCA Logic
                if c_data.get('Cell Availability(%)', 100) < 90:
                    st.error(f"❌ **CELL DOWN:** Availability only {c_data.get('Cell Availability(%)')}%")
                elif not site_alarms.empty:
                    st.error(f"❌ **HARDWARE ISSUE:** Active Alarms found for this Site!")
                    st.dataframe(site_alarms[['Alarm Name', 'Severity', 'Event Time']], use_container_width=True)
                elif c_data.get('RRC Connection Success Rate(%)', 100) < 85:
                    st.warning("⚠️ **SIGNALING ISSUE:** Poor RRC Success. Check for Interference.")
                elif c_data.get('RRC Connection Max Users', 0) < 3:
                    st.info("ℹ️ **LOW FOOTFALL:** Healthy Cell but No Users in the area.")
                else:
                    st.info("🔍 **OBSERVATION:** KPIs look normal. Check Neighbors or Transmission.")
                st.markdown('</div>', unsafe_allow_html=True)

    else:
        st.success("All cells are performing healthy (> 2GB)! ✅")

    # 6. HISTORICAL TRENDS
    st.divider()
    st.subheader("📈 Traffic Analysis by Band & Cell")
    search_site = st.text_input("🔍 Search Site ID for Historical Trends:", "").strip().upper()
    if search_site:
        site_plot_data = df_main[df_main['Site Id'].str.contains(search_site, na=False)]
        if not site_plot_data.empty:
            fig = px.bar(site_plot_data, x='Date', y='Data Volume - Total (GB)', color='Cell ID', facet_col='Band', barmode='group')
            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👈 Please sync data from the sidebar to load files.")
