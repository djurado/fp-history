"""Componentes y helpers para la vista de seguimiento de estudiantes."""

import pandas as pd
import plotly.express as px
import streamlit as st

from src.shared.filter_state import (
    render_shared_segmented_control,
)
from src.shared.components import render_shared_academic_filters
from src.shared.constants import (
    STATE_COLORS,
    STATE_ORDER,
    STUDENT_TRACKING_DISABLED_COLUMNS,
    STUDENT_TRACKING_REQUIRED_COLUMNS,
    STUDENT_TRACKING_TABLE_COLUMNS,
    STUDENT_TRACKING_TABLE_LABELS,
)
from src.shared.utils import (
    load_practical_max_map_for_semester,
    semester_sort_key,
    sort_semester_frame,
)


def validate_student_tracking_data(df: pd.DataFrame) -> list[str]:
    """Retorna las columnas mínimas faltantes para la vista de seguimiento."""
    return [column for column in STUDENT_TRACKING_REQUIRED_COLUMNS if column not in df.columns]


def build_students_table(
    df: pd.DataFrame,
    selected_careers: list[str] | str | None = None,
    selected_faculties: list[str] | None = None,
    selected_career_types: list[str] | None = None,
) -> pd.DataFrame:
    """Construye la tabla resumen con el último estado de cada estudiante."""
    source_df = df.copy()
    if selected_faculties and "FACULTAD" in source_df.columns:
        source_df = source_df[source_df["FACULTAD"].astype(str).isin(selected_faculties)].copy()
    if selected_career_types and "CARRERA_TIPO" in source_df.columns:
        source_df = source_df[
            source_df["CARRERA_TIPO"].astype(str).isin(selected_career_types)
        ].copy()

    selected_career_values = _coerce_selected_careers(selected_careers)
    if selected_career_values:
        source_df = source_df[source_df["CARRERA"].astype(str).isin(selected_career_values)].copy()

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


def render_student_academic_filters(historical_df: pd.DataFrame) -> tuple[list[str], list[str], list[str]]:
    """Renderiza filtros generales para seguimiento."""
    with st.sidebar:
        return render_shared_academic_filters(historical_df)


def render_student_table_filters(students_table: pd.DataFrame) -> tuple[list[int], str]:
    """Renderiza filtros laterales que dependen de la tabla de estudiantes."""
    attempt_options = sorted(students_table["INTENTOS"].dropna().astype(int).unique().tolist())
    with st.sidebar:
        selected_attempts = render_shared_segmented_control(
            "Veces tomadas",
            options=attempt_options,
            state_key="seguimiento_selected_attempts",
            widget_key="_seguimiento_selected_attempts",
            default=attempt_options,
        )
        search_query = st.text_input("Buscar por nombre o matrícula", value="").strip().lower()
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
    _render_student_transposed_history_table(history_df)


def _build_student_table_column_config() -> dict[str, object]:
    return {
        "VER": st.column_config.CheckboxColumn("VER", help="Seleccionar para ver el histórico"),
        "MATRICULA": st.column_config.TextColumn("Matrícula"),
        "NOMBRE": st.column_config.TextColumn("Nombre"),
        "ULTIMA_CARRERA": st.column_config.TextColumn("Carrera (*)", help="Última carrera"),
        "ULTIMO_SEMESTRE": st.column_config.TextColumn("Semestre (*)", help="Último semestre"),
        "ULTIMO_ESTADO": st.column_config.TextColumn("Estado (*)", help="Último estado"),
        "INTENTOS": st.column_config.NumberColumn("Intentos", format="%d", help="Número de veces que el estudiante aparece en el histórico"),
    }


def _coerce_selected_careers(selected_careers: list[str] | str | None) -> list[str]:
    if selected_careers is None:
        return []
    if isinstance(selected_careers, str):
        return [selected_careers]
    return list(selected_careers)


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


def _render_student_transposed_history_table(history_df: pd.DataFrame) -> None:
    semester_labels = _build_unique_semester_labels(history_df)
    section_rows = _build_transposed_history_rows(history_df, semester_labels)
    practical_max_by_semester = _build_practical_max_by_semester(history_df, semester_labels)

    for section_name, section_df in section_rows:
        with st.expander(section_name, expanded=section_name == "Resumen"):
            _render_section_dataframes(
                section_df,
                semester_labels,
                practical_max_by_semester,
            )


def _format_binary_bool_value(value) -> str:
    if pd.isna(value):
        return ""

    normalized_value = str(value).strip().lower()
    if normalized_value in {"1", "1.0", "sí", "si", "true", "verdadero"}:
        return "✅ Sí"
    if normalized_value in {"0", "0.0", "no", "false", "falso"}:
        return "❌ No"
    return "✅ Sí" if bool(value) else "❌ No"


def _build_unique_semester_labels(history_df: pd.DataFrame) -> list[str]:
    seen_counts: dict[str, int] = {}
    labels: list[str] = []
    for semester in history_df["SEMESTRE"].astype(str).tolist():
        seen_counts[semester] = seen_counts.get(semester, 0) + 1
        label = semester if seen_counts[semester] == 1 else f"{semester} ({seen_counts[semester]})"
        labels.append(label)
    return labels


def _build_transposed_history_rows(
    history_df: pd.DataFrame,
    semester_labels: list[str],
) -> list[tuple[str, pd.DataFrame]]:
    sections = [
        (
            "Resumen",
            [
                ("Estado", "ESTADO", "state"),
                ("Paralelo", "PARALELO", "state"),
                ("Nota final", "NOTA FINAL", "progress"),
                ("Teórico", "TOTAL TEORICO", "progress"),
                ("Práctico", "PRACTICO", "progress"),
            ],
        ),
        (
            "Evaluaciones teóricas",
            [
                ("Parcial", "PARCIAL", "progress"),
                ("Examen parcial", "EXAMEN 1E", "progress"),
                ("Revisó examen parcial", "REVISADO_X_ESTUDIANTE 1E", "icon"),
                ("Final", "FINAL", "progress"),
                ("Examen final", "EXAMEN 2E", "progress"),
                ("Revisó examen final", "REVISADO_X_ESTUDIANTE 2E", "icon"),
                ("Mejoramiento", "EXAMEN 3E", "progress"),
                ("Revisó examen mejoramiento", "REVISADO_X_ESTUDIANTE 3E", "icon"),
                ("Presentó trabajos extras", "TRABAJOS_EXTRA", "icon"),
            ],
        ),
        (
            "Práctico",
            [
                ("Práctico", "PRACTICO", "progress"),
                ("Talleres", "TALLERES", "progress"),
                ("Participación", "PARTICIPACION", "progress"),
            ],
        ),
    ]

    table_sections = []
    for section_name, indicators in sections:
        rows = [
            _build_indicator_row(history_df, semester_labels, label, source_column, value_type)
            for label, source_column, value_type in indicators
            if source_column in history_df.columns
        ]
        if rows:
            table_sections.append((section_name, pd.DataFrame(rows)))
    return table_sections


def _build_indicator_row(
    history_df: pd.DataFrame,
    semester_labels: list[str],
    label: str,
    source_column: str,
    value_type: str,
) -> dict[str, object]:
    row = {"Indicador": label, "_source_column": source_column, "_value_type": value_type}
    for semester_label, (_, source_row) in zip(semester_labels, history_df.iterrows(), strict=False):
        row[semester_label] = _get_display_source_value(source_row, source_column)
    return row


def _get_display_source_value(source_row: pd.Series, source_column: str):
    if not _should_show_exam_value(source_row, source_column):
        return pd.NA
    return source_row[source_column]


def _should_show_exam_value(source_row: pd.Series, source_column: str) -> bool:
    exam_status_columns = {
        "EXAMEN 1E": "ESTADO 1E",
        "EXAMEN 2E": "ESTADO 2E",
        "EXAMEN 3E": "ESTADO 3E",
    }
    status_column = exam_status_columns.get(source_column)
    if status_column is None or status_column not in source_row.index:
        return True

    return _is_exam_taken(source_row[status_column])


def _is_exam_taken(value) -> bool:
    if pd.isna(value):
        return False

    normalized_value = str(value).strip().lower()
    return normalized_value in {"1", "1.0", "sí", "si", "true", "verdadero", '3', '3.0'}


def _render_section_dataframes(
    section_df: pd.DataFrame,
    semester_labels: list[str],
    practical_max_by_semester: dict[str, dict[str, float]],
) -> None:
    state_df = _build_display_dataframe(section_df, semester_labels, "state", practical_max_by_semester)
    if not state_df.empty:
        st.dataframe(
            _style_state_dataframe(state_df, semester_labels),
            width="stretch",
            hide_index=True,
            column_config=_build_text_column_config(semester_labels),
        )

    progress_df = _build_display_dataframe(
        section_df,
        semester_labels,
        "progress",
        practical_max_by_semester,
    )
    if not progress_df.empty:
        st.dataframe(
            _style_progress_dataframe(progress_df, semester_labels),
            width="stretch",
            hide_index=True,
            column_config=_build_progress_column_config(semester_labels),
        )

    checkbox_df = _build_display_dataframe(section_df, semester_labels, "icon", practical_max_by_semester)
    if not checkbox_df.empty:
        st.dataframe(
            checkbox_df,
            width="stretch",
            hide_index=True,
            column_config=_build_checkbox_column_config(semester_labels),
        )


def _build_display_dataframe(
    section_df: pd.DataFrame,
    semester_labels: list[str],
    value_type: str,
    practical_max_by_semester: dict[str, dict[str, float]],
) -> pd.DataFrame:
    display_df = section_df.loc[section_df["_value_type"] == value_type].copy()
    if display_df.empty:
        return pd.DataFrame()

    if value_type == "progress":
        for semester_label in semester_labels:
            display_df[semester_label] = display_df.apply(
                lambda row: _normalize_progress_value(
                    value=row[semester_label],
                    source_column=str(row["_source_column"]),
                    semester_label=semester_label,
                    practical_max_by_semester=practical_max_by_semester,
                ),
                axis=1,
            )
    elif value_type == "icon":
        for semester_label in semester_labels:
            display_df[semester_label] = display_df[semester_label].map(_format_binary_bool_value)
    else:
        for semester_label in semester_labels:
            display_df[semester_label] = display_df[semester_label].map(_format_plain_value)

    display_df = display_df.drop(columns=["_source_column", "_value_type"])
    return display_df


def _build_progress_column_config(semester_labels: list[str]) -> dict[str, object]:
    column_config: dict[str, object] = {
        "Indicador": st.column_config.TextColumn("Indicador", pinned=True),
    }
    column_config.update(
        {
            semester_label: st.column_config.ProgressColumn(
                semester_label,
                format="%.1f%%",
                min_value=0,
                max_value=100,
                color="gray",
            )
            for semester_label in semester_labels
        }
    )
    return column_config


def _build_checkbox_column_config(semester_labels: list[str]) -> dict[str, object]:
    column_config: dict[str, object] = {
        "Indicador": st.column_config.TextColumn("Indicador", pinned=True),
    }
    column_config.update(
        {
            semester_label: st.column_config.TextColumn(semester_label)
            for semester_label in semester_labels
        }
    )
    return column_config


def _build_text_column_config(semester_labels: list[str]) -> dict[str, object]:
    column_config: dict[str, object] = {
        "Indicador": st.column_config.TextColumn("Indicador", pinned=True),
    }
    column_config.update(
        {
            semester_label: st.column_config.TextColumn(semester_label)
            for semester_label in semester_labels
        }
    )
    return column_config


def _style_state_dataframe(df: pd.DataFrame, semester_labels: list[str]):
    return df.style.map(_style_state_value, subset=semester_labels)


def _style_progress_dataframe(df: pd.DataFrame, semester_labels: list[str]):
    return df.style.map(_style_progress_value, subset=semester_labels)


def _style_state_value(value) -> str:
    state = str(value).strip()
    if state == "AP":
        return "background-color: #DCFCE7; color: #166534; font-weight: 700;"
    if state in ["RP", "RT", "PF"]:
        return "background-color: #FEE2E2; color: #7F1D1D; font-weight: 700;"
    return "background-color: #F1F3F5; color: #4B5563; font-weight: 700;"


def _style_progress_value(value) -> str:
    numeric_value = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric_value) or numeric_value < 50:
        return ""
    if numeric_value < 60:
        return "background-color: #FEF3C7;"
    return "background-color: #DCFCE7;"


def _build_practical_max_by_semester(
    history_df: pd.DataFrame,
    semester_labels: list[str],
) -> dict[str, dict[str, float]]:
    return {
        semester_label: load_practical_max_map_for_semester(str(source_row["SEMESTRE"]))
        for semester_label, (_, source_row) in zip(semester_labels, history_df.iterrows(), strict=False)
    }


def _normalize_progress_value(
    value,
    source_column: str,
    semester_label: str,
    practical_max_by_semester: dict[str, dict[str, float]],
) -> float:
    numeric_value = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric_value):
        return numeric_value

    if source_column not in {"TALLERES", "PARTICIPACION"}:
        return float(numeric_value)

    max_value = practical_max_by_semester.get(semester_label, {}).get(source_column)
    if max_value is None or max_value <= 0:
        return float(numeric_value)

    return min(100.0, max(0.0, (float(numeric_value) / float(max_value)) * 100.0))


def _format_plain_value(value) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return f"{int(value)}"
    return str(value)
