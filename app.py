import streamlit as st
import pandas as pd
import plotly.express as px
import glob
import os

# 1. Page Configuration & Styling (Big Fonts & Blue Headers)
st.set_page_config(layout="wide", page_title="Tejas Smart RAN Dashboard")

st.markdown("""
    <style>
    .report-title { font-size:32px !important; font-weight: bold; color: #1E3A8A; text-align: center; }
    /* Table letters peddaga kanipinchadaniki */
    .stDataFrame div[data-testid="stTable"] { font-size: 18px !important; }
    /* Blue Headers */
    thead tr th { background-color: #1E3A8A !important; color: white !important; }
    .status-card { border-radius: 10px; padding: 15px; margin: 10px 0; color: white; text-align: center; font-weight: bold; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #1E3A8A; color: white; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="report-title">📡 Tejas RAN Smart Performance & Status Dashboard</p>', unsafe_allow_html=True)

# Session State
if 'master_kpi' not in st.session_state: st.session_state['master_kpi'] = pd.DataFrame()
if 'alarm_data' not in st.session_state: st.session_state['alarm_data'] = pd.DataFrame()

# 2. Optimized Data Loading
def load_data():
    k_files = glob.glob("data/*.parquet") + glob.glob("data/*.csv")
    a_files = glob.glob("alarms/*")
    k_list, a_list = [], []
    
    for f in k_files:
        try:
            df = pd.read_parquet(f, engine='pyarrow') if f.endswith('.parquet') else pd.read_csv(f)
            df.columns = [c.strip() for c in df.columns] # Remove spaces in headers
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
    
    return final_k, (pd.concat(a_list, ignore_index=True) if a_list else pd.DataFrame())

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

# --- MAIN DASHBOARD ---
df_main = st.session_state['master_kpi']
df_alarm = st.session_state['alarm_data']

if not df_main.empty:
    search_site = st.text_input("🔍 Enter Site ID (e.g., AT2001):").strip().upper()

    if search_site:
        site_data = df_main[df_main['Site Id'].astype(str).str.contains(search_site, na=False)]
        
        if not site_data.empty:
            # --- STATUS CARDS ---
            st.subheader(f"⚡ Live Status: {search_site}")
            cell_ids = sorted(site_data['Cell ID'].unique())
            status_cols = st.columns(len(cell_ids))
            
            for i, cell in enumerate(cell_ids):
                has_alarm = False
                if not df_alarm.empty:
                    has_alarm = df_alarm.astype(str).apply(lambda x: x.str.contains(search_site, case=False)).any(axis=1).any()
                
                color = "#EF4444" if has_alarm else "#10B981"
                status_cols[i].markdown(f'<div class="status-card" style="background-color: {color};">{cell}<br>STATUS: {"ALARM" if has_alarm else "HEALTHY"}</div>', unsafe_allow_html=True)

            # --- GRAPH ---
            st.subheader("📊 Historical Traffic Analysis")
            fig = px.bar(site_data, x='Date', y='Data Volume - Total (GB)', color='Cell ID', facet_col='Band', barmode='group', text_auto='.1f')
            st.plotly_chart(fig, use_container_width=True)
            
            # --- LOW TRAFFIC INVESTIGATION (< 2GB) ---
            st.subheader("📉 Investigation: Low Traffic Analysis")
            low_traf = site_data[site_data['Data Volume - Total (GB)'] < 2.0]
            if not low_traf.empty:
                sel_c = st.selectbox("👉 Select Low Traffic Cell to Analyze Why:", low_traf['4G Cell Name'].unique())
                c_row = low_traf[low_traf['4G Cell Name'] == sel_c]
                
                # RCA Display without iloc crash
                st.info(f"**Analysis for {sel_c}:** Traffic is {c_row['Data Volume - Total (GB)'].values[0]} GB. Check RF KPIs and Site Alarms below.")
                st.dataframe(low_traf[['Date', '4G Cell Name', 'Data Volume - Total (GB)']], use_container_width=True, hide_index=True)
            
            # --- ALARM & RECORDS ---
            st.subheader("📋 Performance Records")
            TARGET_COLS = ['Date', 'Site Id', '4G Cell Name', 'Data Volume - Total (GB)', 'RRC Connection Success Rate(All) (%)', 'E-UTRAN Cell availability (%)']
            disp = [c for c in TARGET_COLS if c in site_data.columns]
            st.dataframe(site_data[disp], use_container_width=True, hide_index=True)
else:
    st.info("👈 Click Sync to load data.")
