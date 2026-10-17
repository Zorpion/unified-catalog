import streamlit as st
from databricks.sdk import WorkspaceClient

# Page configuration
st.set_page_config(
    page_title="Unified Data Catalog",
    page_icon="🛡️",
    layout="wide"
)

# Initialize session state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.workspace_url = ""
    st.session_state.client = None

# --- SCREEN 1: ENTERPRISE SSO LOGIN ---
if not st.session_state.authenticated:
    st.title("🛡️ Unified Data Catalog")
    st.markdown("### Enterprise Metadata Explorer (Zero-Trust & Local-First)")
    st.info("🔒 **Enterprise Security Notice:** This application uses OAuth 2.0 PKCE via your corporate Single Sign-On (SSO). No credentials or data leave your device.")
    
    st.markdown("---")
    
    with st.form("sso_login_form"):
        workspace_url = st.text_input(
            "Databricks Workspace URL",
            placeholder="https://adb-xxxx.azuredatabricks.net"
        )
        
        submitted = st.form_submit_button("🔐 Sign in with Corporate SSO")
        
        if submitted:
            if workspace_url:
                clean_url = workspace_url.strip().rstrip("/")
                
                with st.spinner("Opening browser for Corporate SSO authentication..."):
                    try:
                        # Enterprise-grade OAuth PKCE flow (Browser-based SSO)
                        w = WorkspaceClient(
                            host=clean_url,
                            auth_type="external-browser"
                        )
                        
                        # Verify access by reading catalog metadata only
                        list(w.catalogs.list())
                        
                        st.session_state.authenticated = True
                        st.session_state.workspace_url = clean_url
                        st.session_state.client = w
                        
                        st.success("Authenticated successfully via Corporate IdP!")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Authentication failed: {e}")
                        st.caption("Ensure you are running this app locally on your machine so the SSO browser redirect to `localhost` can complete successfully.")
            else:
                st.warning("Please enter your Databricks workspace URL.")

# --- SCREEN 2: METADATA CATALOG DASHBOARD ---
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

    st.success(f"🟢 Active Session: `{st.session_state.workspace_url}`")
    st.markdown("---")

    search_query = st.text_input("🔍 Search catalogs, schemas, or tables...", "")

    st.subheader("Unity Catalog Metadata")

    with st.spinner("Loading metadata..."):
        try:
            w = st.session_state.client
            catalogs = list(w.catalogs.list())
            
            st.metric(label="Total Catalogs", value=len(catalogs))
            
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
                                            "Owner": tbl.owner or "Unassigned"
                                        })
                                if table_list:
                                    st.dataframe(table_list, use_container_width=True)
                            else:
                                st.text("   (No tables in schema)")
                    except Exception as schema_err:
                        st.warning(f"Could not read schema metadata for {cat.name}: {schema_err}")
                        
        except Exception as e:
            st.error(f"Metadata read error: {e}")