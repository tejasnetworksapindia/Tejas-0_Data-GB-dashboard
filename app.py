import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob

# 1. Webpage Configuration
st.set_page_config(layout="wide", page_title="Tejas Smart RAN Dashboard")

# Custom CSS for better look
st.markdown("""
    <style>
    .report-title { font-size:28px !important; font-weight: bold; color: #1E3A8A; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #1E3A8A; color: white; }
    .stDataFrame { border: 1px solid #1E3A8A; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="report-title">📡 Tejas RAN Smart Performance & Historical Dashboard</p>', unsafe_allow_html=True)

# 2. Session State Storage
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
        except: pass
    combined = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()
    if 'Data Volume - Total (GB)' in combined.columns:
        combined['Data Volume - Total (GB)'] = pd.to_numeric(combined['Data Volume - Total (GB)'], errors='coerce').fillna(0)
    return combined

def load_alarm_data():
    files = glob.glob("alarms/*.xlsx") + glob.glob("alarms/*.csv")
    if not files: return pd.DataFrame()
    df_list = []
    # ✅ SMART ALARM FILTERING LOGIC
    keywords = ['Critical', 'Major', 'Service Affecting', 'Outage', 'Down', 'VSWR', 'Link Down', 'Loss of']
    pattern = '|'.join(keywords)
    
    for f in files:
        try:
            df_temp = pd.read_excel(f) if f.endswith('.xlsx') else pd.read_csv(f)
            # కేవలం పనికివచ్చే అలారమ్స్ మాత్రమే తీసుకుంటుంది
            mask = df_temp.astype(str).apply(lambda x: x.str.contains(pattern, case=False)).any(axis=1)
            df_list.append(df_temp[mask])
        except: pass
    return pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()

# --- SIDEBAR: DATA MANAGEMENT ---
with st.sidebar:
    st.header("📂 Data Sync Center")
    st.write("GitHub ఫోల్డర్స్ నుండి డేటాని తెచ్చుకో మామా.")
    
    if st.button("🔄 Sync All Smart Data"):
        with st.spinner("ఫిల్టర్ చేసిన డేటాని లోడ్ చేస్తున్నాను..."):
            # KPI Loading
            kpi_df = load_kpi_data()
            if not kpi_df.empty:
                kpi_df['Date'] = pd.to_datetime(kpi_df['Date']).dt.date
                kpi_df['Band'] = kpi_df['4G Cell Name'].str[:6] # T4AP41, etc.
                st.session_state['master_kpi'] = kpi_df.drop_duplicates()
            
            # Alarm Loading
            st.session_state['alarm_data'] = load_alarm_data()
            st.success("Cloud Data Synced! 🚀")

    st.divider()
    st.subheader("🧹 Maintenance")
    if st.button("🗑️ Clear Dashboard Cache"):
        st.session_state['master_kpi'] = pd.DataFrame()
        st.session_state['alarm_data'] = pd.DataFrame()
        st.rerun()

# --- MAIN PAGE: SEARCH & ANALYSIS ---
df_main = st.session_state['master_kpi']
df_alarm = st.session_state['alarm_data']

if not df_main.empty:
    col_s, col_d = st.columns([2, 1])
    with col_s:
        search_site = st.text_input("🔍 Search Site ID (e.g., AT2002):", "").strip().upper()
    with col_d:
        min_d, max_d = df_main['Date'].min(), df_main['Date'].max()
        date_range = st.date_input("📅 Select Date Range", [min_d, max_d])

    if search_site:
        mask = (df_main['Site Id'].str.contains(search_site, case=False, na=False))
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            mask &= (df_main['Date'] >= date_range[0]) & (df_main['Date'] <= date_range[1])
        
        site_data = df_main[mask].sort_values(by=['Date', 'Band'])

        if not site_data.empty:
            # --- TRAFFIC GRAPH ---
            st.subheader(f"📊 Traffic Analysis for {search_site}")
            fig = px.bar(site_data, x='Date', y='Data Volume - Total (GB)', 
                         color='Band', barmode='group', height=450, text_auto='.2f')
            fig.update_xaxes(type='category', tickangle=45) 
            st.plotly_chart(fig, use_container_width=True)

            # --- SMART ANALYSIS SECTION ---
            st.divider()
            col_kpi, col_alm = st.columns(2)
            
            with col_kpi:
                st.subheader("📉 Traffic Trouble Tracker (< 2GB)")
                low_traf = site_data[site_data['Data Volume - Total (GB)'] < 2.0]
                if not low_traf.empty:
                    st.warning(f"Found {len(low_traf)} low traffic bands!")
                    st.dataframe(low_traf[['Date', '4G Cell Name', 'Data Volume - Total (GB)']], use_container_width=True)
                else:
                    st.success("All bands performing healthy! ✅")

            with col_alm:
                st.subheader("🚨 Critical/Major Alarms")
                if not df_alarm.empty:
                    site_alarms = df_alarm[df_alarm.astype(str).apply(lambda x: x.str.contains(search_site, case=False)).any(axis=1)]
                    if not site_alarms.empty:
                        st.error(f"Alert: {len(site_alarms)} critical issues found!")
                        st.dataframe(site_alarms, use_container_width=True)
                    else:
                        st.success("No active service-affecting alarms. ✅")
            
            st.divider()
            st.subheader("📋 Full KPI Detailed Table")
            st.dataframe(site_data, use_container_width=True)
        else:
            st.warning("Maama, ee site ID tho data emi dorakaledu.")

    # --- OA TRACKER SECTION ---
    st.divider()
    st.markdown("### 🔍 OA Wise Low Traffic Cells (Current Status)")
    if 'OA' in df_main.columns:
        oa_list = sorted(df_main['OA'].dropna().unique())
        sel_oa = st.selectbox("🎯 Filter by Operational Area (OA):", ["Select Area"] + oa_list)
        if sel_oa != "Select Area":
            df_oa = df_main[df_main['OA'] == sel_oa]
            latest_d = df_oa['Date'].max()
            low_cells = df_oa[(df_oa['Date'] == latest_d) & (df_oa['Data Volume - Total (GB)'] < 2.0)]
            if not low_cells.empty:
                st.error(f"⚠️ Found {len(low_cells)} cells below 2GB on {latest_d}")
                st.dataframe(low_cells[['Site Id', '4G Cell Name', 'Data Volume - Total (GB)', 'LOCATION']], use_container_width=True)
            else:
                st.success(f"Excellent! All cells in {sel_oa} are healthy on {latest_d}. ✅")
else:
    st.info("👈 సైడ్ బార్ లో 'Sync' బటన్ నొక్కితే GitHub డేటా లోడ్ అవుతుంది మామా!")
