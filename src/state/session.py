import streamlit as st

DEFAULT_SESSION_VALUES = {
    "selected_year": None,
    "selected_term": None,
    "selected_mode": "Histórico",
    "validation_summary": [],
    "validation_details": [],
    "validation_results": [],
    "current_dataset_name": None,
    "active_filters": {},
}

def init_session_state() -> None:
    for key, value in DEFAULT_SESSION_VALUES.items():
        if key not in st.session_state:
            st.session_state[key] = value
