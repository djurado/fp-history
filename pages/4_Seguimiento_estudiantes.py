"""Página de Seguimiento de Estudiantes - Evolución de repetidores."""

import pandas as pd
import plotly.express as px
import streamlit as st

from src.shared import init_session_state_defaults, load_historical_data, semester_sort_key

st.set_page_config(layout="wide", initial_sidebar_state="expanded")


def _sort_semester_frame(df: pd.DataFrame) -> pd.DataFrame:
    parts = df["SEMESTRE"].astype(str).str.split("-", n=1, expand=True)
    sorted_df = df.assign(
        _YEAR=pd.to_numeric(parts[0], errors="coerce"),
        _TERM=pd.to_numeric(parts[1], errors="coerce"),
    ).sort_values(["_YEAR", "_TERM"], kind="stable")
    return sorted_df.drop(columns=["_YEAR", "_TERM"])


def _build_students_table(df: pd.DataFrame, selected_career: str | None = None) -> pd.DataFrame:
    source_df = df.copy()
    if selected_career:
        source_df = source_df[source_df["CARRERA"].astype(str) == selected_career].copy()

    if source_df.empty:
        return pd.DataFrame()

    # Cada fila representa una toma de la materia para la matrícula.
    attempts = source_df.groupby("MATRICULA").size()
    source_df = _sort_semester_frame(source_df)
    latest = source_df.groupby("MATRICULA", as_index=False).tail(1).copy()
    latest["INTENTOS"] = latest["MATRICULA"].map(attempts).astype(int)

    table = latest[
        ["MATRICULA", "NOMBRE_ESTUDIANTE", "CARRERA", "SEMESTRE", "ESTADO", 
        #  "SIT", 
         "INTENTOS"]
    ].rename(
        columns={
            "NOMBRE_ESTUDIANTE": "NOMBRE",
            "CARRERA": "ULTIMA_CARRERA",
            "SEMESTRE": "ULTIMO_SEMESTRE",
            "ESTADO": "ULTIMO_ESTADO",
            # "SIT": "ULTIMO_SIT",
        }
    )
    parts = table["ULTIMO_SEMESTRE"].astype(str).str.split("-", n=1, expand=True)
    table["_YEAR"] = pd.to_numeric(parts[0], errors="coerce")
    table["_TERM"] = pd.to_numeric(parts[1], errors="coerce")
    table = table.sort_values(["_YEAR", "_TERM", "INTENTOS"], ascending=[False, False, False], kind="stable")
    return table.drop(columns=["_YEAR", "_TERM"])


def _render_student_history(df: pd.DataFrame, selected_matricula: str) -> None:
    history_df = df[df["MATRICULA"].astype(str) == selected_matricula].copy()
    if history_df.empty:
        st.warning("No se encontró histórico para la matrícula seleccionada.")
        return

    history_df = _sort_semester_frame(history_df)
    student_name = str(history_df["NOMBRE_ESTUDIANTE"].iloc[-1])
    last_state = str(history_df["ESTADO"].iloc[-1]) if "ESTADO" in history_df.columns else "-"

    st.subheader(f"Histórico de {student_name} ({selected_matricula})")
    col1, col2, col3 = st.columns(3)
    col1.metric("Intentos", len(history_df))
    col2.metric("Último semestre", str(history_df["SEMESTRE"].iloc[-1]))
    col3.metric("Último estado", last_state)

    if "NOTA FINAL" in history_df.columns:
        chart_df = history_df[["SEMESTRE", "NOTA FINAL", "ESTADO"]].copy()
        semester_order = sorted(
            chart_df["SEMESTRE"].astype(str).unique().tolist(),
            key=semester_sort_key,
        )
        chart_df["SEMESTRE"] = pd.Categorical(chart_df["SEMESTRE"].astype(str), categories=semester_order, ordered=True)
        chart_df = chart_df.sort_values("SEMESTRE")
        chart_df["SEMESTRE"] = chart_df["SEMESTRE"].astype(str)

        fig = px.bar(
            chart_df,
            x="SEMESTRE",
            y="NOTA FINAL",
            color="ESTADO",
            text=chart_df["NOTA FINAL"].map(lambda value: f"{value:.2f}" if pd.notna(value) else ""),
            title=None,
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            yaxis_title="Nota final",
            xaxis_title="Semestre",
            legend_title="Estado",
            xaxis=dict(type="category", categoryorder="array", categoryarray=semester_order),
            height=380,
        )
        st.plotly_chart(fig, use_container_width=True)

    theoretical_columns = [
        "PARCIAL",
        "FINAL",
        "MEJORAMIENTO",
    ]
    practical_columns = [
        
        "TALLERES",
        "PARTICIPACION",
    ]
    review_columns = [
        "SEMESTRE",
        "EXAMEN 1E",
        "REVISADO_X_ESTUDIANTE 1E",
        "EXAMEN 2E",
        "REVISADO_X_ESTUDIANTE 2E",
        "EXAMEN 3E",
        "REVISADO_X_ESTUDIANTE 3E",
        "TRABAJOS_EXTRA",
    ]
    base_columns = [
        "SEMESTRE",
        "PARALELO",
        "ESTADO",
        "NOTA FINAL",
        "TOTAL TEORICO",
        "PRACTICO",
        # "SIT",
    ]

    columns_to_show = [col for col in (base_columns + theoretical_columns + practical_columns) if col in history_df.columns]
    if columns_to_show:
        st.dataframe(history_df[columns_to_show], width="stretch", hide_index=True)
    
    review_to_show = [col for col in (review_columns) if col in history_df.columns]
    if review_to_show:
        review_df = history_df[review_to_show].copy()
        binary_columns = [
            col for col in review_df.columns
            if col.startswith("REVISADO_X_ESTUDIANTE") or col == "TRABAJOS_EXTRA"
        ]
        for column_name in binary_columns:
            numeric_col = pd.to_numeric(review_df[column_name], errors="coerce")
            review_df[column_name] = review_df[column_name].where(
                numeric_col.isna(),
                numeric_col.map({0: "No", 1: "Sí"}).fillna(numeric_col.astype("Int64").astype(str)),
            )

        review_labels = {
            "SEMESTRE": "Semestre",
            "EXAMEN 1E": "Ex 1E",
            "REVISADO_X_ESTUDIANTE 1E": "Rev 1E",
            "EXAMEN 2E": "Ex 2E",
            "REVISADO_X_ESTUDIANTE 2E": "Rev 2E",
            "EXAMEN 3E": "Ex 3E",
            "REVISADO_X_ESTUDIANTE 3E": "Rev 3E",
            "TRABAJOS_EXTRA": "Presentó Trabajos Extras",
        }
        st.dataframe(
            review_df.rename(columns=review_labels),
            width="stretch",
            hide_index=True,
        )


def main() -> None:
    st.title("Seguimiento de estudiantes")
    st.caption("Evolución histórica de estudiantes.")

    init_session_state_defaults()
    historical_df = load_historical_data()

    if historical_df.empty:
        st.warning("No hay datasets históricos disponibles. Primero genera consolidados en datasets/.")
        st.stop()

    if "CARRERA" not in historical_df.columns or "MATRICULA" not in historical_df.columns:
        st.error("El dataset histórico no contiene las columnas mínimas para seguimiento (CARRERA, MATRICULA).")
        st.stop()

    careers = sorted(historical_df["CARRERA"].dropna().astype(str).unique().tolist())
    if not careers:
        st.warning("No hay carreras disponibles en el histórico.")
        st.stop()

    selected_career_label = st.sidebar.selectbox("Carrera", options=["Todas"] + careers)
    selected_career = None if selected_career_label == "Todas" else selected_career_label
    students_table = _build_students_table(historical_df, selected_career)

    if students_table.empty:
        st.info("No se encontraron estudiantes para los filtros seleccionados.")
        st.stop()

    attempt_options = sorted(students_table["INTENTOS"].dropna().astype(int).unique().tolist())
    selected_attempts = st.sidebar.multiselect(
        "Veces tomadas",
        options=attempt_options,
        default=attempt_options,
    )

    # sit_options = sorted(students_table["ULTIMO_SIT"].dropna().unique().tolist())
    # selected_sit = st.sidebar.multiselect(
    #     "Situación (SIT)",
    #     options=sit_options,
    #     default=sit_options,
    # )

    search_query = st.sidebar.text_input("Buscar por nombre o matrícula", value="").strip().lower()

    filtered_table = students_table.copy()
    if selected_attempts:
        filtered_table = filtered_table[filtered_table["INTENTOS"].isin(selected_attempts)]

    # if selected_sit:
    #     filtered_table = filtered_table[filtered_table["ULTIMO_SIT"].isin(selected_sit)]

    if search_query:
        filtered_table = filtered_table[
            filtered_table["NOMBRE"].astype(str).str.lower().str.contains(search_query, na=False)
            | filtered_table["MATRICULA"].astype(str).str.lower().str.contains(search_query, na=False)
        ]

    title_scope = selected_career if selected_career else "todas las carreras"
    st.subheader(f"Estudiantes en {title_scope}")
    if filtered_table.empty:
        st.info("No hay estudiantes que cumplan los filtros seleccionados.")
        st.stop()

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
        disabled=["MATRICULA", "NOMBRE", "ULTIMA_CARRERA", "ULTIMO_SEMESTRE", "ULTIMO_ESTADO", 
                #   "ULTIMO_SIT", 
                  "INTENTOS"],
        column_config={
            "VER": st.column_config.CheckboxColumn("VER", help="Marca para ver el histórico"),
            "MATRICULA": st.column_config.TextColumn("MATRICULA"),
            "NOMBRE": st.column_config.TextColumn("NOMBRE"),
            "ULTIMA_CARRERA": st.column_config.TextColumn("ULTIMA_CARRERA"),
            "ULTIMO_SEMESTRE": st.column_config.TextColumn("ULTIMO_SEMESTRE"),
            "ULTIMO_ESTADO": st.column_config.TextColumn("ULTIMO_ESTADO"),
            # "ULTIMO_SIT": st.column_config.NumberColumn("ULTIMO_SIT", format="%d"),
            "INTENTOS": st.column_config.NumberColumn("INTENTOS", format="%d"),
        },
        key="students_table_editor",
    )

    selected_rows = edited_df[edited_df["VER"]]
    previous_matricula = str(st.session_state.selected_student_matricula)

    if selected_rows.empty:
        selected_matricula = str(filtered_table.iloc[0]["MATRICULA"])
    elif len(selected_rows) == 1:
        selected_matricula = str(selected_rows.iloc[0]["MATRICULA"])
    else:
        checked_matriculas = selected_rows["MATRICULA"].astype(str).tolist()
        new_choices = [matricula for matricula in checked_matriculas if matricula != previous_matricula]
        selected_matricula = new_choices[-1] if new_choices else checked_matriculas[-1]

    selection_changed = selected_matricula != previous_matricula
    needs_cleanup = len(selected_rows) != 1

    st.session_state.selected_student_matricula = selected_matricula

    if selection_changed or needs_cleanup:
        st.rerun()

    _render_student_history(historical_df, selected_matricula)


main()
