import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io

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

# 3. Helper Function - ✅ CSV FILES కోసం పక్కాగా మార్చాను మామా
def fetch_from_drive(file_id):
    if not file_id: return None
    
    # CSV ఫైల్స్ ని డైరెక్ట్ గా డౌన్‌లోడ్ చేయడానికి వాడే కరెక్ట్ URL ఫార్మాట్ ఇది:
    url = f"https://google.com{file_id.strip()}"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            # CSV కాబట్టి read_csv వాడాలి
            return pd.read_csv(io.BytesIO(response.content))
        else:
            st.error(f"Download Error (ID: {file_id}): Drive permissions 'Anyone with the link' లో ఉన్నాయో లేదో చూడు మామా!")
    except Exception as e:
        st.error(f"Fetch Error: {e}")
    return None

# --- SIDEBAR: DATA MANAGEMENT ---
with st.sidebar:
    st.header("📂 Data Management")
    
    # మామా, నీ CSV ఫైల్ ఐడిలు ఇక్కడ ఉన్నాయి
    FIXED_KPI_IDS = [
        "1wvh8AAWhuj_ZDkiHKhIKU0YiFtf8CoJS",
        "1o1a7QX47BGUlwZ1Vm6DrDhM1Uh62wVPB",
        "10KzzznYIUHitWMSEnKG2KoQnySkoPnQG",
        "136xNGW0_EghLz8sGw8AGJPVnp5y9rR0L"
    ]

    st.subheader("📅 KPI Auto-Sync")
    if st.button("🔄 Sync Fixed 4-Day KPI"):
        all_dfs = []
        with st.spinner("CSV ఫైల్స్ క్లౌడ్ నుండి తెస్తున్నాను..."):
            for f_id in FIXED_KPI_IDS:
                df = fetch_from_drive(f_id)
                if df is not None:
                    all_dfs.append(df)
            if all_dfs:
                combined = pd.concat(all_dfs, ignore_index=True)
                # డేట్ ఫార్మాట్ సెట్ చేద్దాం
                if 'Date' in combined.columns:
                    combined['Date'] = pd.to_datetime(combined['Date']).dt.date
                st.session_state['master_kpi'] = combined.drop_duplicates()
                st.success("CSV Data Loaded Successfully! 🚀")

    st.divider()
    if st.button("🗑️ Clear Dashboard"):
        st.session_state['master_kpi'] = pd.DataFrame()
        st.rerun()

# --- MAIN PAGE: SEARCH & FILTERS ---
df_main = st.session_state['master_kpi']

col_search, col_date = st.columns(2)

with col_search:
    search_site = st.text_input("🔍 Search Site ID (e.g., AT2001)", "").strip().upper()

with col_date:
    if not df_main.empty:
        min_d = df_main['Date'].min()
        max_d = df_main['Date'].max()
        date_range = st.date_input("📅 Date Range Filter", [min_d, max_d])
    else:
        st.info("Sync data to enable Date Filter")
        date_range = []

# --- ANALYSIS SECTION ---
if search_site and not df_main.empty:
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
        kpi_cols = ['Date', '4G Cell Name', 'CSSR', 'RRC Connection Success Rate(All) (%)', 'ERAB Drop Rate - PS (%)']
        available_cols = [c for c in kpi_cols if c in site_data.columns]
        st.dataframe(site_data[available_cols].sort_values(by='Date', ascending=False), use_container_width=True)
    else:
        st.warning(f"No records found for Site: {search_site}")

# --- BOTTOM SECTION: OA TRACKER ---
st.divider()
st.markdown("### 🔍 Low Traffic Cell Tracker (OA Wise)")
if not df_main.empty:
    if 'OA' in df_main.columns:
        oa_list = sorted(df_main['OA'].dropna().unique())
        selected_oa = st.selectbox("🎯 Filter by Operational Area (OA):", ["Select Area"] + oa_list)
        latest_date = df_main['Date'].max()
        df_latest = df_main[df_main['Date'] == latest_date]
        if selected_oa != "Select Area":
            df_filtered_oa = df_latest[df_latest['OA'] == selected_oa]
            # Data volume 2GB కంటే తక్కువ ఉన్నవి చూపిద్దాం
            low_cells = df_filtered_oa[df_filtered_oa['Data Volume - Total (GB)'] < 2.0]
            if not low_cells.empty:
                st.warning(f"⚠️ {len(low_cells)} cells below 2GB on {latest_date}")
                st.dataframe(low_cells[['Site Id', 'LOCATION', '4G Cell Name', 'Data Volume - Total (GB)']], use_container_width=True)
            else:
                st.success(f"✅ All cells in {selected_oa} are above 2GB.")
else:
    st.info("👈 గూగుల్ డ్రైవ్ లో ఉన్న CSV డేటా కోసం పైన ఉన్న 'Sync' బటన్ నొక్కు మామా!")
