"""Página de Detalle de Semestre - Vista detallada de un semestre específico."""

import streamlit as st

from src.shared import (
    init_session_state_defaults,
    get_dataset_map,
    load_data,
    apply_filters,
    render_sidebar_single_semester,
    render_main_metrics,
    render_totals,
    render_theory,
    render_practical,
    render_topics,
)

st.set_page_config(layout="wide", initial_sidebar_state="expanded")


def main() -> None:
    st.title("Detalle de semestre")

    init_session_state_defaults()
    
    dataset_map = get_dataset_map()

    if not dataset_map:
        st.warning("No hay datasets disponibles. Primero genera un consolidado.")
        return

    from src.shared.constants import EXAM_LABELS
    if "selected_exam_detail" not in st.session_state:
        st.session_state.selected_exam_detail = "1E"
    if st.session_state.selected_exam_detail not in EXAM_LABELS:
        st.session_state.selected_exam_detail = "1E"

    from src.shared.utils import get_default_semester
    default_semester = get_default_semester(dataset_map)
    default_year, default_term = default_semester.split("-")
    st.session_state.selected_year = int(default_year)
    st.session_state.selected_term = int(default_term)
    
    df = load_data(dataset_map[default_semester])
    
    selected_semester, selected_careers, selected_sit, selected_states, selected_parallels = render_sidebar_single_semester(
        dataset_map, df
    )

    filtered_df = apply_filters(
        df=df,
        carreras=selected_careers,
        sit=selected_sit,
        estados=selected_states,
        paralelos=selected_parallels,
    )

    if filtered_df.empty:
        st.warning("Sin datos para los filtros seleccionados.")
        return

    with st.expander("📊 Indicadores", expanded=False):
        render_main_metrics(filtered_df, f"Indicadores del semestre: {selected_semester}")
    render_totals(filtered_df)
    col1, col2 = st.columns(2)
    with col1:
        render_practical(filtered_df, selected_semester)
    with col2:
        render_theory(filtered_df)
    render_topics(filtered_df, selected_semester)


main()
