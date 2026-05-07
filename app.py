import streamlit as st
import pandas as pd
import plotly.express as px
import glob
import os

# 1. Page Config & Professional Styling
st.set_page_config(layout="wide", page_title="Tejas Smart RAN Dashboard")

st.markdown("""
    <style>
    .report-title { font-size:30px !important; font-weight: bold; color: #1E3A8A; margin-bottom: -15px; }
    thead tr th { background-color: #1E3A8A !important; color: white !important; font-size: 16px !important; }
    .stDataFrame { border: 1px solid #1E3A8A; border-radius: 5px; font-size: 16px !important; }
    .rca-box { background-color: #EBF5FB; padding: 15px; border-radius: 8px; border-left: 8px solid #1E3A8A; color: #1E3A8A; font-weight: bold; }
    .stButton>button { width: 100%; border-radius: 5px; background-color: #1E3A8A; color: white; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="report-title">📡 Tejas RAN Smart Performance & Historical Dashboard</p>', unsafe_allow_html=True)

# Session State
if 'master_kpi' not in st.session_state: st.session_state['master_kpi'] = pd.DataFrame()
if 'alarm_data' not in st.session_state: st.session_state['alarm_data'] = pd.DataFrame()

# 2. Targeted Columns (Nee file headers batti update chesa maama)
TARGET_RF_COLS = [
    'Date', 'Site Id', '4G Cell Name', 'Data Volume - Total (GB)', 
    'RRC Connection Success Rate(All) (%)', 'E-UTRAN Cell availability (%)', 'OA'
]

# 3. Helper for RCA Reasoning Logic
def get_rca_reason(row, alarm_df, site_id):
    try:
        # File lo unna names batti check chesthundhi
        avail = row.get('E-UTRAN Cell availability (%)', 100)
        if avail < 90: return "❌ Cell Down (Low Availability)"
        
        if not alarm_df.empty and site_id:
            site_alarms = alarm_df[alarm_df.astype(str).apply(lambda x: x.str.contains(str(site_id), case=False)).any(axis=1)]
            if not site_alarms.empty: return "🚨 Active Hardware Alarms"
        
        rrc = row.get('RRC Connection Success Rate(All) (%)', 100)
        if rrc < 85: return "📉 Poor Signaling (RRC Issue)"
        
        return "⚠️ Low Footfall / Area Traffic"
    except: return "🔍 Analyzing..."

# 4. Data Loading
def load_data():
    k_files = glob.glob("data/*.parquet") + glob.glob("data/*.csv")
    a_files = glob.glob("alarms/*")
    k_list, a_list = [], []
    
    for f in k_files:
        try:
            df = pd.read_parquet(f, engine='pyarrow') if f.endswith('.parquet') else pd.read_csv(f)
            # Column Names clean up (Spaces removal)
            df.columns = [c.strip() for c in df.columns]
            
            if '4G Cell Name' in df.columns:
                df['Cell ID'] = "Cell " + df['4G Cell Name'].astype(str).str[-1]
                df['Band'] = df['4G Cell Name'].astype(str).str[:6]
            k_list.append(df)
        except Exception as e: st.sidebar.error(f"Error KPI {os.path.basename(f)}: {e}")
        
    for f in a_files:
        try:
            df = pd.read_parquet(f) if f.endswith('.parquet') else (pd.read_excel(f) if f.endswith('.xlsx') else pd.read_csv(f))
            df.columns = [c.strip() for c in df.columns]
            a_list.append(df)
        except: continue
    
    k_df = pd.concat(k_list, ignore_index=True) if k_list else pd.DataFrame()
    a_df = pd.concat(a_list, ignore_index=True) if a_list else pd.DataFrame()
    
    if not k_df.empty:
        k_df['Date'] = pd.to_datetime(k_df['Date'], errors='coerce').dt.date
        k_df['Data Volume - Total (GB)'] = pd.to_numeric(k_df['Data Volume - Total (GB)'], errors='coerce').fillna(0)
        # Pre-tag RCA Reasons
        k_df['RCA Reason'] = k_df.apply(lambda r: get_rca_reason(r, a_df, r.get('Site Id')), axis=1)
        
    return k_df, a_df

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
            else: st.error("Sync Failed! Check folders.")
    if st.button("🗑️ Clear Cache"):
        st.session_state.clear()
        st.rerun()

# --- MAIN DASHBOARD ---
df_main = st.session_state['master_kpi']
df_alarm = st.session_state['alarm_data']

if not df_main.empty:
    search_site = st.text_input("🔍 Search Site ID (e.g., AT2001):").strip().upper()
    if search_site:
        site_data = df_main[df_main['Site Id'].astype(str).str.contains(search_site, na=False)].sort_values('Date', ascending=False)
        
        if not site_data.empty:
            # 📊 TRAFFIC GRAPH
            st.subheader(f"📊 Traffic Analysis for {search_site}")
            fig = px.bar(site_data, x='Date', y='Data Volume - Total (GB)', color='Cell ID', facet_col='Band', 
                         barmode='group', height=400, text_auto='.1f',
                         color_discrete_map={"Cell 0": "#1E3A8A", "Cell 1": "#3B82F6", "Cell 2": "#EF4444"})
            st.plotly_chart(fig, use_container_width=True)

            col_l, col_r = st.columns(2)
            with col_l:
                st.subheader("🚨 Site Alarms")
                site_alarms = df_alarm[df_alarm.astype(str).apply(lambda x: x.str.contains(search_site, case=False)).any(axis=1)] if not df_alarm.empty else pd.DataFrame()
                st.dataframe(site_alarms, use_container_width=True, hide_index=True)

            with col_r:
                st.subheader("📉 RCA Analysis (< 2GB)")
                low_traf = site_data[site_data['Data Volume - Total (GB)'] < 2.0]
                if not low_traf.empty:
                    sel_c = st.selectbox("Analyze Cell:", low_traf['4G Cell Name'].unique())
                    c_rows = site_data[site_data['4G Cell Name'] == sel_c]
                    if not c_rows.empty:
                        st.markdown(f'<div class="rca-box">📌 Diagnosis: {c_rows.iloc[0]["RCA Reason"]}</div>', unsafe_allow_html=True)
                    st.dataframe(low_traf[['Date', '4G Cell Name', 'Data Volume - Total (GB)', 'RCA Reason']], use_container_width=True, hide_index=True)

            st.subheader("📋 Key RF Records")
            disp_cols = [c for c in TARGET_RF_COLS if c in site_data.columns]
            st.dataframe(site_data[disp_cols], use_container_width=True, hide_index=True)

    # --- OA WISE TRACKER ---
    st.divider()
    st.subheader("🎯 OA Wise Tracker (Bellow 2GB List)")
    if 'OA' in df_main.columns:
        sel_oa = st.selectbox("🎯 Filter Area (OA):", ["Select Area"] + sorted(df_main['OA'].dropna().unique()))
        if sel_oa != "Select Area":
            oa_df = df_main[df_main['OA'] == sel_oa]
            latest_d = oa_df['Date'].max()
            oa_low = oa_df[(oa_df['Date'] == latest_d) & (oa_df['Data Volume - Total (GB)'] < 2.0)]
            if not oa_low.empty:
                analyze_oa_cell = st.selectbox("👉 Click to Analyze OA Cell:", oa_low['4G Cell Name'].unique())
                if analyze_oa_cell:
                    oa_c = oa_low[oa_low['4G Cell Name'] == analyze_oa_cell]
                    st.info(f"**Diagnosis for {analyze_oa_cell}:** {oa_c.iloc[0]['RCA Reason']}")
                st.dataframe(oa_low[['Site Id', '4G Cell Name', 'Data Volume - Total (GB)', 'RCA Reason']], use_container_width=True, hide_index=True)
else:
    st.info("👈 Please sync data to begin.")
