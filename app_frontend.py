import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="MaintAI Cloud Dashboard", page_icon="⚙️", layout="wide")

API_BASE_URL = "http://localhost:8000/api/v1"

st.title("⚙️ MaintAI Cloud — Multi-Factory Management")

# Sidebar Authentication
st.sidebar.header("🔐 Authentication")
email = st.sidebar.text_input("Admin Email", value="admin3@ensam.ma")
password = st.sidebar.text_input("Password", type="password", value="password123")

if "token" not in st.session_state:
    st.session_state["token"] = None

if st.sidebar.button("Log In"):
    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/login",
            data={"username": email, "password": password}
        )
        if response.status_code == 200:
            st.session_state["token"] = response.json()["access_token"]
            st.sidebar.success("Logged in successfully!")
        else:
            st.sidebar.error("Invalid credentials.")
    except Exception as e:
        st.sidebar.error(f"Could not connect to API: {e}")

if st.session_state["token"]:
    headers = {"Authorization": f"Bearer {st.session_state['token']}"}
    
    # Navigation Tabs
    tab1, tab2 = st.tabs(["🚨 Live Alert Stream", "🏭 Machine Management"])
    
    # TAB 1: Live Alerts
    with tab1:
        @st.fragment(run_every=3)
        def render_live_alerts():
            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader("Real-Time Telemetry & Failure Alerts")
                try:
                    alerts_res = requests.get(f"{API_BASE_URL}/alerts", headers=headers)
                    if alerts_res.status_code == 200:
                        alerts_data = alerts_res.json()
                        if alerts_data:
                            df = pd.DataFrame(alerts_data)
                            if 'risk_score' in df.columns:
                                df['risk_confidence'] = (df['risk_score'] * 100).map('{:.1f}%'.format)
                            st.dataframe(df, use_container_width=True)
                        else:
                            st.info("No active failure alerts. Monitored machinery operating normally.")
                except Exception as e:
                    st.error(f"Error fetching alerts: {e}")

            with col2:
                st.subheader("System Status")
                st.metric(label="API Backend", value="Online 🟢")
                st.metric(label="Celery Engine", value="Active ⚡")
                st.caption("🔄 Auto-polling alerts every 3 seconds...")

        render_live_alerts()

    # TAB 2: Machine Management
    with tab2:
        st.subheader("➕ Register New Equipment")
        with st.form("add_machine_form"):
            new_machine_name = st.text_input("Machine Name", placeholder="e.g. Robot Arm Alpha")
            submit_button = st.form_submit_button("Register Machine")
            
            if submit_button:
                if new_machine_name.strip():
                    res = requests.post(
                        f"{API_BASE_URL}/machines",
                        headers=headers,
                        json={"name": new_machine_name}
                    )
                    if res.status_code in [200, 201]:
                        machine_data = res.json()
                        st.success(f"Machine '{new_machine_name}' registered!")
                        st.code(f"API Key: {machine_data.get('api_key')}", language="text")
                        st.info("Copy this API key into simulator/stream_simulator.py to start streaming data.")
                    else:
                        st.error(f"Failed to register machine: {res.text}")
                else:
                    st.warning("Please enter a valid machine name.")
else:
    st.warning("Please log in from the sidebar to access factory controls and monitoring.")
