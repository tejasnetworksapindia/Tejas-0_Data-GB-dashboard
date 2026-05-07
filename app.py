import streamlit as st
import pandas as pd
import plotly.express as px
import glob
import os

# 1. Page Configuration & Styling
st.set_page_config(layout="wide", page_title="Tejas Smart RAN Dashboard")

st.markdown("""
    <style>
    .report-title { font-size:30px !important; font-weight: bold; color: #1E3A8A; text-align: center; }
    thead tr th { background-color: #1E3A8A !important; color: white !important; font-size: 16px !important; }
    .stDataFrame { border: 1px solid #1E3A8A; border-radius: 5px; font-size: 16px !important; }
    .stButton>button { width: 100%; border-radius: 5px; background-color: #1E3A8A; color: white; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="report-title">📡 Tejas RAN Smart Performance & Historical Dashboard</p>', unsafe_allow_html=True)

# Session State
if 'master_kpi' not in st.session_state: st.session_state['master_kpi'] = pd.DataFrame()
if 'alarm_data' not in st.session_state: st.session_state['alarm_data'] = pd.DataFrame()

# 2. Simplified Data Loading (No RCA logic inside)
def load_data():
    k_files = glob.glob("data/*.parquet") + glob.glob("data/*.csv")
    a_files = glob.glob("alarms/*")
    k_list, a_list = [], []
    
    for f in k_files:
        try:
            df = pd.read_parquet(f, engine='pyarrow') if f.endswith('.parquet') else pd.read_csv(f)
            df.columns = [c.strip() for c in df.columns]
            if '4G Cell Name' in df.columns:
                df['Cell ID'] = "Cell " + df['4G Cell Name'].astype(str).str[-1]
                df['Band'] = df['4G Cell Name'].astype(str).str[:6]
            k_list.append(df)
        except: continue
        
    for f in a_files:
        try:
            df = pd.read_parquet(f) if f.endswith('.parquet') else (pd.read_excel(f) if f.endswith('.xlsx') else pd.read_csv(f))
            df.columns = [c.strip() for c in df.columns]
            a_list.append(df)
        except: continue
    
    final_k = pd.concat(k_list, ignore_index=True) if k_list else pd.DataFrame()
    if not final_k.empty:
        final_k['Date'] = pd.to_datetime(final_k['Date'], errors='coerce').dt.date
        final_k['Data Volume - Total (GB)'] = pd.to_numeric(final_k['Data Volume - Total (GB)'], errors='coerce').fillna(0)
        
    return final_k, pd.concat(a_list, ignore_index=True) if a_list else pd.DataFrame()

# --- SIDEBAR ---
with st.sidebar:
    st.header("📂 Data Controls")
    if st.button("🔄 Sync All Smart Data"):
        with st.spinner("Processing..."):
            k, a = load_data()
            if not k.empty:
                st.session_state['master_kpi'] = k.drop_duplicates()
                st.session_state['alarm_data'] = a
                st.success("Sync Done! 🚀")
            else: st.error("No Data Found!")

# --- MAIN DASHBOARD ---
df_main = st.session_state['master_kpi']
df_alarm = st.session_state['alarm_data']

if not df_main.empty:
    search_site = st.text_input("🔍 Search Site ID (e.g., AT2001):").strip().upper()
    if search_site:
        site_data = df_main[df_main['Site Id'].astype(str).str.contains(search_site, na=False)].sort_values('Date', ascending=False)
        
        if not site_data.empty:
            # 📊 TRAFFIC GRAPH
            st.subheader(f"📊 Traffic Analysis: {search_site}")
            fig = px.bar(site_data, x='Date', y='Data Volume - Total (GB)', color='Cell ID', facet_col='Band', 
                         barmode='group', height=400, text_auto='.1f')
            st.plotly_chart(fig, use_container_width=True)

            col_l, col_r = st.columns(2)
            with col_l:
                st.subheader("🚨 Site Status & Alarms")
                s_alarms = df_alarm[df_alarm.astype(str).apply(lambda x: x.str.contains(search_site, case=False)).any(axis=1)] if not df_alarm.empty else pd.DataFrame()
                st.dataframe(s_alarms, use_container_width=True, hide_index=True)

            with col_r:
                st.subheader("📉 Low Traffic Cells (< 2GB)")
                low_traf = site_data[site_data['Data Volume - Total (GB)'] < 2.0]
                st.dataframe(low_traf[['Date', '4G Cell Name', 'Data Volume - Total (GB)']], use_container_width=True, hide_index=True)

            st.subheader("📋 Key RF Records")
            TARGET_COLS = ['Date', 'Site Id', '4G Cell Name', 'Data Volume - Total (GB)', 'RRC Connection Success Rate(All) (%)', 'E-UTRAN Cell availability (%)']
            disp = [c for c in TARGET_COLS if c in site_data.columns]
            st.dataframe(site_data[disp], use_container_width=True, hide_index=True)

    # --- OA WISE TRACKER ---
    st.divider()
    st.subheader("🎯 OA Wise Tracker (Latest)")
    if 'OA' in df_main.columns:
        sel_oa = st.selectbox("Filter OA Area:", ["Select Area"] + sorted(df_main['OA'].dropna().unique()))
        if sel_oa != "Select Area":
            oa_df = df_main[df_main['OA'] == sel_oa]
            latest_d = oa_df['Date'].max()
            oa_low = oa_df[(oa_df['Date'] == latest_d) & (oa_df['Data Volume - Total (GB)'] < 2.0)]
            st.dataframe(oa_low[['Site Id', '4G Cell Name', 'Data Volume - Total (GB)']], use_container_width=True, hide_index=True)
else:
    st.info("👈 Please sync data from the sidebar.")
