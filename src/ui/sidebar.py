import streamlit as st

from config import DATASETS_PATH
from src.io.dataset_loader import list_available_datasets
from src.state.session import init_session_state

def render_sidebar() -> None:
    init_session_state()

    with st.sidebar:
        st.header("Dashboard FP")

        mode = st.radio(
            "Modo",
            options=["Histórico", "Semestre específico"],
            index=0 if st.session_state.selected_mode == "Histórico" else 1,
        )
        st.session_state.selected_mode = mode

        st.subheader("Datasets disponibles")
        datasets = list_available_datasets(DATASETS_PATH)

        if datasets:
            st.caption(f"{len(datasets)} dataset(s) encontrado(s)")
            for dataset_name in datasets:
                st.write(f"• {dataset_name}")
        else:
            st.caption("No hay datasets consolidados todavía.")

        st.subheader("Estado")
        st.write(f"Modo activo: {st.session_state.selected_mode}")
        current_name = st.session_state.current_dataset_name or "Ninguno"
        st.write(f"Dataset actual: {current_name}")
