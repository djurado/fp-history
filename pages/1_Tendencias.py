"""Página de Tendencias - Vista histórica de múltiples semestres."""

import streamlit as st

from src.shared import (
    init_session_state_defaults,
    load_historical_data,
    apply_historical_filters,
    render_sidebar_historical,
    render_historical_main_metrics,
    build_historical_state_distribution,
    render_historical_state_chart,
    render_historical_student_counts_chart,
    render_historical_state_table,
)

st.set_page_config(layout="wide")


def main() -> None:
    st.title("Análisis histórico")

    # Inicializar estado de sesión
    init_session_state_defaults()

    historical_df = load_historical_data()

    if historical_df.empty:
        st.warning("No hay datasets históricos disponibles. Primero genera consolidados en datasets/.")
        st.stop()

    # Renderizar sidebar y obtener filtros
    semester_range, selected_faculties, selected_careers, selected_sit = render_sidebar_historical(historical_df)

    # Aplicar filtros
    filtered_df = apply_historical_filters(
        df=historical_df,
        semester_range=semester_range,
        selected_faculties=selected_faculties,
        selected_careers=selected_careers,
        selected_sit=selected_sit,
    )

    if filtered_df.empty:
        st.warning("No hay datos para los filtros seleccionados.")
        st.stop()

    # Renderizar indicadores siempre en expander
    with st.expander("📊 Indicadores", expanded=False):
        render_historical_main_metrics(filtered_df)
    
    grouped = build_historical_state_distribution(filtered_df)
    render_historical_state_chart(grouped)
    render_historical_student_counts_chart(grouped)
    render_historical_state_table(grouped)


main()
