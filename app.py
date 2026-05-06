import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob

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
if 'alarm_data' not in st.session_state:
    st.session_state['alarm_data'] = pd.DataFrame()

# 3. Helper Function - GitHub 'data' folder nundi read cheyadaniki
def load_data_from_github():
    data_path = 'data' 
    all_files = glob.glob(os.path.join(data_path, "*.csv"))
    if not all_files:
        st.error("Maama, 'data' folder lo CSV files emi dorakaledu! GitHub lo upload chesavo ledo chudu.")
        return pd.DataFrame()
    
    df_list = []
    for filename in all_files:
        try:
            df = pd.read_csv(filename)
            df_list.append(df)
        except Exception as e:
            st.error(f"Error reading {filename}: {e}")
    
    if not df_list: return pd.DataFrame()
    
    combined = pd.concat(df_list, ignore_index=True)
    
    # ✅ TYPE ERROR FIX: Data Volume ni numeric (numbers) loki marchadam
    vol_col = 'Data Volume - Total (GB)'
    if vol_col in combined.columns:
        combined[vol_col] = pd.to_numeric(combined[vol_col], errors='coerce').fillna(0)
    
    return combined

# --- SIDEBAR: DATA MANAGEMENT ---
with st.sidebar:
    st.header("📂 Data Management")
    
    # KPI SYNC SECTION
    st.subheader("📅 KPI Management")
    if st.button("🔄 Sync All KPI Data"):
        with st.spinner("GitHub data loading..."):
            df = load_data_from_github()
            if not df.empty:
                if 'Date' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date']).dt.date
                st.session_state['master_kpi'] = df.drop_duplicates()
                st.success(f"Loaded {len(st.session_state['master_kpi'])} records! 🚀")

    st.divider()
    
    # ✅ ALARM FILE UPLOAD SECTION - IKKADA ALARMS ADD CHESUKO MAAMA
    st.subheader("🚨 HW Alarm Management")
    uploaded_alarms = st.file_uploader("Upload Alarm CSV Files:", type=["csv"], accept_multiple_files=True)
    if st.button("📂 Load Selected Alarms"):
        if uploaded_alarms:
            try:
                alarm_dfs = [pd.read_csv(f) for f in uploaded_alarms]
                st.session_state['alarm_data'] = pd.concat(alarm_dfs, ignore_index=True)
                st.success(f"{len(uploaded_alarms)} Alarm Files Loaded! ⚠️")
            except Exception as e:
                st.error(f"Alarm Load Error: {e}")
        else:
            st.warning("Files select cheyi maama mundu!")

    st.divider()
    if st.button("🗑️ Clear Dashboard"):
        st.session_state['master_kpi'] = pd.DataFrame()
        st.session_state['alarm_data'] = pd.DataFrame()
        st.rerun()

# --- MAIN PAGE: ANALYSIS ---
df_main = st.session_state['master_kpi']
df_alarm = st.session_state['alarm_data']

if not df_main.empty:
    col_search, col_date = st.columns(2)
    with col_search:
        search_site = st.text_input("🔍 Search Site ID (e.g., AT2001):", "").strip().upper()
    with col_date:
        min_d = df_main['Date'].min()
        max_d = df_main['Date'].max()
        date_range = st.date_input("📅 Date Range Filter", [min_d, max_d])

    if search_site:
        mask = (df_main['Site Id'].str.contains(search_site, case=False, na=False))
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            mask &= (df_main['Date'] >= date_range[0]) & (df_main['Date'] <= date_range[1])
        
        site_data = df_main[mask].sort_values(by='Date')

        if not site_data.empty:
            st.subheader(f"📊 Traffic Analysis for {search_site}")
            fig = px.bar(site_data, x='Date', y='Data Volume - Total (GB)', 
                         color='4G Cell Name', barmode='group', height=450, text_auto='.2f')
            st.plotly_chart(fig, use_container_width=True)

            # KPI TABLE
            st.subheader("📉 RF KPI Parameters")
            st.dataframe(site_data, use_container_width=True)
            
            # ✅ ALARM DISPLAY FOR SEARCHED SITE
            if not df_alarm.empty:
                st.divider()
                st.subheader(f"⚠️ Alarms for {search_site}")
                # Alarm file lo Site Id column unna lekapoyina, search site string batti filter chesthundi
                site_alarms = df_alarm[df_alarm.astype(str).apply(lambda x: x.str.contains(search_site, case=False)).any(axis=1)]
                if not site_alarms.empty:
                    st.dataframe(site_alarms, use_container_width=True)
                else:
                    st.success(f"No active alarms found for {search_site}! ✅")
        else:
            st.warning(f"No KPI records found for {search_site}.")

    # --- LOW TRAFFIC TRACKER ---
    st.divider()
    st.markdown("### 🔍 Low Traffic Cell Tracker (OA Wise)")
    if 'OA' in df_main.columns:
        oa_list = sorted(df_main['OA'].dropna().unique())
        selected_oa = st.selectbox("🎯 Filter by Operational Area (OA):", ["Select Area"] + oa_list)
        if selected_oa != "Select Area":
            df_oa = df_main[df_main['OA'] == selected_oa]
            latest_date = df_oa['Date'].max()
            df_latest = df_oa[df_oa['Date'] == latest_date]
            
            # ✅ TypeError Fix logic ikkada panichesthundi
            low_cells = df_latest[df_latest['Data Volume - Total (GB)'] < 2.0]
            
            if not low_cells.empty:
                st.warning(f"⚠️ {len(low_cells)} cells below 2GB on {latest_date}")
                st.dataframe(low_cells[['Site Id', 'Date', '4G Cell Name', 'Data Volume - Total (GB)']], use_container_width=True)
            else:
                st.success(f"✅ All cells in {selected_oa} are above 2GB on {latest_date}.")
else:
    st.info("👈 Side-bar lo 'Sync All KPI Data' kotti modalupettu maama!")
