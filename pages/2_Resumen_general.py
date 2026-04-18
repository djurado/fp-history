"""Página de Resumen General - Vista de un semestre específico."""

import streamlit as st

from src.shared import (
    init_session_state_defaults,
    get_dataset_map,
    load_data,
    apply_filters,
    render_sidebar_single_semester,
    render_main_metrics,
    build_state_distribution_df,
    render_state_distribution_chart,
    render_state_distribution_table,
    render_sit_distribution,
    render_students_by_career_and_state,
    render_approved_percentage_by_career,
)

st.set_page_config(layout="wide", initial_sidebar_state="expanded")


def main() -> None:
    st.title("Resumen general")

    init_session_state_defaults()

    dataset_map = get_dataset_map()

    if not dataset_map:
        st.warning("No hay datasets disponibles. Primero genera un consolidado para un semestre.")
        st.stop()

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
        st.warning("No hay datos para los filtros seleccionados.")
        st.stop()

    with st.expander("📊 Indicadores", expanded=False):
        render_main_metrics(filtered_df, f"Indicadores del semestre: {selected_semester}")
    
    
    state_counts, state_percent, state_df_plot = build_state_distribution_df(filtered_df)
    col_left, col_right = st.columns(2)
    with col_left:
        render_state_distribution_chart(state_df_plot)
    with col_right:
        render_sit_distribution(filtered_df)
    render_state_distribution_table(state_counts, state_percent)
    
    with st.expander("📊 Análisis por carrera", expanded=True):
        col_left, col_right = st.columns(2)
        with col_left:
            career_order = render_students_by_career_and_state(
                filtered_df, 
                st.session_state.career_sort_order
            )
        with col_right:
            render_approved_percentage_by_career(
                filtered_df, 
                career_order, 
                st.session_state.career_sort_order
            )

main()