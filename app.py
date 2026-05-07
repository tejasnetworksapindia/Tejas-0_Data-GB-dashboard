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
    h3 { margin-top: 10px !important; margin-bottom: 5px !important; color: #1E3A8A; font-size: 20px !important; font-weight: bold; }
    thead tr th { background-color: #1E3A8A !important; color: white !important; font-size: 16px !important; }
    .stDataFrame { border: 1px solid #1E3A8A; border-radius: 5px; font-size: 16px !important; }
    .rca-box { 
        background-color: #EBF5FB; padding: 15px; border-radius: 8px; 
        border-left: 8px solid #1E3A8A; margin-bottom: 10px; color: #1E3A8A; font-weight: bold;
    }
    .stButton>button { width: 100%; border-radius: 5px; background-color: #1E3A8A; color: white; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="report-title">📡 Tejas RAN Smart Performance & Historical Dashboard</p>', unsafe_allow_html=True)

# Session State
if 'master_kpi' not in st.session_state: st.session_state['master_kpi'] = pd.DataFrame()
if 'alarm_data' not in st.session_state: st.session_state['alarm_data'] = pd.DataFrame()

# 2. Targeted Display Columns
TARGET_COLS = ['Date', 'Site Id', '4G Cell Name', 'Data Volume - Total (GB)', 
               'RRC Connection Success Rate(All) (%)', 'E-UTRAN Cell availability (%)']

# 3. Robust RCA Reasoning Logic
def get_rca_reason(row, alarm_df, site_id):
    try:
        avail = row.get('E-UTRAN Cell availability (%)', row.get('Cell Availability(%)', 100))
        if avail < 90: return "❌ Cell Down (Low Availability)"
        
        if not alarm_df.empty and site_id:
            site_alarms = alarm_df[alarm_df.astype(str).apply(lambda x: x.str.contains(str(site_id), case=False)).any(axis=1)]
            if not site_alarms.empty: return "🚨 Active Hardware Alarms"
        
        rrc = row.get('RRC Connection Success Rate(All) (%)', row.get('RRC Connection Success Rate(%)', 100))
        if rrc < 85: return "📉 Poor Signaling (RRC Issue)"
        
        return "⚠️ Low Footfall / Area Traffic"
    except: return "🔍 Analyzing..."

# 4. Data Loading (Stable & Fast)
def load_data():
    k_files = glob.glob("data/*.parquet") + glob.glob("data/*.csv")
    a_files = glob.glob("alarms/*")
    k_list, a_list = [], []
    
    for f in a_files:
        try:
            df_a = pd.read_parquet(f) if f.endswith('.parquet') else (pd.read_excel(f) if f.endswith('.xlsx') else pd.read_csv(f))
            df_a.columns = [c.strip() for c in df_a.columns]
            a_list.append(df_a)
        except: continue
    final_a = pd.concat(a_list, ignore_index=True) if a_list else pd.DataFrame()

    for f in k_files:
        try:
            df = pd.read_parquet(f, engine='pyarrow') if f.endswith('.parquet') else pd.read_csv(f)
            df.columns = [c.strip() for c in df.columns]
            if '4G Cell Name' in df.columns:
                df['Cell ID'] = "Cell " + df['4G Cell Name'].astype(str).str[-1]
                df['Band'] = df['4G Cell Name'].astype(str).str[:6]
            k_list.append(df)
        except: continue
    
    final_k = pd.concat(k_list, ignore_index=True) if k_list else pd.DataFrame()
    if not final_k.empty:
        final_k['Date'] = pd.to_datetime(final_k['Date'], errors='coerce').dt.date
        final_k['Data Volume - Total (GB)'] = pd.to_numeric(final_k['Data Volume - Total (GB)'], errors='coerce').fillna(0)
        final_k['RCA Reason'] = final_k.apply(lambda r: get_rca_reason(r, final_a, r.get('Site Id')), axis=1)
        
    return final_k, final_a

# --- SIDEBAR ---
with st.sidebar:
    st.header("📂 Data Controls")
    if st.button("🔄 Sync All Smart Data"):
        with st.spinner("Processing..."):
            k, a = load_data()
            if not k.empty:
                st.session_state['master_kpi'] = k.drop_duplicates()
                st.session_state['alarm_data'] = a
                st.success(f"Sync Done! ({len(k)} rows) 🚀")
            else: st.error("No Data Found!")
    if st.button("🗑️ Clear Cache"):
        st.session_state.clear()
        st.rerun()

# --- MAIN DASHBOARD ---
df_main = st.session_state['master_kpi']
df_alarm = st.session_state['alarm_data']

if not df_main.empty:
    search_site = st.text_input("🔍 Search Site ID:").strip().upper()
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
                st.subheader("📉 RCA Analysis (< 2GB)")
                low_traf = site_data[site_data['Data Volume - Total (GB)'] < 2.0]
                if not low_traf.empty:
                    sel_c = st.selectbox("Analyze Cell:", low_traf['4G Cell Name'].unique())
                    # SAFE ACCESS: Use values[0] only after checking length
                    reason_vals = low_traf[low_traf['4G Cell Name'] == sel_c]['RCA Reason'].values
                    reason = reason_vals[0] if len(reason_vals) > 0 else "Analyzing..."
                    st.markdown(f'<div class="rca-box">📌 Diagnosis: {reason}</div>', unsafe_allow_html=True)
                    st.dataframe(low_traf[['Date', '4G Cell Name', 'Data Volume - Total (GB)', 'RCA Reason']], use_container_width=True, hide_index=True)
                else: st.success("All cells performing healthy! ✅")

            st.subheader("📋 Key RF Records")
            disp = [c for c in TARGET_COLS if c in site_data.columns]
            st.dataframe(site_data[disp], use_container_width=True, hide_index=True)

else:
    st.info("👈 Sync data from sidebar to begin.")
