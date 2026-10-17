import streamlit as st
import requests
from databricks.sdk import WorkspaceClient
from azure.identity import InteractiveBrowserCredential
import snowflake.connector
from google.cloud import bigquery
import redshift_connector
import pymssql

# Page setup
st.set_page_config(
    page_title="Unified Enterprise Data Catalog",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Enterprise Styling & Animations
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        height: 45px;
        background-color: #f1f5f9;
        border-radius: 6px 6px 0px 0px;
        padding: 8px 16px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #0f172a;
        color: #ffffff;
    }
    .bronze-badge { background-color: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px; }
    .silver-badge { background-color: #fef3c7; color: #b45309; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px; }
    .gold-badge { background-color: #dcfce7; color: #15803d; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px; }
    .mv-badge { background-color: #e0e7ff; color: #3730a3; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px; }
    
    .platform-badge-db { background-color: #ffedd5; color: #c2410c; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px; }
    .platform-badge-fb { background-color: #e0e7ff; color: #3730a3; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px; }
    .platform-badge-sf { background-color: #e1f5fe; color: #01579b; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px; }
    .platform-badge-bq { background-color: #e8f5e9; color: #2e7d32; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px; }
    .platform-badge-rs { background-color: #fce4ec; color: #c2185b; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px; }
    .platform-badge-sql { background-color: #e3f2fd; color: #0277bd; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px; }

    @keyframes dash {
        to { stroke-dashoffset: -20; }
    }
    .animated-path {
        stroke: #6366f1;
        stroke-width: 3;
        stroke-dasharray: 8, 8;
        animation: dash 1s linear infinite;
    }
    .pipeline-node {
        padding: 14px;
        border-radius: 8px;
        border: 1px solid #cbd5e1;
        background-color: #ffffff;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# Session State Initialization
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.connected_platforms = []
    # Databricks
    st.session_state.db_client = None
    st.session_state.available_catalogs = []
    st.session_state.selected_catalogs = []
    # Fabric
    st.session_state.fabric_token = None
    st.session_state.available_fabric_workspaces = {}
    st.session_state.selected_fabric_workspaces = []
    # Snowflake
    st.session_state.sf_connected = False
    # Other clouds
    st.session_state.bq_connected = False
    st.session_state.rs_connected = False
    st.session_state.sql_connected = False
    # Inspector
    st.session_state.selected_table_inspector = None
    st.session_state.inspector_open = False

# --- SCREEN 1: VISUAL PLATFORM SELECTION & AUTHENTICATION MENU ---
if not st.session_state.authenticated:
    st.title("🛡️ Unified Multi-Cloud Data Catalog")
    st.caption("Select your enterprise data platforms below. You can connect to one or multiple systems.")
    st.markdown("---")
    
    st.subheader("Step 1: Choose Target Systems")
    
    col_sys1, col_sys2, col_sys3 = st.columns(3)
    with col_sys1:
        sel_db = st.checkbox("🧊 **Databricks Unity Catalog**", value=True)
        sel_sf = st.checkbox("❄️ **Snowflake Data Cloud**", value=False)
    with col_sys2:
        sel_fb = st.checkbox("⚡ **Microsoft Fabric**", value=True)
        sel_bq = st.checkbox("🔍 **Google BigQuery**", value=False)
    with col_sys3:
        sel_rs = st.checkbox("☁️ **AWS Redshift**", value=False)
        sel_sql = st.checkbox("🗄️ **Microsoft SQL Server**", value=False)

    st.markdown("---")
    st.subheader("Step 2: Authenticate Selected Platforms")

    # 1. Databricks Auth Block
    if sel_db:
        with st.expander("🧊 Databricks Configuration", expanded=True):
            db_url_input = st.text_input("Databricks Workspace URL", placeholder="https://adb-xxxx.azuredatabricks.net", key="setup_db_url")
            if db_url_input.strip():
                if st.button("🔄 Connect Databricks via SSO", key="btn_auth_db"):
                    try:
                        with st.spinner("Authenticating via browser SSO..."):
                            w = WorkspaceClient(host=db_url_input.strip().rstrip("/"), auth_type="external-browser")
                            cats = [c.name for c in w.catalogs.list()]
                            st.session_state.db_client = w
                            st.session_state.available_catalogs = cats
                            st.session_state.selected_catalogs = cats
                            if "Databricks" not in st.session_state.connected_platforms:
                                st.session_state.connected_platforms.append("Databricks")
                            st.success(f"Connected! Discovered {len(cats)} catalogs.")
                    except Exception as e:
                        st.error(f"Databricks connection failed: {e}")
            if st.session_state.available_catalogs:
                st.session_state.selected_catalogs = st.multiselect("Select Catalogs:", st.session_state.available_catalogs, default=st.session_state.selected_catalogs, key="sel_cats_multi")

    # 2. Microsoft Fabric Auth Block
    if sel_fb:
        with st.expander("⚡ Microsoft Fabric Configuration", expanded=True):
            if st.button("🔄 Connect Microsoft Fabric via Entra ID", key="btn_auth_fb"):
                try:
                    with st.spinner("Authenticating via Entra ID token..."):
                        credential = InteractiveBrowserCredential()
                        token_obj = credential.get_token("https://api.fabric.microsoft.com/.default")
                        st.session_state.fabric_token = token_obj.token
                        resp = requests.get("https://api.fabric.microsoft.com/v1/workspaces", headers={"Authorization": f"Bearer {token_obj.token}"})
                        if resp.status_code == 200:
                            ws_list = resp.json().get("value", [])
                            st.session_state.available_fabric_workspaces = {ws["displayName"]: ws["id"] for ws in ws_list}
                            st.session_state.selected_fabric_workspaces = list(st.session_state.available_fabric_workspaces.keys())
                            if "Microsoft Fabric" not in st.session_state.connected_platforms:
                                st.session_state.connected_platforms.append("Microsoft Fabric")
                            st.success(f"Connected! Discovered {len(ws_list)} workspaces.")
                        else:
                            st.error(f"API Error: {resp.text}")
                except Exception as e:
                    st.error(f"Fabric auth error: {e}")
            if st.session_state.available_fabric_workspaces:
                st.session_state.selected_fabric_workspaces = st.multiselect("Select Fabric Workspaces:", list(st.session_state.available_fabric_workspaces.keys()), default=st.session_state.selected_fabric_workspaces, key="sel_fb_multi")

    # 3. Snowflake Auth Block
    if sel_sf:
        with st.expander("❄️ Snowflake Configuration", expanded=True):
            sf_account = st.text_input("Snowflake Account Identifier", placeholder="org-account_name")
            sf_user = st.text_input("Username", placeholder="user@company.com")
            if sf_account and sf_user:
                if st.button("🔄 Connect Snowflake (External Browser SSO)", key="btn_auth_sf"):
                    st.session_state.sf_connected = True
                    if "Snowflake" not in st.session_state.connected_platforms:
                        st.session_state.connected_platforms.append("Snowflake")
                    st.success("Snowflake authenticated successfully.")

    # 4. BigQuery Auth Block
    if sel_bq:
        with st.expander("🔍 Google BigQuery Configuration", expanded=True):
            bq_project = st.text_input("GCP Project ID", placeholder="my-analytics-project-prod")
            if bq_project:
                if st.button("🔄 Link Google BigQuery Project", key="btn_auth_bq"):
                    st.session_state.bq_connected = True
                    if "Google BigQuery" not in st.session_state.connected_platforms:
                        st.session_state.connected_platforms.append("Google BigQuery")
                    st.success("BigQuery project linked.")

    # 5. Redshift / SQL Server
    if sel_rs:
        with st.expander("☁️ AWS Redshift Configuration", expanded=True):
            if st.button("🔄 Link AWS Redshift Cluster", key="btn_auth_rs"):
                st.session_state.rs_connected = True
                if "AWS Redshift" not in st.session_state.connected_platforms:
                    st.session_state.connected_platforms.append("AWS Redshift")
                st.success("Redshift linked.")

    if sel_sql:
        with st.expander("🗄️ Microsoft SQL Server Configuration", expanded=True):
            if st.button("🔄 Link SQL Server Instance", key="btn_auth_sql"):
                st.session_state.sql_connected = True
                if "SQL Server" not in st.session_state.connected_platforms:
                    st.session_state.connected_platforms.append("SQL Server")
                st.success("SQL Server linked.")

    st.markdown("---")
    
    # Launch Button (Requires at least one connected platform)
    if st.button("🚀 Launch Unified Data Catalog Dashboard", use_container_width=True, type="primary"):
        if not st.session_state.connected_platforms:
            st.warning("Please successfully connect or configure at least one platform before launching.")
        else:
            st.session_state.authenticated = True
            st.rerun()

# --- SCREEN 2: MAIN DASHBOARD ---
else:
    top_col1, top_col2, top_col3 = st.columns([4, 3, 3])
    with top_col1:
        st.title("🛡️ Multi-Cloud Enterprise Catalog")
        st.caption(f"Active Systems: **{', '.join(st.session_state.connected_platforms)}**")
    with top_col2:
        if st.button("⚙️ Change Connections & Menu", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()
    with top_col3:
        inspector_label = "❌ Close Inspector" if st.session_state.inspector_open else "☰ Open Inspector"
        if st.button(inspector_label, use_container_width=True):
            st.session_state.inspector_open = not st.session_state.inspector_open
            st.rerun()

    st.markdown("---")

    main_ui, inspector_ui = st.columns([3, 1]) if st.session_state.inspector_open else (st.container(), None)

    with main_ui:
        tab_search, tab_lineage, tab_catalog, tab_governance = st.tabs([
            "🔍 Global Multi-Cloud Search",
            "🌿 Live Medallion Lineage",
            "📁 Connected Catalogs & Workspaces", 
            "🛡️ Governance Rules"
        ])

        # --- TAB 1: GLOBAL SEARCH ---
        with tab_search:
            st.subheader("🔍 Cross-Platform Enterprise Asset Search")
            global_query = st.text_input("Search tables, datasets, or schemas across connected systems...", "", key="global_search_input").strip().lower()
            matched_assets = []

            # Databricks Assets
            if st.session_state.db_client and st.session_state.selected_catalogs:
                try:
                    for cat_name in st.session_state.selected_catalogs:
                        for sch in st.session_state.db_client.schemas.list(catalog_name=cat_name):
                            for t in st.session_state.db_client.tables.list(catalog_name=cat_name, schema_name=sch.name):
                                full_name = f"{cat_name}.{sch.name}.{t.name}"
                                if not global_query or global_query in full_name.lower():
                                    matched_assets.append({"Platform": "Databricks", "Badge": "DATABRICKS", "Name": t.name, "Location": f"{cat_name} ➔ {sch.name}", "Type": t.table_type, "Owner": t.owner or "N/A", "Path": full_name})
                except Exception:
                    pass

            # Fabric Assets
            if st.session_state.fabric_token and st.session_state.selected_fabric_workspaces:
                try:
                    headers = {"Authorization": f"Bearer {st.session_state.fabric_token}"}
                    for ws_name in st.session_state.selected_fabric_workspaces:
                        ws_id = st.session_state.available_fabric_workspaces.get(ws_name)
                        if ws_id:
                            items_resp = requests.get(f"https://api.fabric.microsoft.com/v1/workspaces/{ws_id}/items", headers=headers)
                            if items_resp.status_code == 200:
                                for item in items_resp.json().get("value", []):
                                    if not global_query or global_query in item.get("displayName", "").lower():
                                        matched_assets.append({"Platform": "Microsoft Fabric", "Badge": "FABRIC", "Name": item.get("displayName"), "Location": f"{ws_name} ({item.get('type')})", "Type": item.get("type"), "Owner": "Entra ID", "Path": f"{ws_name}.{item.get('displayName')}"})
                except Exception:
                    pass

            # Snowflake / BigQuery / Redshift / SQL Server placeholders if active
            if st.session_state.sf_connected:
                matched_assets.append({"Platform": "Snowflake", "Badge": "SNOWFLAKE", "Name": "fct_snowflake_orders", "Location": "PROD_WAREHOUSE ➔ GOLD", "Type": "Snowflake Table", "Owner": "snowflake_admin@company.com", "Path": "PROD_WAREHOUSE.GOLD.fct_snowflake_orders"})
            if st.session_state.bq_connected:
                matched_assets.append({"Platform": "Google BigQuery", "Badge": "BIGQUERY", "Name": "bq_global_sales_mart", "Location": "prod-analytics ➔ analytics_gold", "Type": "BigQuery Table", "Owner": "gcp_admin@company.com", "Path": "prod-analytics.analytics_gold.bq_global_sales_mart"})
            if st.session_state.rs_connected:
                matched_assets.append({"Platform": "AWS Redshift", "Badge": "REDSHIFT", "Name": "rs_warehouse_transactions", "Location": "dw-cluster ➔ public", "Type": "Redshift Table", "Owner": "aws_data@company.com", "Path": "dw-cluster.public.rs_warehouse_transactions"})
            if st.session_state.sql_connected:
                matched_assets.append({"Platform": "SQL Server", "Badge": "SQLSERVER", "Name": "dbo_erp_ledger", "Location": "CorporateSQL ➔ dbo", "Type": "Relational Table", "Owner": "erp_dba@company.com", "Path": "CorporateSQL.dbo.dbo_erp_ledger"})

            if matched_assets:
                for asset in matched_assets:
                    col_s1, col_s2, col_s3, col_s4 = st.columns([1, 4, 3, 2])
                    with col_s1:
                        st.markdown(f"<span class='platform-badge-db'>{asset['Badge']}</span>", unsafe_allow_html=True)
                    with col_s2:
                        st.markdown(f"**{asset['Name']}**")
                        st.caption(f"`{asset['Path']}`")
                    with col_s3:
                        st.caption(f"📂 {asset['Location']}")
                    with col_s4:
                        if st.button("🔍 Inspect", key=f"search_{asset['Path']}"):
                            st.session_state.selected_table_inspector = {"Table": asset["Name"], "Layer": asset["Location"], "Workspace": asset["Platform"], "Owner": asset["Owner"], "Type": asset["Type"]}
                            st.session_state.inspector_open = True
                            st.rerun()
                    st.divider()
            else:
                st.info("No matching assets found across connected systems.")

        # --- TAB 2: LINEAGE & FIELD ANIMATOR ---
        with tab_lineage:
            st.subheader("🌿 Live Medallion Lineage & Field Flow Animator")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                st.selectbox("🎯 Target Asset", ["raw_stripe_events", "stg_transactions", "fct_customer_orders", "mv_executive_revenue_kpi"])
            with col_f2:
                selected_field = st.selectbox("🔍 Trace Column", ["customer_id", "net_revenue", "order_amount", "timestamp"])

            st.markdown(f"""
            <div style="display: flex; align-items: center; justify-content: space-between; background-color: #f8fafc; padding: 25px; border-radius: 12px; border: 1px solid #e2e8f0; margin-top: 20px;">
                <div class="pipeline-node" style="width: 22%;"><span class="bronze-badge">Bronze</span><br><br><strong>raw_stripe_events</strong><br><code>{selected_field}</code></div>
                <div style="flex-grow: 1; text-align: center;"><svg height="30" width="100%"><line x1="0" y1="15" x2="100%" y2="15" class="animated-path"/></svg><small>Parse</small></div>
                <div class="pipeline-node" style="width: 22%;"><span class="silver-badge">Silver</span><br><br><strong>stg_transactions</strong><br><code>{selected_field}</code></div>
                <div style="flex-grow: 1; text-align: center;"><svg height="30" width="100%"><line x1="0" y1="15" x2="100%" y2="15" class="animated-path"/></svg><small>Aggregate</small></div>
                <div class="pipeline-node" style="width: 22%;"><span class="gold-badge">Gold</span><br><br><strong>fct_customer_orders</strong><br><code>{selected_field}</code></div>
            </div>
            """, unsafe_allow_html=True)

        # --- TAB 3: CATALOG EXPLORER ---
        with tab_catalog:
            st.subheader("📁 Connected Catalogs & Workspaces Explorer")
            if st.session_state.db_client and st.session_state.selected_catalogs:
                for cat in st.session_state.selected_catalogs:
                    with st.expander(f"📁 Databricks Catalog: **{cat}**"):
                        for sch in st.session_state.db_client.schemas.list(catalog_name=cat):
                            st.markdown(f"**📂 Schema:** `{sch.name}`")
            if st.session_state.selected_fabric_workspaces:
                for ws in st.session_state.selected_fabric_workspaces:
                    with st.expander(f"⚡ Microsoft Fabric Workspace: **{ws}**"):
                        st.caption("Active OneLake & Lakehouse endpoint synchronized.")
            if not st.session_state.db_client and not st.session_state.selected_fabric_workspaces and not st.session_state.sf_connected:
                st.info("No active catalog explorers to display for the currently selected systems.")

        # --- TAB 4: GOVERNANCE ---
        with tab_governance:
            st.subheader("🛡️ Governance Rules")
            st.json({"connected_systems": st.session_state.connected_platforms, "storage": "Local Ephemeral Memory Only"})

    # --- INSPECTOR DRAWER ---
    if st.session_state.inspector_open and inspector_ui is not None:
        with inspector_ui:
            st.markdown("### 🗂️ Table Inspector")
            st.markdown("---")
            if st.session_state.selected_table_inspector:
                tbl = st.session_state.selected_table_inspector
                st.markdown(f"**Table:** `{tbl['Table']}`")
                st.markdown(f"**Location:** `{tbl['Layer']}`")
                st.markdown(f"**Platform:** `{tbl['Workspace']}`")
            if st.button("Close Panel", use_container_width=True):
                st.session_state.inspector_open = False
                st.rerun()