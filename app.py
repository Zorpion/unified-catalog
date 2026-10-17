import os
import streamlit as st
from databricks.sdk import WorkspaceClient

# Page configuration
st.set_page_config(
    page_title="Unified Data Catalog",
    page_icon="🛡️",
    layout="wide"
)

# Initialize session state for connection handling
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.workspace_url = ""
    st.session_state.client = None

# --- SCREEN 1: LOGIN WIZARD ---
if not st.session_state.authenticated:
    st.title("🛡️ Unified Data Catalog")
    st.markdown("### Enterprise Metadata Explorer")
    st.write("Connect securely to your Databricks workspace.")
    
    st.markdown("---")
    
    with st.form("sso_login_form"):
        workspace_url = st.text_input(
            "Databricks Workspace URL",
            placeholder="https://adb-xxxx.azuredatabricks.net"
        )
        
        # Optional token or client ID/Secret for cloud deployments if browser auth isn't local
        auth_mode = st.radio("Authentication Method", ["Local / Browser SSO", "Databricks Personal Access Token (PAT)"])
        
        token = ""
        if auth_mode == "Databricks Personal Access Token (PAT)":
            token = st.text_input("Databricks Token", type="password", placeholder="dapi...")
            
        submitted = st.form_submit_button("🔐 Connect to Workspace")
        
        if submitted:
            if workspace_url:
                clean_url = workspace_url.strip().rstrip("/")
                
                with st.spinner("Connecting to Databricks..."):
                    try:
                        if auth_mode == "Databricks Personal Access Token (PAT)" and token:
                            w = WorkspaceClient(host=clean_url, token=token)
                        else:
                            # Default fallback for local browser or default credential chain
                            w = WorkspaceClient(host=clean_url, auth_type="external-browser")
                        
                        # Test connection
                        list(w.catalogs.list())
                        
                        st.session_state.authenticated = True
                        st.session_state.workspace_url = clean_url
                        st.session_state.client = w
                        
                        st.success("Successfully authenticated!")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Authentication failed: {e}")
            else:
                st.warning("Please enter your Databricks workspace URL first.")
                
    st.markdown("Status: 🔴 **Not Signed In**")

# --- SCREEN 2: MAIN METADATA DASHBOARD ---
else:
    col1, col2 = st.columns([8, 2])
    with col1:
        st.title("🛡️ Unified Data Catalog")
    with col2:
        if st.button("Sign Out"):
            st.session_state.authenticated = False
            st.session_state.workspace_url = ""
            st.session_state.client = None
            st.rerun()

    st.success(f"🟢 Connected to Databricks: `{st.session_state.workspace_url}`")
    st.markdown("---")

    search_query = st.text_input("🔍 Search tables, schemas, or catalogs...", "")

    st.subheader("Unity Catalog Assets (Metadata-Only)")

    with st.spinner("Fetching catalog metadata..."):
        try:
            w = st.session_state.client
            catalogs = list(w.catalogs.list())
            
            st.metric(label="Total Catalogs Discovered", value=len(catalogs))
            
            for cat in catalogs:
                with st.expander(f"📁 Catalog: {cat.name}"):
                    try:
                        schemas = list(w.schemas.list(catalog_name=cat.name))
                        for sch in schemas:
                            st.markdown(f"**📂 Schema:** `{sch.name}`")
                            
                            tables = list(w.tables.list(catalog_name=cat.name, schema_name=sch.name))
                            if tables:
                                table_list = []
                                for tbl in tables:
                                    if search_query.lower() in tbl.name.lower():
                                        table_list.append({
                                            "Table Name": tbl.name,
                                            "Type": tbl.table_type,
                                            "Owner": tbl.owner or "Not Assigned"
                                        })
                                if table_list:
                                    st.dataframe(table_list, use_container_width=True)
                            else:
                                st.text("   (No tables in this schema)")
                    except Exception as schema_err:
                        st.warning(f"Could not load schemas for {cat.name}: {schema_err}")
                        
        except Exception as e:
            st.error(f"Error communicating with Databricks API: {e}")