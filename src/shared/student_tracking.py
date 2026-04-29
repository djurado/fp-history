"""Componentes y helpers para la vista de seguimiento de estudiantes."""

import pandas as pd
import plotly.express as px
import streamlit as st

from src.shared.constants import (
    STATE_COLORS,
    STATE_ORDER,
    STUDENT_HISTORY_BASE_COLUMNS,
    STUDENT_HISTORY_PRACTICAL_COLUMNS,
    STUDENT_HISTORY_REVIEW_COLUMNS,
    STUDENT_HISTORY_REVIEW_LABELS,
    STUDENT_HISTORY_THEORY_COLUMNS,
    STUDENT_TRACKING_DISABLED_COLUMNS,
    STUDENT_TRACKING_REQUIRED_COLUMNS,
    STUDENT_TRACKING_TABLE_COLUMNS,
    STUDENT_TRACKING_TABLE_LABELS,
)
from src.shared.utils import semester_sort_key, sort_semester_frame


def validate_student_tracking_data(df: pd.DataFrame) -> list[str]:
    """Retorna las columnas mínimas faltantes para la vista de seguimiento."""
    return [column for column in STUDENT_TRACKING_REQUIRED_COLUMNS if column not in df.columns]


def build_students_table(df: pd.DataFrame, selected_career: str | None = None) -> pd.DataFrame:
    """Construye la tabla resumen con el último estado de cada estudiante."""
    source_df = df.copy()
    if selected_career:
        source_df = source_df[source_df["CARRERA"].astype(str) == selected_career].copy()

    if source_df.empty:
        return pd.DataFrame()

    attempts = source_df.groupby("MATRICULA").size()
    source_df = sort_semester_frame(source_df)
    latest = source_df.groupby("MATRICULA", as_index=False).tail(1).copy()
    latest["INTENTOS"] = latest["MATRICULA"].map(attempts).astype(int)

    columns_to_show = [column for column in STUDENT_TRACKING_TABLE_COLUMNS if column in latest.columns]
    table = latest[columns_to_show].rename(columns=STUDENT_TRACKING_TABLE_LABELS)

    parts = table["ULTIMO_SEMESTRE"].astype(str).str.split("-", n=1, expand=True)
    table["_YEAR"] = pd.to_numeric(parts[0], errors="coerce")
    table["_TERM"] = pd.to_numeric(parts[1], errors="coerce")
    table = table.sort_values(
        ["_YEAR", "_TERM", "INTENTOS"],
        ascending=[False, False, False],
        kind="stable",
    )
    return table.drop(columns=["_YEAR", "_TERM"])


def render_student_career_filter(historical_df: pd.DataFrame) -> str | None:
    """Renderiza el filtro de carrera para seguimiento."""
    careers = sorted(historical_df["CARRERA"].dropna().astype(str).unique().tolist())
    selected_career_label = st.sidebar.selectbox("Carrera", options=["Todas"] + careers)
    return None if selected_career_label == "Todas" else selected_career_label


def render_student_table_filters(students_table: pd.DataFrame) -> tuple[list[int], str]:
    """Renderiza filtros laterales que dependen de la tabla de estudiantes."""
    attempt_options = sorted(students_table["INTENTOS"].dropna().astype(int).unique().tolist())
    selected_attempts = st.sidebar.multiselect(
        "Veces tomadas",
        options=attempt_options,
        default=attempt_options,
    )

    search_query = st.sidebar.text_input("Buscar por nombre o matrícula", value="").strip().lower()
    return selected_attempts, search_query


def filter_students_table(
    students_table: pd.DataFrame,
    selected_attempts: list[int],
    search_query: str,
) -> pd.DataFrame:
    """Aplica filtros de intentos y búsqueda sobre la tabla de estudiantes."""
    filtered_table = students_table.copy()

    if selected_attempts:
        filtered_table = filtered_table[filtered_table["INTENTOS"].isin(selected_attempts)]

    if search_query:
        search_mask = (
            filtered_table["NOMBRE"].astype(str).str.lower().str.contains(search_query, na=False)
            | filtered_table["MATRICULA"].astype(str).str.lower().str.contains(search_query, na=False)
        )
        filtered_table = filtered_table[search_mask]

    return filtered_table


def render_students_selector(filtered_table: pd.DataFrame) -> str:
    """Renderiza la tabla seleccionable y retorna la matrícula activa."""
    if "selected_student_matricula" not in st.session_state:
        st.session_state.selected_student_matricula = str(filtered_table.iloc[0]["MATRICULA"])

    editor_df = filtered_table.copy()
    editor_df.insert(0, "VER", False)
    editor_df["MATRICULA"] = editor_df["MATRICULA"].astype(str)
    editor_df.loc[
        editor_df["MATRICULA"] == str(st.session_state.selected_student_matricula),
        "VER",
    ] = True

    edited_df = st.data_editor(
        editor_df,
        width="stretch",
        hide_index=True,
        disabled=list(STUDENT_TRACKING_DISABLED_COLUMNS),
        column_config=_build_student_table_column_config(),
        key="students_table_editor",
    )

    selected_rows = edited_df[edited_df["VER"]]
    previous_matricula = str(st.session_state.selected_student_matricula)
    selected_matricula = _resolve_selected_matricula(
        selected_rows=selected_rows,
        filtered_table=filtered_table,
        previous_matricula=previous_matricula,
    )

    selection_changed = selected_matricula != previous_matricula
    needs_cleanup = len(selected_rows) != 1

    st.session_state.selected_student_matricula = selected_matricula

    if selection_changed or needs_cleanup:
        st.rerun()

    return selected_matricula


def render_student_history(df: pd.DataFrame, selected_matricula: str) -> None:
    """Renderiza el histórico completo de un estudiante."""
    history_df = df[df["MATRICULA"].astype(str) == selected_matricula].copy()
    if history_df.empty:
        st.warning("No se encontró histórico para la matrícula seleccionada.")
        return

    history_df = sort_semester_frame(history_df)
    student_name = str(history_df["NOMBRE_ESTUDIANTE"].iloc[-1])
    last_state = str(history_df["ESTADO"].iloc[-1]) if "ESTADO" in history_df.columns else "-"

    st.subheader(f"Histórico de {student_name} ({selected_matricula})")
    col1, col2, col3 = st.columns(3)
    col1.metric("Intentos", len(history_df))
    col2.metric("Último semestre", str(history_df["SEMESTRE"].iloc[-1]))
    col3.metric("Último estado", last_state)

    _render_student_grade_chart(history_df)
    _render_student_grade_table(history_df)
    _render_student_review_table(history_df)


def _build_student_table_column_config() -> dict[str, object]:
    return {
        "VER": st.column_config.CheckboxColumn("VER", help="Marca para ver el histórico"),
        "MATRICULA": st.column_config.TextColumn("MATRICULA"),
        "NOMBRE": st.column_config.TextColumn("NOMBRE"),
        "ULTIMA_CARRERA": st.column_config.TextColumn("ULTIMA_CARRERA"),
        "ULTIMO_SEMESTRE": st.column_config.TextColumn("ULTIMO_SEMESTRE"),
        "ULTIMO_ESTADO": st.column_config.TextColumn("ULTIMO_ESTADO"),
        "INTENTOS": st.column_config.NumberColumn("INTENTOS", format="%d"),
    }


def _resolve_selected_matricula(
    selected_rows: pd.DataFrame,
    filtered_table: pd.DataFrame,
    previous_matricula: str,
) -> str:
    if selected_rows.empty:
        return str(filtered_table.iloc[0]["MATRICULA"])

    if len(selected_rows) == 1:
        return str(selected_rows.iloc[0]["MATRICULA"])

    checked_matriculas = selected_rows["MATRICULA"].astype(str).tolist()
    new_choices = [matricula for matricula in checked_matriculas if matricula != previous_matricula]
    return new_choices[-1] if new_choices else checked_matriculas[-1]


def _render_student_grade_chart(history_df: pd.DataFrame) -> None:
    if "NOTA FINAL" not in history_df.columns:
        return

    chart_df = history_df[["SEMESTRE", "NOTA FINAL", "ESTADO"]].copy()
    semester_order = sorted(
        chart_df["SEMESTRE"].astype(str).unique().tolist(),
        key=semester_sort_key,
    )
    chart_df["SEMESTRE"] = pd.Categorical(
        chart_df["SEMESTRE"].astype(str),
        categories=semester_order,
        ordered=True,
    )
    chart_df = chart_df.sort_values("SEMESTRE")
    chart_df["SEMESTRE"] = chart_df["SEMESTRE"].astype(str)

    fig = px.bar(
        chart_df,
        x="SEMESTRE",
        y="NOTA FINAL",
        color="ESTADO",
        text=chart_df["NOTA FINAL"].map(lambda value: f"{value:.2f}" if pd.notna(value) else ""),
        color_discrete_map=STATE_COLORS,
        category_orders={"SEMESTRE": semester_order, "ESTADO": STATE_ORDER},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        yaxis_title="Nota final",
        xaxis_title="Semestre",
        legend_title="Estado",
        xaxis=dict(type="category", categoryorder="array", categoryarray=semester_order),
        height=380,
    )
    st.plotly_chart(fig, width="stretch")


def _render_student_grade_table(history_df: pd.DataFrame) -> None:
    columns_to_show = [
        column
        for column in (
            STUDENT_HISTORY_BASE_COLUMNS
            + STUDENT_HISTORY_THEORY_COLUMNS
            + STUDENT_HISTORY_PRACTICAL_COLUMNS
        )
        if column in history_df.columns
    ]
    if columns_to_show:
        st.dataframe(history_df[columns_to_show], width="stretch", hide_index=True)


def _render_student_review_table(history_df: pd.DataFrame) -> None:
    review_to_show = [column for column in STUDENT_HISTORY_REVIEW_COLUMNS if column in history_df.columns]
    if not review_to_show:
        return

    review_df = history_df[review_to_show].copy()
    for column_name in _get_binary_review_columns(review_df):
        review_df[column_name] = _format_binary_review_column(review_df[column_name])

    st.dataframe(
        review_df.rename(columns=STUDENT_HISTORY_REVIEW_LABELS),
        width="stretch",
        hide_index=True,
    )


def _get_binary_review_columns(review_df: pd.DataFrame) -> list[str]:
    return [
        column
        for column in review_df.columns
        if column.startswith("REVISADO_X_ESTUDIANTE") or column == "TRABAJOS_EXTRA"
    ]


def _format_binary_review_column(series: pd.Series) -> pd.Series:
    numeric_col = pd.to_numeric(series, errors="coerce")
    return series.where(
        numeric_col.isna(),
        numeric_col.map({0: "No", 1: "Sí"}).fillna(numeric_col.astype("Int64").astype(str)),
    )
