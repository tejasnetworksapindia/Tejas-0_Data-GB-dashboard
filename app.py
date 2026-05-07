import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob

# 1. Webpage Configuration & Professional Styling
st.set_page_config(layout="wide", page_title="Tejas Smart RAN Dashboard")

st.markdown("""
    <style>
    .report-title { font-size:30px !important; font-weight: bold; color: #1E3A8A; margin-bottom: -15px; }
    h3 { margin-top: 10px !important; margin-bottom: 5px !important; color: #1E3A8A; font-size: 22px !important; font-weight: bold; }
    .block-container { padding-top: 1.5rem !important; padding-bottom: 1rem !important; }
    .element-container { margin-bottom: 0.8rem !important; }
    thead tr th { background-color: #1E3A8A !important; color: white !important; font-size: 16px !important; }
    .stDataFrame { border: 1px solid #1E3A8A; border-radius: 5px; font-size: 16px !important; }
    .rca-box { 
        background-color: #EBF5FB; 
        padding: 15px; 
        border-radius: 8px; 
        border-left: 8px solid #1E3A8A; 
        margin-bottom: 10px;
        color: #1E3A8A;
        font-weight: bold;
    }
    .stButton>button { width: 100%; border-radius: 5px; background-color: #1E3A8A; color: white; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="report-title">📡 Tejas RAN Smart Performance & Historical Dashboard</p>', unsafe_allow_html=True)

# 2. Session State Initialization
if 'master_kpi' not in st.session_state: st.session_state['master_kpi'] = pd.DataFrame()
if 'alarm_data' not in st.session_state: st.session_state['alarm_data'] = pd.DataFrame()

# Helper for RCA Reasoning Logic (Fixed & Robust)
def get_rca_reason(row, alarm_df, site_id):
    try:
        if row.get('Cell Availability(%)', 100) < 90: return "❌ Cell Down (Low Availability)"
        
        # Check for active alarms for this site
        if not alarm_df.empty:
            site_alarms = alarm_df[alarm_df.astype(str).apply(lambda x: x.str.contains(str(site_id), case=False)).any(axis=1)]
            if not site_alarms.empty: return "🚨 Active Hardware Alarms"
        
        if row.get('RRC Connection Success Rate(%)', 100) < 85: return "📉 Poor Signaling (RRC Issue)"
        if row.get('RRC Connection Max Users', 1) == 0: return "🚫 No Active Users"
        return "⚠️ Low Footfall / Area Traffic"
    except: return "🔍 Analyzing..."

# 3. Targeted Columns
TARGET_RF_COLS = ['Date', 'Site Id', '4G Cell Name', 'Data Volume - Total (GB)', 
                  'RRC Connection Success Rate(%)', 'Cell Availability(%)', 'RRC Connection Max Users']

# 4. Data Loading Logic
def load_data():
    k_files = glob.glob("data/*.parquet") + glob.glob("data/*.csv")
    a_files = glob.glob("alarms/*")
    k_list, a_list = [], []
    
    for f in k_files:
        try:
            df = pd.read_parquet(f, engine='pyarrow') if f.endswith('.parquet') else pd.read_csv(f)
            if '4G Cell Name' in df.columns:
                df['Cell ID'] = "Cell " + df['4G Cell Name'].astype(str).str[-1]
                df['Band'] = df['4G Cell Name'].astype(str).str[:6]
            k_list.append(df)
        except: continue
        
    for f in a_files:
        try:
            df = pd.read_parquet(f) if f.endswith('.parquet') else (pd.read_excel(f) if f.endswith('.xlsx') else pd.read_csv(f))
            a_list.append(df)
        except: continue
    
    k_df = pd.concat(k_list, ignore_index=True) if k_list else pd.DataFrame()
    a_df = pd.concat(a_list, ignore_index=True) if a_list else pd.DataFrame()
    
    if not k_df.empty:
        k_df['Date'] = pd.to_datetime(k_df['Date'], errors='coerce').dt.date
        # Numeric safety for RCA
        k_df['Data Volume - Total (GB)'] = pd.to_numeric(k_df['Data Volume - Total (GB)'], errors='coerce').fillna(0)
        # Pre-tag RCA Reasons
        k_df['RCA Reason'] = k_df.apply(lambda r: get_rca_reason(r, a_df, r.get('Site Id', '')), axis=1)
        
    return k_df, a_df

# --- SIDEBAR ---
with st.sidebar:
    st.header("📂 Data Sync Center")
    if st.button("🔄 Sync All Smart Data"):
        with st.spinner("Processing Cloud Data..."):
            k, a = load_data()
            if not k.empty:
                st.session_state['master_kpi'] = k.drop_duplicates()
                st.session_state['alarm_data'] = a
                st.success("Sync Complete! 🚀")
            else:
                st.error("No Data Found in Folders!")
    if st.button("🗑️ Clear Cache"):
        st.session_state.clear()
        st.rerun()

# --- MAIN PAGE: SEARCH & ANALYSIS ---
df_main = st.session_state['master_kpi']
df_alarm = st.session_state['alarm_data']

if not df_main.empty:
    col_s, col_d = st.columns(2)
    with col_s:
        search_site = st.text_input("🔍 Search Site ID:").strip().upper()
    with col_d:
        min_d, max_d = df_main['Date'].min(), df_main['Date'].max()
        dr = st.date_input("📅 Date Range Filter", [min_d, max_d])

    if search_site:
        site_data = df_main[df_main['Site Id'].str.contains(search_site, na=False)].sort_values('Date', ascending=False)
        
        if not site_data.empty:
            # 📊 TRAFFIC GRAPH
            st.subheader(f"📊 Traffic Analysis for {search_site}")
            fig = px.bar(site_data, x='Date', y='Data Volume - Total (GB)', color='Cell ID', facet_col='Band', 
                         barmode='group', height=400, text_auto='.1f',
                         color_discrete_map={"Cell 0": "#1E3A8A", "Cell 1": "#3B82F6", "Cell 2": "#EF4444"})
            fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
            st.plotly_chart(fig, use_container_width=True)

            st.divider()
            col_l, col_r = st.columns(2)
            
            with col_l:
                st.subheader("🚨 Site Status & Alarms")
                site_alarms = df_alarm[df_alarm.astype(str).apply(lambda x: x.str.contains(search_site, case=False)).any(axis=1)] if not df_alarm.empty else pd.DataFrame()
                if not site_alarms.empty:
                    st.error("Critical Issues Found!")
                    st.dataframe(site_alarms, use_container_width=True, hide_index=True)
                else:
                    st.success("No active critical alarms! ✅")

            with col_r:
                st.subheader("📉 RCA: Low Traffic Analysis (< 2GB)")
                low_traf = site_data[site_data['Data Volume - Total (GB)'] < 2.0]
                if not low_traf.empty:
                    sel_c = st.selectbox("Analyze Cell:", low_traf['4G Cell Name'].unique())
                    c_rows = site_data[site_data['4G Cell Name'] == sel_c]
                    if not c_rows.empty:
                        # Fixed RCA Access logic
                        c_row = c_rows.iloc[0]
                        st.markdown(f'<div class="rca-box">📌 RCA Diagnosis: {c_row["RCA Reason"]}</div>', unsafe_allow_html=True)
                    st.dataframe(low_traf[['Date', '4G Cell Name', 'Data Volume - Total (GB)', 'RCA Reason']], 
                                 use_container_width=True, hide_index=True)
                else:
                    st.success("All cells performing healthy! ✅")

            st.subheader("📋 Key RF KPI Records")
            show_cols = [c for c in TARGET_RF_COLS if c in site_data.columns]
            st.dataframe(site_data[show_cols], use_container_width=True, hide_index=True)

    # --- OA WISE TRACKER ---
    st.divider()
    st.subheader("🎯 OA Wise Tracker (Bellow 2GB List)")
    if 'OA' in df_main.columns:
        sel_oa = st.selectbox("🎯 Filter by OA:", ["Select Area"] + sorted(df_main['OA'].dropna().unique()))
        if sel_oa != "Select Area":
            oa_df = df_main[df_main['OA'] == sel_oa]
            latest_d = oa_df['Date'].max()
            oa_low = oa_df[(oa_df['Date'] == latest_d) & (oa_df['Data Volume - Total (GB)'] < 2.0)]
            
            if not oa_low.empty:
                st.warning(f"Found {len(oa_low)} Problem Cells in {sel_oa}")
                analyze_oa_cell = st.selectbox("👉 Click to Analyze OA Cell:", oa_low['4G Cell Name'].unique())
                if analyze_oa_cell:
                    oa_c_rows = oa_low[oa_low['4G Cell Name'] == analyze_oa_cell]
                    if not oa_c_rows.empty:
                        st.info(f"**RCA Diagnosis for {analyze_oa_cell}:** {oa_c_rows.iloc[0]['RCA Reason']}")
                st.dataframe(oa_low[['Site Id', '4G Cell Name', 'Data Volume - Total (GB)', 'RCA Reason']], use_container_width=True, hide_index=True)
            else:
                st.success(f"All cells in {sel_oa} are healthy! ✅")
else:
    st.info("👈 Please sync data from the sidebar.")
