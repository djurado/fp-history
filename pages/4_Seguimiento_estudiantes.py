"""Página de Seguimiento de Estudiantes."""

import streamlit as st

from src.shared import (
    build_students_table,
    filter_students_table,
    init_session_state_defaults,
    load_historical_data,
    render_student_career_filter,
    render_student_history,
    render_student_table_filters,
    render_students_selector,
    validate_student_tracking_data,
)

st.set_page_config(layout="wide", initial_sidebar_state="expanded")


def main() -> None:
    st.title("Seguimiento de estudiantes")
    st.caption("Evolución histórica de estudiantes.")

    init_session_state_defaults()
    historical_df = load_historical_data()

    if historical_df.empty:
        st.warning("No hay datasets históricos disponibles. Primero genera consolidados en datasets/.")
        st.stop()

    missing_columns = validate_student_tracking_data(historical_df)
    if missing_columns:
        st.error(
            "El dataset histórico no contiene las columnas mínimas para seguimiento "
            f"({', '.join(missing_columns)})."
        )
        st.stop()

    if historical_df["CARRERA"].dropna().empty:
        st.warning("No hay carreras disponibles en el histórico.")
        st.stop()

    selected_career = render_student_career_filter(historical_df)
    students_table = build_students_table(historical_df, selected_career)

    if students_table.empty:
        st.info("No se encontraron estudiantes para los filtros seleccionados.")
        st.stop()

    selected_attempts, search_query = render_student_table_filters(students_table)
    filtered_table = filter_students_table(students_table, selected_attempts, search_query)
    title_scope = selected_career if selected_career else "todas las carreras"
    st.subheader(f"Estudiantes en {title_scope}")

    if filtered_table.empty:
        st.info("No hay estudiantes que cumplan los filtros seleccionados.")
        st.stop()

    selected_matricula = render_students_selector(filtered_table)
    render_student_history(historical_df, selected_matricula)


main()
