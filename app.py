import streamlit as st
import pandas as pd
import datetime
import json
from utils.db import init_db, save_metrics, get_metrics, get_all_weeks, get_comparison_data, save_setting, load_settings
from utils.llm import extract_metrics_from_file, generate_email
from utils.eml import parse_eml_content

# Initialize Database
init_db()

def main():
    st.set_page_config(
        page_title="CEO Brief Generator", 
        layout="wide",
        page_icon="assets/logo.png"
    )
    
    # Custom CSS for Premium UI
    st.markdown("""
        <style>
        .main {
            background-color: #f8f9fa; 
        }
        .stButton>button {
            width: 100%;
            border-radius: 5px;
            font-weight: bold;
        }
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        h1 {
            color: #1E3A8A;
        }
        h2 {
            color: #1E3A8A;
            font-size: 1.5rem;
        }
        </style>
    """, unsafe_allow_html=True)

    # Use columns to position logo next to title
    col_logo, col_title = st.columns([2, 8])
    with col_logo:
        try:
            st.image("assets/logo_header.png", width=200)
        except:
             st.write("🧊") # Fallback
    with col_title:
        st.title("CEO Brief Generator")
    
    st.markdown("Generate executive-level briefs from raw data in seconds.")

    # --- Load Persisted Settings ---
    saved_settings = load_settings()

    # Initialize Session State
    if 'gemini_api_key' not in st.session_state:
        st.session_state['gemini_api_key'] = saved_settings.get('gemini_api_key', '')
    if 'openai_api_key' not in st.session_state:
        st.session_state['openai_api_key'] = saved_settings.get('openai_api_key', '')
    if 'azure_api_key' not in st.session_state:
        st.session_state['azure_api_key'] = saved_settings.get('azure_api_key', '')
    if 'azure_endpoint' not in st.session_state:
        st.session_state['azure_endpoint'] = saved_settings.get('azure_endpoint', '')
    if 'azure_version' not in st.session_state:
        st.session_state['azure_version'] = saved_settings.get('azure_version', '2024-02-15-preview')
    if 'azure_deployment' not in st.session_state:
        st.session_state['azure_deployment'] = saved_settings.get('azure_deployment', '')
    
    # Init other state
    if 'extracted_metrics' not in st.session_state:
        st.session_state['extracted_metrics'] = None
    if 'generated_email' not in st.session_state:
        st.session_state['generated_email'] = ""
    # Init default note value if not present (allows EML overwrite)
    if 'notes_content' not in st.session_state:
        st.session_state['notes_content'] = ""

    # Default Style Reference
    default_sample = """Subject: Weekly CEO Brief - Week 42

Team,

Solid performance this week driven by [Brand A] and [Brand B]. We are seeing strong conversion in MENA despite footfall challenges.

CORE 12 PERFORMANCE:
| Brand | Sales vs BP | Margin vs BP |
|-------|-------------|--------------|
| SBX   | +5%         | +2%          |
| H&M   | -1%         | +0.5%        |
...

MARKET HIGHLIGHTS:
- KSA: Strong start to the holiday season.
- UAE: Traffic flat, conversion up.

Focus for next week is inventory consolidation.

Regards,
CEO"""

    # --- SIDEBAR: Settings & Configuration ---
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        st.subheader("🤖 AI Provider")
        # Load saved provider/model
        provider_options = ["Google Gemini", "OpenAI", "Azure OpenAI"]
        saved_provider = saved_settings.get('provider', "Google Gemini")
        default_provider_idx = provider_options.index(saved_provider) if saved_provider in provider_options else 0
        
        provider = st.radio("Select Provider", provider_options, index=default_provider_idx, label_visibility="collapsed")
        
        st.subheader("🔑 Credentials")
        
        active_api_key = ""
        model_name = None
        azure_config = None

        if provider == "Google Gemini":
            api_key_input = st.text_input("Gemini API Key", type="password", value=st.session_state['gemini_api_key'])
            if api_key_input:
                st.session_state['gemini_api_key'] = api_key_input
            active_api_key = st.session_state['gemini_api_key']
            
            gemini_models = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-3-pro-preview", "gemini-3-flash-preview"]
            saved_model = saved_settings.get('model_name', gemini_models[0])
            model_index = gemini_models.index(saved_model) if saved_model in gemini_models else 0
            
            model_name = st.selectbox("Model", gemini_models, index=model_index)
            
        elif provider == "OpenAI":
            api_key_input = st.text_input("OpenAI API Key", type="password", value=st.session_state['openai_api_key'])
            if api_key_input:
                st.session_state['openai_api_key'] = api_key_input
            active_api_key = st.session_state['openai_api_key']
            
            openai_models = ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]
            saved_model = saved_settings.get('model_name', openai_models[0])
            model_index = openai_models.index(saved_model) if saved_model in openai_models else 0
            
            model_name = st.selectbox("Model", openai_models, index=model_index)
            
        elif provider == "Azure OpenAI":
            # API Key
            api_key_input = st.text_input("Azure API Key", type="password", value=st.session_state['azure_api_key'])
            if api_key_input:
                st.session_state['azure_api_key'] = api_key_input
            active_api_key = st.session_state['azure_api_key']
            
            # Endpoint
            endpoint_input = st.text_input("Azure Endpoint", value=st.session_state['azure_endpoint'], help="https://YOUR_RESOURCE.openai.azure.com/")
            if endpoint_input:
                st.session_state['azure_endpoint'] = endpoint_input
                
            # Version
            version_input = st.text_input("API Version", value=st.session_state['azure_version'], help="e.g., 2024-02-15-preview")
            if version_input:
                 st.session_state['azure_version'] = version_input
                 
            # Deployment
            deployment_input = st.text_input("Deployment Name", value=st.session_state['azure_deployment'], help="The name of your deployed model")
            if deployment_input:
                st.session_state['azure_deployment'] = deployment_input
            
            azure_config = {
                "endpoint": st.session_state['azure_endpoint'],
                "version": st.session_state['azure_version'],
                "deployment": st.session_state['azure_deployment']
            }
            # For Azure, model_name is effectively the deployment name, used for display
            model_name = st.session_state['azure_deployment']


        with st.expander("Advanced Settings"):
            system_instruction = st.text_area("System Prompt", value=saved_settings.get('system_prompt', "You are an Executive Assistant. Be precise, professional, and data-driven."))

        if st.button("💾 Save Configuration"):
            save_setting('gemini_api_key', st.session_state['gemini_api_key'])
            save_setting('openai_api_key', st.session_state['openai_api_key'])
            
            # Save Azure settings
            save_setting('azure_api_key', st.session_state['azure_api_key'])
            save_setting('azure_endpoint', st.session_state['azure_endpoint'])
            save_setting('azure_version', st.session_state['azure_version'])
            save_setting('azure_deployment', st.session_state['azure_deployment'])

            save_setting('provider', provider)
            # Only save model_name if not Azure (since Azure uses Deployment)
            if provider != "Azure OpenAI":
                save_setting('model_name', model_name)
            
            save_setting('system_prompt', system_instruction)
            st.success("Settings Saved!")

        st.markdown("---")
        st.caption("v1.5 | AI-Powered Briefs")

    # --- Main Content ---
    # Use tabs for major functional areas
    tab1, tab2 = st.tabs(["🚀 Generator", "📊 The Vault"])

    # --- Tab 1: Generator ---
    with tab1:
        
        # Top Control Bar
        col_ctrl1, col_ctrl2 = st.columns([1, 4])
        with col_ctrl1:
            st.info(f"Target: **{datetime.date.today().strftime('%B %Y')}**")
        with col_ctrl2:
             # Week Selection
            c1, c2 = st.columns(2)
            with c1:
                week_num = st.number_input("Week #", min_value=1, max_value=53, value=datetime.date.today().isocalendar()[1])
            with c2:
                year_val = st.number_input("Year", min_value=2024, max_value=2030, value=datetime.date.today().year)
            current_week_id = f"{year_val}-W{week_num}"

        st.divider()

        # Step 1: Input Data
        col_left, col_right = st.columns([1, 1])
        
        with col_left:
            st.subheader("1️⃣ Data & Context")
            
            with st.container(border=True):
                st.markdown("**Sales & Margin Data**")
                metrics_files = st.file_uploader("Upload Image/PDF/XLSX", type=['png', 'jpg', 'jpeg', 'pdf', 'xlsx'], key="metrics", accept_multiple_files=True)
                if metrics_files:
                    st.success(f"{len(metrics_files)} files uploaded", icon="✅")
            
            with st.container(border=True):
                st.markdown("**Market Report (Context)**")
                market_files = st.file_uploader("Upload PDF", type=['pdf'], key="market", accept_multiple_files=True)
                if market_files:
                    st.info(f"{len(market_files)} reports attached", icon="📎")
            
            st.subheader("2️⃣ The Voice")
            with st.container(border=True):
                st.markdown("**CEO Notes / Intro**")
                eml_notes = st.file_uploader("Import from Email (.eml)", type=['eml'], key="eml_notes")
                if eml_notes:
                    parsed_body = parse_eml_content(eml_notes.getvalue())
                    st.session_state['notes_content'] = parsed_body
                    st.info("Notes imported from email!", icon="📧")
                
                notes = st.text_area("Edit Notes", value=st.session_state['notes_content'], height=150, placeholder="E.g., Great work on inventory management this week...")
                # Sync back manually if edited
                st.session_state['notes_content'] = notes

        with col_right:
            st.subheader("3️⃣ Style & Output")
            
            # Load saved style or default
            style_content = saved_settings.get('style_reference', default_sample)
            
            # Allow EML import for style
            eml_style = st.file_uploader("Import Style from Email (.eml)", type=['eml'], key="eml_style")
            if eml_style:
                parsed_style = parse_eml_content(eml_style.getvalue())
                style_content = parsed_style
                st.info("Style imported from email!", icon="📧")

            with st.expander("📝 Edit Style Reference (Default)", expanded=False):
                sample_text = st.text_area("Sample Output", value=style_content, height=300)
                if st.button("💾 Save as Default Style"):
                    save_setting('style_reference', sample_text)
                    st.success("Style Template Saved!")

            st.markdown("###") # Spacer
            generate_btn = st.button("✨ Generate Brief", type="primary", use_container_width=True)

        # Generation Logic
        if generate_btn:
            if not active_api_key:
                st.toast("Please configure API Key in the Sidebar!", icon="⚠️")
            elif not metrics_files:
                st.toast("Please upload at least one Sales & Margin data file.", icon="⚠️")
            else:
                try:
                    with st.status("🚀 Processing...", expanded=True) as status:
                        
                        # 1. Parsing Metrics from Multiple Files
                        status.write("Analyzing Sales Data...")
                        all_metrics_data = {}
                        
                        for idx, m_file in enumerate(metrics_files):
                            status.write(f"Reading file {idx+1}/{len(metrics_files)}...")
                            bytes_data = m_file.getvalue()
                            file_type = m_file.type
                            
                            # Update extraction call to include Azure config
                            metrics_json_str = extract_metrics_from_file(
                                bytes_data, 
                                file_type, 
                                active_api_key, 
                                provider, 
                                model_name,
                                azure_config=azure_config
                            )
                            metrics_json_str = metrics_json_str.replace("```json", "").replace("```", "").strip()
                            
                            try:
                                file_metrics = json.loads(metrics_json_str)
                                all_metrics_data.update(file_metrics)
                            except json.JSONDecodeError as e:
                                st.warning(f"Could not parse JSON from file {m_file.name}")
                        
                        st.session_state['extracted_metrics'] = all_metrics_data
                        
                        status.write(f"Metrics Extracted: found {len(all_metrics_data)} brands total.")
                        
                        # Save to DB
                        save_metrics(current_week_id, all_metrics_data)
                        
                        # 2. Context from Multiple Files
                        status.write("Reading Context...")
                        market_text_context = ""
                        if market_files:
                            market_text_context = f"Context provided in {len(market_files)} attached Market Report files. "
                        else:
                            market_text_context = "No specific market report attached."

                        # 3. Generating
                        status.write("Drafting Email...")
                        # Update generation call to include Azure config
                        final_email = generate_email(
                            notes, 
                            json.dumps(all_metrics_data), 
                            market_text_context, 
                            sample_text, 
                            active_api_key, 
                            provider, 
                            model_name, 
                            system_instruction,
                            azure_config=azure_config
                        )
                        st.session_state['generated_email'] = final_email
                        
                        status.update(label="Brief Generated Successfully!", state="complete", expanded=False)
                        
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")

        # Output Display
        if st.session_state['generated_email']:
            st.divider()
            st.subheader("📨 Final Brief")
            
            with st.expander("🔍 Debug: Extracted Data"):
                st.json(st.session_state['extracted_metrics'])
                
            st.text_area("Copy your brief here:", value=st.session_state['generated_email'], height=500)


    # --- Tab 2: The Vault ---
    with tab2:
        st.subheader("📊 Performance Comparison")
        
        available_weeks = get_all_weeks()
        
        if len(available_weeks) < 2:
            st.info("ℹ️ Need at least two weeks of data to compare. Generate briefs for different weeks to populate.")
        else:
            with st.container(border=True):
                col1, col2, col3 = st.columns([1, 1, 1])
                with col1:
                    week_baseline = st.selectbox("Baseline Week", available_weeks, index=1 if len(available_weeks)>1 else 0)
                with col2:
                    week_current = st.selectbox("Current Week", available_weeks, index=0)
                with col_3:
                    st.write("") # Spacer
                    st.write("") # Spacer
                    compare = st.toggle("Show Comparison", value=True)

            if compare:
                df_comp = get_comparison_data(week_baseline, week_current)
                if not df_comp.empty:
                    # Identify sales and margin columns for formatting
                    sales_cols = [c for c in df_comp.columns if 'Sales' in c]
                    margin_cols = [c for c in df_comp.columns if 'Margin' in c]
                    
                    st.dataframe(
                        df_comp,
                        use_container_width=True,
                        column_config={
                            "brand": "Brand",
                            **{c: st.column_config.TextColumn(c) for c in df_comp.columns if c != "brand"} 
                        },
                        hide_index=True
                    )
                    
                    st.caption("Green/Red highlighting is conceptual in standard dataframe view. For full color logic, we can apply style:")
                    
                    # Apply simple styling again
                    st.dataframe(
                        df_comp.style.applymap(
                            lambda x: 'color: green; font-weight: bold' if isinstance(x, str) and '+' in x 
                            else ('color: red; font-weight: bold' if isinstance(x, str) and '-' in x else ''), 
                            subset=pd.IndexSlice[:, pd.IndexSlice[df_comp.columns.str.contains("Sales|Margin")]]
                        ),
                        use_container_width=True
                    )

                else:
                    st.warning("No data found for selected weeks.")

if __name__ == "__main__":
    main()
