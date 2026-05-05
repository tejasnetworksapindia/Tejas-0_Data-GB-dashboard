import streamlit as st
import pandas as pd
import plotly.express as px

# Webpage setup
st.set_page_config(layout="wide", page_title="Tejas Traffic Analyzer")

# Custom Styling
st.markdown("""
    <style>
    .report-title { font-size:28px !important; font-weight: bold; color: #1E3A8A; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="report-title">📡 RAN Network Performance Dashboard</p>', unsafe_allow_html=True)

# --- NEW STORAGE LOGIC ---
if 'master_kpi' not in st.session_state:
    st.session_state['master_kpi'] = pd.DataFrame()

# Helper function to read multiple files (CSV or Excel)
def load_and_combine_data(uploaded_files):
    all_data = []
    if uploaded_files:
        for file in uploaded_files:
            try:
                if file.name.endswith('.csv'):
                    df = pd.read_csv(file)
                else:
                    df = pd.read_excel(file)
                all_data.append(df)
            except Exception as e:
                st.error(f"Error loading {file.name}: {e}")
        if all_data:
            return pd.concat(all_data, ignore_index=True)
    return None

# Helper function for single file reading
def load_single_file(uploaded_file):
    if uploaded_file is not None:
        try:
            return pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"Error loading {uploaded_file.name}: {e}")
    return None

# --- SIDEBAR: Upload Section ---
with st.sidebar:
    st.header("📂 Data Management")
    file_kpi_list = st.file_uploader("1. KPI Reports (Upload New Days)", type=['xlsx', 'csv'], accept_multiple_files=True)
    
    # 🟢 SAVE BUTTON: Database loki save cheyataniki
    if st.button("💾 Save & Refresh Database"):
        if file_kpi_list:
            new_data = load_and_combine_data(file_kpi_list)
            # Patha data tho combine chesthunnam
            combined = pd.concat([st.session_state['master_kpi'], new_data], ignore_index=True)
            
            # Last 4 Days logic: Dates batti filter chestham
            if not combined.empty and 'Date' in combined.columns:
                combined['Date'] = combined['Date'].astype(str)
                unique_dates = sorted(combined['Date'].unique(), reverse=True)[:4]
                combined = combined[combined['Date'].isin(unique_dates)]
            
            st.session_state['master_kpi'] = combined.drop_duplicates()
            st.success("Data Saved! Kept last 4 days trends.")

    if st.button("🗑️ Clear All Storage"):
        st.session_state['master_kpi'] = pd.DataFrame()
        st.rerun()

    st.divider()
    file_alarm = st.file_uploader("2. Active Alarm Report", type=['xlsx', 'csv'])
    file_fm = st.file_uploader("3. FM Report", type=['xlsx', 'csv'])
    file_vswr = st.file_uploader("4. VSWR Alarm Report", type=['xlsx', 'csv'])

# --- SEARCH BAR ---
search_site = st.text_input("🔍 Search Site ID (e.g., AT2001)", "").strip()

# Check stored data first
df_kpi = st.session_state['master_kpi']

if search_site and not df_kpi.empty:
    # Smart Search logic
    df_kpi['Site Id'] = df_kpi['Site Id'].astype(str)
    site_data = df_kpi[df_kpi['Site Id'].str.contains(search_site, case=False, na=False)]

    if not site_data.empty:
        # --- 1. TRAFFIC SECTION (50%) ---
        st.subheader(f"📊 4-Day Traffic Trend: {search_site}")
        
        site_data = site_data.sort_values(by='Date')
        fig_traffic = px.bar(
            site_data, 
            x='4G Cell Name', 
            y='Data Volume - Total (GB)', 
            color='Date',
            barmode='group',
            height=450,
            text_auto='.2f'
        )
        st.plotly_chart(fig_traffic, use_container_width=True)

        st.divider()

        # --- 2. BOTTOM SECTION (KPI & ALARMS) ---
        col_kpi, col_alarm = st.columns(2)
        
        with col_kpi:
            st.subheader("📉 RF KPI Parameters")
            kpi_cols = ['Date', '4G Cell Name', 'CSSR', 'RRC Connection Success Rate(All) (%)', 'ERAB Drop Rate - PS (%)']
            available_cols = [c for c in kpi_cols if c in site_data.columns]
            st.dataframe(site_data[available_cols].sort_values(by='Date', ascending=False), use_container_width=True)

        with col_alarm:
            st.subheader("⚠️ HW Alarms & Faults (Combined)")
            combined_alarms = []
            for label, f in [("Active", file_alarm), ("FM", file_fm), ("VSWR", file_vswr)]:
                df = load_single_file(f)
                if df is not None:
                    site_al = df[df.astype(str).apply(lambda x: x.str.contains(search_site, case=False, na=False)).any(axis=1)].copy()
                    if not site_al.empty:
                        site_al['Source'] = label
                        combined_alarms.append(site_al)
            
            if combined_alarms:
                st.dataframe(pd.concat(combined_alarms, ignore_index=True), use_container_width=True)
            else:
                st.success(f"No active alarms found for {search_site}! ✅")
    else:
        st.error(f"Site ID {search_site} not found in database!")
else:
    if search_site:
        st.info("👈 Database is empty. Please upload files and click 'Save & Refresh Database'.")
    else:
        st.warning("🔍 Please enter a Site ID to see the flow.")
