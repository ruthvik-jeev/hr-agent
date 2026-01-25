"""
HR Agent Web UI - Streamlit Chat Interface
"""

import streamlit as st
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from dotenv import load_dotenv

load_dotenv()

from hr_agent.seed import seed_if_needed
from hr_agent.core.agent import HRAgent

# Seed database if needed
seed_if_needed()

# Page config
st.set_page_config(
    page_title="HR Agent",
    page_icon="👥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown(
    """
<style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    .user-message {
        background-color: #e3f2fd;
        border-left: 4px solid #2196f3;
    }
    .assistant-message {
        background-color: #f5f5f5;
        border-left: 4px solid #4caf50;
    }
    .sidebar-info {
        background-color: #fff3e0;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/human-resources.png", width=80)
    st.title("HR Agent")
    st.markdown("---")

    # User selection
    st.subheader("👤 Current User")

    # Get list of employees for dropdown
    import sqlite3

    conn = sqlite3.connect("hr_demo.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT email, legal_name, title, department FROM employee ORDER BY legal_name"
    )
    employees = cursor.fetchall()
    conn.close()

    employee_options = {f"{e[1]} ({e[3]})": e[0] for e in employees}

    selected_employee = st.selectbox(
        "Select Employee",
        options=list(employee_options.keys()),
        index=(
            list(employee_options.keys()).index("Alex Kim (Engineering)")
            if "Alex Kim (Engineering)" in employee_options
            else 0
        ),
    )

    current_email = employee_options[selected_employee]
    st.info(f"📧 {current_email}")

    # Get employee details
    conn = sqlite3.connect("hr_demo.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT e.legal_name, e.title, e.department, e.location, e.hire_date,
               m.legal_name as manager_name
        FROM employee e
        LEFT JOIN manager_reports mr ON mr.report_employee_id = e.employee_id
        LEFT JOIN employee m ON mr.manager_employee_id = m.employee_id
        WHERE e.email = ?
    """,
        (current_email,),
    )
    emp_details = cursor.fetchone()
    conn.close()

    if emp_details:
        st.markdown("---")
        st.subheader("📋 Employee Info")
        st.markdown(
            f"""
        - **Name:** {emp_details[0]}
        - **Title:** {emp_details[1]}
        - **Department:** {emp_details[2]}
        - **Location:** {emp_details[3]}
        - **Hire Date:** {emp_details[4]}
        - **Manager:** {emp_details[5] or 'N/A'}
        """
        )

    st.markdown("---")

    # Quick actions
    st.subheader("⚡ Quick Questions")
    quick_questions = [
        "What is my holiday balance?",
        "Who is my manager?",
        "What is my salary?",
        "Show my salary history",
        "Do I have pending holiday requests?",
        "Who is my manager's manager?",
        "What company events are coming up?",
        "What is the remote work policy?",
        "How long have I been at the company?",
        "Who are my teammates?",
    ]

    for q in quick_questions:
        if st.button(q, key=f"quick_{q}", use_container_width=True):
            st.session_state.quick_question = q

    st.markdown("---")

    # Clear chat button
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.session_state.agent = None
        st.rerun()

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if (
    "agent" not in st.session_state
    or st.session_state.get("current_email") != current_email
):
    st.session_state.agent = HRAgent(current_email)
    st.session_state.current_email = current_email
    st.session_state.messages = []  # Clear messages when user changes

# Main chat area
st.title("💬 HR Agent Chat")
st.markdown(f"*Chatting as **{selected_employee}***")
st.markdown("---")

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(
        message["role"], avatar="👤" if message["role"] == "user" else "🤖"
    ):
        st.markdown(message["content"])

# Handle quick question if selected
if "quick_question" in st.session_state:
    prompt = st.session_state.quick_question
    del st.session_state.quick_question

    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # Get agent response
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Thinking..."):
            response = st.session_state.agent.chat(prompt)
        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()

# Chat input
if prompt := st.chat_input("Ask me anything about HR..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # Get agent response
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Thinking..."):
            response = st.session_state.agent.chat(prompt)
        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})

# Footer
st.markdown("---")
st.markdown(
    """
<div style="text-align: center; color: #888; font-size: 0.8rem;">
    HR Agent Demo | Built with Streamlit | Data is for demonstration purposes only
</div>
""",
    unsafe_allow_html=True,
)
