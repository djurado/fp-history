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
    parallel_sort_key,
)

st.set_page_config(layout="wide", initial_sidebar_state="expanded")


def main() -> None:
    st.title("Resumen general")

    # Inicializar estado de sesión
    init_session_state_defaults()

    dataset_map = get_dataset_map()

    if not dataset_map:
        st.warning("No hay datasets disponibles. Primero genera un consolidado para un semestre.")
        st.stop()

    # Cargar datos del semestre seleccionado
    available_semesters = sorted(dataset_map.keys(), reverse=True)
    from src.shared import get_default_semester
    default_semester = get_default_semester(dataset_map)
    
    # Obtener el índice del semestre por defecto
    default_index = available_semesters.index(default_semester) if default_semester in available_semesters else 0

    # Selector de semestre en la barra lateral
    with st.sidebar:
        st.header("Filtros")
        selected_semester = st.selectbox(
            "Semestre",
            options=available_semesters,
            index=default_index,
        )
        selected_year_str, selected_term_str = selected_semester.split("-")
        st.session_state.selected_year = int(selected_year_str)
        st.session_state.selected_term = int(selected_term_str)

    df = load_data(dataset_map[selected_semester]).copy()

    # Obtener opciones de filtros
    career_options = (
        sorted(df["CARRERA"].dropna().astype(str).unique().tolist())
        if "CARRERA" in df.columns
        else []
    )
    sit_options = (
        sorted(df["SIT"].dropna().unique().tolist())
        if "SIT" in df.columns
        else []
    )
    state_options = (
        sorted(df["ESTADO"].dropna().astype(str).unique().tolist())
        if "ESTADO" in df.columns
        else []
    )
    parallel_options = (
        sorted(df["PARALELO"].dropna().astype(str).unique().tolist(), key=parallel_sort_key)
        if "PARALELO" in df.columns
        else []
    )

    # Filtros en sidebar
    with st.sidebar:
        selected_careers = st.multiselect("Carrera", options=career_options)
        selected_sit = st.multiselect("Veces tomada (SIT)", options=sit_options)
        selected_states = st.multiselect("Estado", options=state_options)
        selected_parallels = st.multiselect("Paralelo", options=parallel_options)

    # Aplicar filtros
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

    # Renderizar componentes siempre en expanders
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