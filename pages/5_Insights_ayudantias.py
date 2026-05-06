"""Página de insights de ayudantías."""

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.shared.ayudantias import (
    DAY_ORDER,
    DAY_TYPE_ORDER,
    MODALITY_ORDER,
    build_attendance_by_hour,
    build_attendance_day_hour,
    build_modality_day_type_comparison,
    build_student_attendance_distribution,
    filter_ayudantias_attendance,
    load_ayudantias_sources,
    prepare_ayudantias_data,
    validate_ayudantias_sources,
)


MODALITY_COLORS = {
    "Presencial": "#4E79A7",
    "Virtual": "#F28E2B",
    "Sin clasificar": "#9EA3A8",
}


st.set_page_config(layout="wide", initial_sidebar_state="expanded")


def main() -> None:
    st.title("Insights de ayudantías")
    st.caption("Análisis de asistencia del semestre 2025-2.")

    attendance_df, classes_df = load_ayudantias_sources()
    issues = validate_ayudantias_sources(attendance_df, classes_df)

    if issues:
        for issue in issues:
            st.error(issue)
        st.stop()

    data = prepare_ayudantias_data(attendance_df, classes_df)
    attendance = data.attendance

    if attendance.empty:
        st.warning("No hay asistencias disponibles para graficar.")
        st.stop()

    filtered_attendance = render_filters(attendance)

    if filtered_attendance.empty:
        st.warning("No hay asistencias para los filtros seleccionados.")
        st.stop()

    render_quality_notes(data)
    render_metrics(filtered_attendance)

    col_left, col_right = st.columns(2)
    with col_left:
        render_attendance_by_hour(filtered_attendance)
    with col_right:
        render_modality_comparison(filtered_attendance)

    render_attendance_day_hour(filtered_attendance)
    render_student_boxplot(filtered_attendance)


def render_filters(attendance):
    min_date = attendance["FECHA_DT"].min().date()
    max_date = attendance["FECHA_DT"].max().date()
    hour_options = sorted(attendance["HORA"].dropna().astype(str).unique().tolist())
    modality_options = [value for value in MODALITY_ORDER if value in set(attendance["MODALIDAD"])]
    day_type_options = [value for value in DAY_TYPE_ORDER if value in set(attendance["TIPO_DIA"])]

    with st.sidebar:
        st.header("Filtros")

        date_range = st.date_input(
            "Rango de fechas",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
        if isinstance(date_range, tuple) and len(date_range) == 2:
            selected_date_range = date_range
        else:
            selected_date_range = (min_date, max_date)

        selected_hours = st.multiselect(
            "Horario",
            options=hour_options,
            default=hour_options,
        )
        selected_modalities = st.segmented_control(
            "Modalidad",
            options=modality_options,
            default=modality_options,
            selection_mode="multi",
        )
        if selected_modalities is None:
            selected_modalities = []

        selected_day_types = st.segmented_control(
            "Tipo de día",
            options=day_type_options,
            default=day_type_options,
            selection_mode="multi",
        )
        if selected_day_types is None:
            selected_day_types = []

    return filter_ayudantias_attendance(
        attendance,
        date_range=selected_date_range,
        hours=selected_hours,
        modalities=list(selected_modalities),
        day_types=list(selected_day_types),
    )


def render_quality_notes(data) -> None:
    notes = []
    if data.duplicated_attendance_rows:
        notes.append(f"{data.duplicated_attendance_rows} asistencias duplicadas fueron deduplicadas.")
    if data.invalid_attendance_dates:
        notes.append(f"{data.invalid_attendance_dates} fechas inválidas en asistencias no se usaron.")
    if data.invalid_class_dates:
        notes.append(f"{data.invalid_class_dates} fechas inválidas en clases no se usaron.")
    if data.unmatched_attendance_sessions:
        notes.append(
            f"{data.unmatched_attendance_sessions} sesiones con asistencia no tienen lugar en clases."
        )

    if notes:
        st.info(" ".join(notes))


def render_metrics(attendance) -> None:
    student_distribution = build_student_attendance_distribution(attendance)
    sessions = attendance.drop_duplicates(["FECHA_KEY", "HORA", "AYUDANTE_KEY"])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Asistencias", f"{len(attendance):,}")
    col2.metric("Estudiantes", f"{attendance['MATRICULA'].nunique():,}")
    col3.metric("Sesiones", f"{len(sessions):,}")
    col4.metric("Promedio por estudiante", f"{student_distribution['Asistencias'].mean():.2f}")


def render_attendance_by_hour(attendance) -> None:
    chart_df = build_attendance_by_hour(attendance)
    hour_order = chart_df["HORA"].astype(str).tolist()
    st.subheader("Asistencias por horario")
    fig = px.bar(
        chart_df,
        x="HORA",
        y="Asistencias",
        text="Asistencias",
        color="HORA",
        category_orders={"HORA": hour_order},
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(
        showlegend=False,
        xaxis_title="Horario",
        yaxis_title="Asistencias",
        xaxis=dict(type="category", categoryorder="array", categoryarray=hour_order),
        margin=dict(t=20, r=20, b=20, l=20),
    )
    st.plotly_chart(fig, width="stretch")


def render_attendance_day_hour(attendance) -> None:
    chart_df = build_attendance_day_hour(attendance)
    pivot = chart_df.pivot(index="DIA", columns="HORA", values="Asistencias").reindex(DAY_ORDER)

    st.subheader("Asistencias por día y hora")
    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns,
            y=pivot.index,
            colorscale="YlGnBu",
            text=pivot.values,
            texttemplate="%{text}",
            hovertemplate="Día: %{y}<br>Horario: %{x}<br>Asistencias: %{z}<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis_title="Horario",
        yaxis_title="Día",
        xaxis=dict(type="category"),
        margin=dict(t=20, r=20, b=20, l=20),
    )
    st.plotly_chart(fig, width="stretch")


def render_modality_comparison(attendance) -> None:
    chart_df = build_modality_day_type_comparison(attendance)
    st.subheader("Presenciales vs virtuales")
    fig = px.bar(
        chart_df,
        x="TIPO_DIA",
        y="Asistencias",
        color="MODALIDAD",
        text="Asistencias",
        barmode="group",
        category_orders={
            "TIPO_DIA": DAY_TYPE_ORDER,
            "MODALIDAD": MODALITY_ORDER,
        },
        color_discrete_map=MODALITY_COLORS,
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(
        legend_title_text="Modalidad",
        xaxis_title="Tipo de día",
        yaxis_title="Asistencias",
        margin=dict(t=20, r=20, b=20, l=20),
    )
    st.plotly_chart(fig, width="stretch")


def render_student_boxplot(attendance) -> None:
    student_distribution = build_student_attendance_distribution(attendance)
    st.subheader("Asistencias por estudiante")
    fig = px.box(
        student_distribution,
        y="Asistencias",
        points="all",
        hover_data=["MATRICULA", "Estudiante", "Paralelo"],
    )
    fig.update_traces(marker=dict(size=5, opacity=0.55))
    fig.update_layout(
        xaxis_title="Estudiantes",
        yaxis_title="Número de asistencias",
        margin=dict(t=20, r=20, b=20, l=20),
    )
    st.plotly_chart(fig, width="stretch")

    with st.expander("Estudiantes con más asistencias", expanded=False):
        st.dataframe(
            student_distribution.head(20)[
                ["MATRICULA", "Estudiante", "Paralelo", "Asistencias"]
            ],
            hide_index=True,
            width="stretch",
        )


main()
