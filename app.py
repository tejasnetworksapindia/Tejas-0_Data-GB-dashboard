import streamlit as st
import pandas as pd
import plotly.express as px
import glob
import os

# 1. PAGE CONFIGURATION & ADVANCED STYLING
st.set_page_config(layout="wide", page_title="Tejas Smart RAN Dashboard")

st.markdown("""
    <style>
    .report-title { font-size:32px !important; font-weight: bold; color: #1E3A8A; text-align: center; margin-bottom: 20px; }
    /* Table font size and row padding for BIG LETTERS */
    .stDataFrame div[data-testid="stTable"] { font-size: 18px !important; }
    .stMetric { background-color: #f1f3f9; border-radius: 10px; padding: 15px; border: 1px solid #1E3A8A; }
    .rca-card { background-color: #ffffff; padding: 20px; border-radius: 15px; border-left: 8px solid #ff4b4b; box-shadow: 2px 2px 10px rgba(0,0,0,0.1); }
    .status-card { border-radius: 10px; padding: 15px; margin: 10px 0; color: white; text-align: center; font-weight: bold; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #1E3A8A; color: white; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="report-title">📡 Tejas RAN Smart Performance & Historical Dashboard</p>', unsafe_allow_html=True)

# 2. SESSION STATE MANAGEMENT
if 'master_kpi' not in st.session_state: st.session_state['master_kpi'] = pd.DataFrame()
if 'alarm_data' not in st.session_state: st.session_state['alarm_data'] = pd.DataFrame()

# 3. TARGETED COLUMNS FOR CLEAN UI
TARGET_COLS = [
    'Date', 'Site Id', '4G Cell Name', 'Data Volume - Total (GB)',
    'RRC Connection Success Rate(%)', 'ERAB Setup Success Rate(%)',
    'RRC Connection Max Users', 'Cell Availability(%)', 'OA'
]

# 4. SMART DATA LOADING (PARQUET + CSV + EXCEL)
def load_data():
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

# --- SIDEBAR: DATA CONTROLS ---
with st.sidebar:
    st.header("📂 Data Sync Center")
    if st.button("🔄 Sync Parquet & Cloud Data"):
        with st.spinner("Analyzing Records..."):
            k, a = load_data()
            if not k.empty and 'Date' in k.columns:
                k['Date'] = pd.to_datetime(k['Date']).dt.date
            st.session_state['master_kpi'] = k.drop_duplicates()
            st.session_state['alarm_data'] = a
            st.success(f"Sync Done! Records: {len(k)}")

    st.divider()
    if st.button("🗑️ Clear Dashboard Cache"):
        st.session_state['master_kpi'] = pd.DataFrame()
        st.session_state['alarm_data'] = pd.DataFrame()
        st.rerun()

# --- MAIN PAGE LOGIC ---
df_main = st.session_state['master_kpi']
df_alarm = st.session_state['alarm_data']

if not df_main.empty:
    # 5. KEY PERFORMANCE TABLE (Filtered & Big Fonts)
    st.subheader("📋 Performance Overview (Key Traffic Metrics)")
    display_cols = [c for c in TARGET_COLS if c in df_main.columns]
    st.dataframe(df_main[display_cols].sort_values('Date', ascending=False), use_container_width=True, height=350)

    st.divider()

    # 6. SITE SEARCH & STATUS CARDS
    col_s, col_d = st.columns([2, 2])
    with col_s:
        search_site = st.text_input("🔍 Search Site ID (e.g., AT2001):").strip().upper()
    with col_d:
        min_d, max_d = df_main['Date'].min(), df_main['Date'].max()
        dr = st.date_input("📅 Date Range Filter", [min_d, max_d])

    if search_site:
        mask = df_main['Site Id'].str.contains(search_site, na=False)
        if isinstance(dr, (list, tuple)) and len(dr) == 2:
            mask &= (df_main['Date'] >= dr[0]) & (df_main['Date'] <= dr[1])
        
        site_data = df_main[mask].sort_values(['Date', 'Band', 'Cell ID'])

        if not site_data.empty:
            # LIVE STATUS CARDS
            st.subheader(f"⚡ Live Status: {search_site}")
            cell_unique = sorted(site_data['Cell ID'].unique())
            status_cols = st.columns(len(cell_unique))
            
            for i, cell in enumerate(cell_unique):
                has_alarm = False
                if not df_alarm.empty:
                    has_alarm = df_alarm.astype(str).apply(lambda x: x.str.contains(search_site, case=False)).any(axis=1).any()
                
                s_color = "#EF4444" if has_alarm else "#10B981"
                s_text = "DOWN / ALARM" if has_alarm else "ACTIVE / HEALTHY"
                status_cols[i].markdown(f'<div class="status-card" style="background-color: {s_color};">{cell}<br><span style="font-size: 0.8em;">{s_text}</span></div>', unsafe_allow_html=True)

            # 7. TRAFFIC GRAPH (MANDATORY)
            st.subheader(f"📈 Traffic Analysis for {search_site}")
            fig = px.bar(site_data, x='Date', y='Data Volume - Total (GB)', color='Cell ID', 
                         facet_col='Band', barmode='group', height=500, text_auto='.1f',
                         color_discrete_map={"Cell 0": "#1E3A8A", "Cell 1": "#3B82F6", "Cell 2": "#EF4444"})
            fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
            st.plotly_chart(fig, use_container_width=True)

            # 8. SMART RCA INVESTIGATION (< 2GB)
            st.divider()
            st.subheader("📉 Investigation: Why Traffic is Low?")
            low_traf_df = site_data[site_data['Data Volume - Total (GB)'] < 2.0]
            
            if not low_traf_df.empty:
                sel_cell = st.selectbox("Select Low Traffic Cell to Analyze:", low_traf_df['4G Cell Name'].unique())
                c_info = site_data[site_data['4G Cell Name'] == sel_cell].iloc[-1]
                
                r1, r2 = st.columns(2)
                with r1:
                    st.metric("Total Traffic (GB)", f"{c_info['Data Volume - Total (GB)']} GB")
                    st.metric("RRC Success Rate", f"{c_info.get('RRC Connection Success Rate(%)', 0)}%")
                    st.metric("Cell Availability", f"{c_info.get('Cell Availability(%)', 0)}%")
                
                with r2:
                    st.markdown('<div class="rca-card">', unsafe_allow_html=True)
                    st.markdown("### 💡 Root Cause (RCA)")
                    if c_info.get('Cell Availability(%)', 100) < 95:
                        st.error("❌ ISSUE: Cell was DOWN/Partially Available.")
                    elif not df_alarm.empty and df_alarm.astype(str).apply(lambda x: x.str.contains(search_site, case=False)).any(axis=1).any():
                        st.error("❌ ISSUE: Active Hardware Alarms detected!")
                    elif c_info.get('RRC Connection Success Rate(%)', 100) < 85:
                        st.warning("⚠️ ISSUE: Signaling Failures (Poor RRC).")
                    else:
                        st.info("ℹ️ ISSUE: Low Footfall / Area Usage.")
                    st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.warning("No data found for this site.")

    # 9. OA WISE TRACKER (Advanced Analytics)
    st.divider()
    st.subheader("🎯 OA Wise Latest Tracker")
    if 'OA' in df_main.columns:
        oa_list = sorted(df_main['OA'].dropna().unique())
        sel_oa = st.selectbox("Filter Area (OA):", ["All Areas"] + oa_list)
        if sel_oa != "All Areas":
            oa_df = df_main[df_main['OA'] == sel_oa]
            latest_d = oa_df['Date'].max()
            low_cells = oa_df[(oa_df['Date'] == latest_d) & (oa_df['Data Volume - Total (GB)'] < 2.0)]
            if not low_cells.empty:
                st.error(f"⚠️ {len(low_cells)} cells below 2GB in {sel_oa} on {latest_d}")
                st.dataframe(low_cells[['Site Id', '4G Cell Name', 'Data Volume - Total (GB)']], use_container_width=True)
            else:
                st.success(f"All cells in {sel_oa} are Healthy! ✅")
else:
    st.info("👈 Please sync data from the sidebar to begin analysis.")
