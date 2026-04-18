"""Página de Detalle de Semestre - Vista detallada de un semestre específico."""

import streamlit as st

from src.shared import (
    init_session_state_defaults,
    get_dataset_map,
    load_data,
    apply_filters,
    render_main_metrics,
    render_totals,
    render_theory,
    render_practical,
    render_topics,
    parallel_sort_key,
)

st.set_page_config(layout="wide")


def main() -> None:
    st.title("Detalle de semestre")

    # Inicializar estado de sesión
    init_session_state_defaults()

    dataset_map = get_dataset_map()

    if not dataset_map:
        st.warning("No hay datasets disponibles. Primero genera un consolidado.")
        return

    available_semesters = sorted(dataset_map.keys(), reverse=True)
    from src.shared import get_default_semester
    default_semester = get_default_semester(dataset_map)
    default_index = available_semesters.index(default_semester) if default_semester in available_semesters else 0

    # Selector de semestre
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

    # Asegurar que el examen detail sea válido
    from src.shared.constants import EXAM_LABELS
    if "selected_exam_detail" not in st.session_state:
        st.session_state.selected_exam_detail = "1E"
    if st.session_state.selected_exam_detail not in EXAM_LABELS:
        st.session_state.selected_exam_detail = "1E"

    df = load_data(dataset_map[selected_semester])

    # Opciones de filtros
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
        st.warning("Sin datos para los filtros seleccionados.")
        return

    # Renderizar componentes
    render_main_metrics(filtered_df)
    render_totals(filtered_df)

    col1, col2 = st.columns(2)
    with col1:
        render_theory(filtered_df)
    with col2:
        render_practical(filtered_df, selected_semester)

    render_topics(filtered_df, selected_semester)


main()
