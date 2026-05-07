import streamlit as st
import pandas as pd
import plotly.express as px
import glob
import os

# 1. PAGE CONFIG & CUSTOM STYLING (Big Fonts & Professional Look)
st.set_page_config(layout="wide", page_title="Tejas Smart RAN Dashboard")

st.markdown("""
    <style>
    .report-title { font-size:32px !important; font-weight: bold; color: #1E3A8A; text-align: center; }
    /* Table font size penchadaniki (Big Letters) */
    .stDataFrame div[data-testid="stTable"] { font-size: 18px !important; }
    .stMetric { background-color: #f1f3f9; border-radius: 10px; padding: 15px; border: 1px solid #1E3A8A; }
    .rca-card { background-color: #ffffff; padding: 20px; border-radius: 15px; border-left: 8px solid #ff4b4b; box-shadow: 2px 2px 10px rgba(0,0,0,0.1); }
    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #1E3A8A; color: white; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="report-title">📡 Tejas RAN Smart Performance & RCA Dashboard</p>', unsafe_allow_html=True)

# 2. DEFINING TARGETED KPI COLUMNS (Traffic Impacting Only)
# Nee screen lo unna important columns mathrame ikkada filter chesthunnam
TARGET_COLS = [
    'Date', 'Site Id', '4G Cell Name', 'Data Volume - Total (GB)',
    'RRC Connection Success Rate(%)', 'ERAB Setup Success Rate(%)',
    'RRC Connection Max Users', 'Cell Availability(%)', 'Inter-eNB Handover Success Rate(%)'
]

# 3. SESSION STATE
if 'master_kpi' not in st.session_state: st.session_state['master_kpi'] = pd.DataFrame()
if 'alarm_data' not in st.session_state: st.session_state['alarm_data'] = pd.DataFrame()

# 4. DATA LOADING LOGIC (Parquet + CSV + Excel)
def load_all_data():
    # KPI Loading
    kpi_files = glob.glob("data/*.parquet") + glob.glob("data/*.csv")
    k_list = []
    for f in kpi_files:
        try:
            df = pd.read_parquet(f) if f.endswith('.parquet') else pd.read_csv(f)
            if '4G Cell Name' in df.columns:
                df['Cell ID'] = "Cell " + df['4G Cell Name'].astype(str).str[-1]
                df['Band'] = df['4G Cell Name'].astype(str).str[:6]
            k_list.append(df)
        except Exception as e: st.error(f"KPI Load Error ({os.path.basename(f)}): {e}")

    # Alarm Loading (Filtering Critical/Major issues)
    alarm_files = glob.glob("alarms/*.xlsx") + glob.glob("alarms/*.csv") + glob.glob("alarms/*.parquet")
    a_list = []
    keywords = ['Critical', 'Major', 'Service Affecting', 'Outage', 'Down', 'VSWR', 'Link Down']
    pattern = '|'.join(keywords)
    for f in alarm_files:
        try:
            if f.endswith('.parquet'): df = pd.read_parquet(f)
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
    if st.button("🔄 Sync Parquet & Cloud Data"):
        with st.spinner("Processing Large Datasets..."):
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
    # 5. KEY PERFORMANCE TABLE (Targeted Columns & Big Fonts)
    st.subheader("📋 Performance Records (Optimized View)")
    # Filter only the columns we need to reduce clutter
    display_cols = [c for c in TARGET_COLS if c in df_main.columns]
    st.dataframe(df_main[display_cols].sort_values('Date', ascending=False), use_container_width=True, height=400)

    st.divider()

    # 6. CLICK-TO-ANALYZE: LOW TRAFFIC INVESTIGATION (< 2GB)
    st.subheader("🔍 Smart Investigation: Why is Traffic Below 2GB?")
    low_traf_cells = df_main[df_main['Data Volume - Total (GB)'] < 2.0]

    if not low_traf_cells.empty:
        # Dropdown for the user to "Click" / Select a cell
        selected_cell = st.selectbox("🎯 Select a Cell to Diagnose:", 
                                   options=low_traf_cells['4G Cell Name'].unique(),
                                   index=0)
        
        if selected_cell:
            # Extracting specific cell data
            c_data = df_main[df_main['4G Cell Name'] == selected_cell].iloc[0]
            site_id = c_data['Site Id']

            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.markdown("### 📊 RF KPI Status")
                st.metric("Total Traffic", f"{c_data.get('Data Volume - Total (GB)', 0)} GB", delta="- LOW", delta_color="inverse")
                st.metric("RRC Success %", f"{c_data.get('RRC Connection Success Rate(%)', 0)}%")
                st.metric("Cell Availability %", f"{c_data.get('Cell Availability(%)', 0)}%")
                st.metric("Active Users (Max)", f"{c_data.get('RRC Connection Max Users', 0)}")

            with col2:
                st.markdown("### 🚨 Root Cause Analysis (RCA)")
                
                # Check for Alarms
                site_alarms = pd.DataFrame()
                if not df_alarm.empty:
                    site_alarms = df_alarm[df_alarm.astype(str).apply(lambda x: x.str.contains(site_id, case=False)).any(axis=1)]
                
                with st.container():
                    st.markdown('<div class="rca-card">', unsafe_allow_html=True)
                    
                    # Logic to determine the "Why"
                    if c_data.get('Cell Availability(%)', 100) < 90:
                        st.error(f"❌ **CRITICAL:** Cell was DOWN for a significant time. Availability is only {c_data.get('Cell Availability(%)')}%")
                    elif not site_alarms.empty:
                        st.error(f"❌ **HARDWARE ALARM:** Found {len(site_alarms)} active alarms for this site!")
                        st.dataframe(site_alarms[['Alarm Name', 'Severity', 'Event Time']], use_container_width=True)
                    elif c_data.get('RRC Connection Success Rate(%)', 100) < 85:
                        st.warning("⚠️ **SIGNALING ISSUE:** Poor RRC Success Rate. Users are failing to connect. Check Interference.")
                    elif c_data.get('RRC Connection Max Users', 0) < 3:
                        st.info("ℹ️ **LOW FOOTFALL:** Cell is active and healthy, but very few users are in the area.")
                    else:
                        st.info("🔍 **OTHER:** KPIs look okay. Check for specific neighbor relations or transmission drops.")
                    
                    st.markdown('</div>', unsafe_allow_html=True)

            # 7. HISTORICAL TREND FOR SELECTED CELL
            st.divider()
            st.subheader(f"📈 7-Day Traffic Trend: {selected_cell}")
            hist_data = df_main[df_main['4G Cell Name'] == selected_cell].sort_values('Date')
            fig = px.line(hist_data, x='Date', y='Data Volume - Total (GB)', markers=True, text='Data Volume - Total (GB)')
            st.plotly_chart(fig, use_container_width=True)

    else:
        st.success("All cells are performing healthy (> 2GB)! ✅")

else:
    st.info("👈 Please click 'Sync Parquet & Cloud Data' in the sidebar to start.")
