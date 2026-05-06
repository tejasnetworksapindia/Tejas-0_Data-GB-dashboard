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

# 3. Helper Function - GitHub ఫోల్డర్ నుండి డేటా రీడ్ చేయడానికి
def load_data_from_github():
    data_path = 'data' # నీ GitHub లోని ఫోల్డర్ పేరు
    all_files = glob.glob(os.path.join(data_path, "*.csv"))
    
    if not all_files:
        st.error("Maama, 'data' folder lo CSV files emi dorakaledu! GitHub lo upload chesavo ledo chudu.")
        return pd.DataFrame()
    
    df_list = []
    progress_bar = st.progress(0)
    total_files = len(all_files)
    
    for i, filename in enumerate(all_files):
        # Progress update
        progress_bar.progress((i + 1) / total_files)
        # Reading CSV
        df = pd.read_csv(filename)
        df_list.append(df)
        
    combined_df = pd.concat(df_list, ignore_index=True)
    return combined_df

# --- SIDEBAR: DATA MANAGEMENT ---
with st.sidebar:
    st.header("📂 Data Management")
    st.subheader("📅 GitHub Repository Sync")
    
    if st.button("🔄 Sync All Data (1 Month)"):
        with st.spinner("GitHub నుండి భారీ డేటాని లోడ్ చేస్తున్నాను... ఓపిక పట్టు మామా!"):
            df = load_data_from_github()
            if not df.empty:
                # Date column handling
                if 'Date' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date']).dt.date
                st.session_state['master_kpi'] = df.drop_duplicates()
                st.success(f"Loaded {len(st.session_state['master_kpi'])} records! 🚀")

    st.divider()
    if st.button("🗑️ Clear Dashboard"):
        st.session_state['master_kpi'] = pd.DataFrame()
        st.rerun()

# --- MAIN PAGE: SEARCH & FILTERS ---
df_main = st.session_state['master_kpi']

if not df_main.empty:
    col_search, col_date = st.columns(2)

    with col_search:
        search_site = st.text_input("🔍 Search Site ID (e.g., AT2001)", "").strip().upper()

    with col_date:
        min_d = df_main['Date'].min()
        max_d = df_main['Date'].max()
        date_range = st.date_input("📅 Date Range Filter", [min_d, max_d])

    # --- ANALYSIS SECTION ---
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

            st.divider()
            st.subheader("📉 RF KPI Parameters")
            # Nuvvu adigina columns ikkada unnayi
            kpi_cols = ['Date', '4G Cell Name', 'CSSR', 'RRC Connection Success Rate(All) (%)', 'ERAB Drop Rate - PS (%)']
            available_cols = [c for c in kpi_cols if c in site_data.columns]
            st.dataframe(site_data[available_cols].sort_values(by='Date', ascending=False), use_container_width=True)
        else:
            st.warning("Site data dorakaledu maama!")

    # --- OA TRACKER ---
    st.divider()
    st.markdown("### 🔍 Low Traffic Cell Tracker (OA Wise)")
    if 'OA' in df_main.columns:
        oa_list = sorted(df_main['OA'].dropna().unique())
        selected_oa = st.selectbox("🎯 Operational Area (OA):", ["Select Area"] + oa_list)
        latest_date = df_main['Date'].max()
        df_latest = df_main[df_main['Date'] == latest_date]
        if selected_oa != "Select Area":
            df_filtered_oa = df_latest[df_latest['OA'] == selected_oa]
            low_cells = df_filtered_oa[df_filtered_oa['Data Volume - Total (GB)'] < 2.0]
            if not low_cells.empty:
                st.warning(f"⚠️ {len(low_cells)} cells below 2GB")
                st.dataframe(low_cells[['Site Id', 'LOCATION', 'Data Volume - Total (GB)']], use_container_width=True)
            else:
                st.success(f"✅ All cells in {selected_oa} are above 2GB.")
else:
    st.info("👈 ఎడమవైపు ఉన్న 'Sync' బటన్ నొక్కు మామా, GitHub లో ఉన్న 1 నెల డేటా అంతా ఇక్కడికి వచ్చేస్తుంది!")
