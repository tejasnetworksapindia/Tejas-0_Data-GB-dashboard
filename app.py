import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob

# 1. Webpage Configuration
st.set_page_config(layout="wide", page_title="Tejas Smart RAN Dashboard")

st.markdown('<p style="font-size:28px;font-weight:bold;color:#1E3A8A;">📡 Tejas RAN Performance & Historical Master Dashboard</p>', unsafe_allow_html=True)

# 2. Session State Storage
if 'master_kpi' not in st.session_state:
    st.session_state['master_kpi'] = pd.DataFrame()
if 'alarm_data' not in st.session_state:
    st.session_state['alarm_data'] = pd.DataFrame()

# 3. Helper Function - GitHub నుండి డేటా రీడ్ చేయడానికి
def load_data_from_github():
    data_path = 'data' 
    all_files = glob.glob(os.path.join(data_path, "*.csv"))
    if not all_files:
        st.error("Maama, 'data' folder lo CSV files dorakaledu!")
        return pd.DataFrame()
    
    df_list = []
    for filename in all_files:
        df = pd.read_csv(filename)
        df_list.append(df)
    
    combined = pd.concat(df_list, ignore_index=True)
    
    # ✅ ERROR FIX: Data Volume ని నెంబర్ లోకి మార్చడం
    col_name = 'Data Volume - Total (GB)'
    if col_name in combined.columns:
        combined[col_name] = pd.to_numeric(combined[col_name], errors='coerce').fillna(0)
    
    return combined

# --- SIDEBAR: DATA MANAGEMENT ---
with st.sidebar:
    st.header("📂 Data Management")
    
    # KPI SYNC
    if st.button("🔄 Sync All KPI Data"):
        df = load_data_from_github()
        if not df.empty:
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date']).dt.date
            st.session_state['master_kpi'] = df.drop_duplicates()
            st.success("KPI Data Loaded! 🚀")

    st.divider()
    
    # ✅ ALARM FILE UPLOAD OPTION
    st.subheader("🚨 HW Alarm Management")
    uploaded_alarms = st.file_uploader("Upload Alarm CSV Files:", type=["csv"], accept_multiple_files=True)
    if st.button("📂 Load Alarms"):
        if uploaded_alarms:
            alarm_dfs = [pd.read_csv(f) for f in uploaded_alarms]
            st.session_state['alarm_data'] = pd.concat(alarm_dfs, ignore_index=True)
            st.success("Alarms Loaded! ⚠️")

    if st.button("🗑️ Clear All"):
        st.session_state['master_kpi'] = pd.DataFrame()
        st.session_state['alarm_data'] = pd.DataFrame()
        st.rerun()

# --- MAIN PAGE ---
df_main = st.session_state['master_kpi']
df_alarm = st.session_state['alarm_data']

if not df_main.empty:
    col_search, col_date = st.columns(2)
    with col_search:
        search_site = st.text_input("🔍 Search Site ID:", "").strip().upper()
    with col_date:
        date_range = st.date_input("📅 Date Filter", [df_main['Date'].min(), df_main['Date'].max()])

    if search_site:
        mask = (df_main['Site Id'].str.contains(search_site, case=False, na=False))
        site_data = df_main[mask].sort_values(by='Date')

        if not site_data.empty:
            st.subheader(f"📊 Traffic Analysis: {search_site}")
            fig = px.bar(site_data, x='Date', y='Data Volume - Total (GB)', color='4G Cell Name', barmode='group')
            st.plotly_chart(fig, use_container_width=True)

            # KPI TABLE
            st.subheader("📉 RF KPI Parameters")
            st.dataframe(site_data, use_container_width=True)
            
            # ✅ ALARM DISPLAY FOR SEARCHED SITE
            if not df_alarm.empty:
                st.subheader("⚠️ Site Alarms")
                site_alarms = df_alarm[df_alarm.astype(str).apply(lambda x: x.str.contains(search_site, case=False)).any(axis=1)]
                if not site_alarms.empty:
                    st.dataframe(site_alarms, use_container_width=True)
                else:
                    st.success("No alarms found for this site! ✅")

    # --- LOW TRAFFIC TRACKER ---
    st.divider()
    st.markdown("### 🔍 Low Traffic Cell Tracker (OA Wise)")
    if 'OA' in df_main.columns:
        oa_list = sorted(df_main['OA'].dropna().unique())
        selected_oa = st.selectbox("🎯 Select OA:", ["Select Area"] + oa_list)
        if selected_oa != "Select Area":
            df_oa = df_main[df_main['OA'] == selected_oa]
            # ✅ నెంబర్ లోకి మారింది కాబట్టి ఇక్కడ ఎర్రర్ రాదు
            low_cells = df_oa[df_oa['Data Volume - Total (GB)'] < 2.0]
            if not low_cells.empty:
                st.warning(f"⚠️ {len(low_cells)} cells below 2GB")
                st.dataframe(low_cells[['Site Id', 'Date', 'Data Volume - Total (GB)']], use_container_width=True)
            else:
                st.success("All cells above 2GB! ✅")
else:
    st.info("👈 Side-bar లో 'Sync' నొక్కు మామా!")
