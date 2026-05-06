"""Componentes de UI compartidos entre todas las páginas."""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.shared.constants import (
    STATE_COLORS,
    STATE_LABELS,
    STATE_ORDER,
    THEORY_COMPONENT_COLORS,
    PRACTICAL_COMPONENT_COLORS,
    TOTALS_COMPONENT_COLORS,
    TOPIC_COLORS,
    EXAM_LABELS,
)
from src.shared.filter_state import (
    FILTER_CAREERS_KEY,
    FILTER_CAREERS_WIDGET_KEY,
    FILTER_FACULTIES_KEY,
    FILTER_FACULTIES_WIDGET_KEY,
    FILTER_CAREER_TYPES_KEY,
    FILTER_CAREER_TYPES_WIDGET_KEY,
    render_shared_multiselect,
    render_shared_segmented_control,
)
from src.shared.utils import (
    apply_filters,
    valid_exam_mask,
    mean_exam,
    component_to_exam,
    extract_topic_base,
    group_topic_columns_by_base,
    format_knowledge_list,
    load_topic_max_map_for_semester,
    load_practical_max_map_for_semester,
    load_topic_knowledge_map_for_semester,
    parallel_sort_key,
)


# ============== Componentes de sidebar ==============

def render_sidebar_single_semester(
    dataset_map: dict[str, Path],
    df: pd.DataFrame,
    page_key: str,
) -> tuple[str, list[str], list[str], list[str], list, list[str], list[str]]:
    """Renderiza el sidebar para una página de semestre individual."""
    from src.shared.utils import get_default_semester
    
    with st.sidebar:
        st.header("Filtros")

        available_semesters = sorted(dataset_map.keys(), reverse=True)
        default_semester = get_default_semester(dataset_map)

        selected_semester = st.selectbox(
            "Semestre",
            options=available_semesters,
            index=available_semesters.index(default_semester),
        )
        selected_year_str, selected_term_str = selected_semester.split("-")
        st.session_state.selected_year = int(selected_year_str)
        st.session_state.selected_term = int(selected_term_str)

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

    with st.sidebar:
        selected_faculties, selected_career_types, selected_careers = render_shared_academic_filters(df)

        selected_sit = render_shared_segmented_control(
            "Veces tomada (SIT)",
            options=sit_options,
            state_key=f"{page_key}_selected_sit",
            widget_key=f"_{page_key}_selected_sit",
            default=sit_options,
        )

        selected_states = st.segmented_control(
            "Estado",
            options=state_options,
            default=state_options,
            selection_mode="multi",
        )
        if selected_states is None:
            selected_states = []

        selected_parallels = st.multiselect("Paralelo", options=parallel_options)

    return (
        selected_semester,
        selected_faculties,
        selected_careers,
        selected_career_types,
        selected_sit,
        selected_states,
        selected_parallels,
    )


def render_sidebar_historical(
    df: pd.DataFrame,
) -> tuple[list[str], list[str], list[str], list[str], list]:
    """Renderiza el sidebar para una página histórica."""
    from src.shared.utils import build_semester_options, semester_sort_key
    
    semesters = build_semester_options(df)

    with st.sidebar:
        st.header("Filtros")

        selected_semesters = st.select_slider(
            "Rango de semestres",
            options=semesters,
            value=(semesters[0], semesters[-1]),
        )

        selected_faculties, selected_career_types, selected_careers = render_shared_academic_filters(df)

        sit_options = sorted(df["SIT"].dropna().unique().tolist())
        selected_sit = render_shared_segmented_control(
            "Veces tomada (SIT)",
            options=sit_options,
            state_key="tendencias_selected_sit",
            widget_key="_tendencias_selected_sit",
            default=sit_options,
        )

    semester_start, semester_end = selected_semesters
    semester_range = [
        semester
        for semester in semesters
        if semester_sort_key(semester_start) <= semester_sort_key(semester) <= semester_sort_key(semester_end)
    ]

    return semester_range, selected_faculties, selected_careers, selected_career_types, selected_sit


def render_shared_academic_filters(df: pd.DataFrame) -> tuple[list[str], list[str], list[str]]:
    """Renderiza filtros generales compartidos entre páginas académicas."""
    faculty_options = (
        sorted(df["FACULTAD"].dropna().astype(str).unique().tolist())
        if "FACULTAD" in df.columns
        else []
    )
    career_type_options = (
        sorted(df["CARRERA_TIPO"].dropna().astype(str).unique().tolist())
        if "CARRERA_TIPO" in df.columns
        else []
    )

    selected_faculties = render_shared_multiselect(
        "Facultad",
        options=faculty_options,
        state_key=FILTER_FACULTIES_KEY,
        widget_key=FILTER_FACULTIES_WIDGET_KEY,
    )
    selected_career_types = render_shared_segmented_control(
        "Tipo de carrera",
        options=career_type_options,
        state_key=FILTER_CAREER_TYPES_KEY,
        widget_key=FILTER_CAREER_TYPES_WIDGET_KEY,
        default=career_type_options,
    )

    careers_source = df.copy()
    if selected_faculties and "FACULTAD" in careers_source.columns:
        careers_source = careers_source[
            careers_source["FACULTAD"].astype(str).isin(selected_faculties)
        ].copy()
    if selected_career_types and "CARRERA_TIPO" in careers_source.columns:
        careers_source = careers_source[
            careers_source["CARRERA_TIPO"].astype(str).isin(selected_career_types)
        ].copy()

    career_options = (
        sorted(careers_source["CARRERA"].dropna().astype(str).unique().tolist())
        if "CARRERA" in careers_source.columns
        else []
    )
    selected_careers = render_shared_multiselect(
        "Carrera",
        options=career_options,
        state_key=FILTER_CAREERS_KEY,
        widget_key=FILTER_CAREERS_WIDGET_KEY,
    )

    return selected_faculties, selected_career_types, selected_careers


# ============== Componentes de métricas ==============

def render_main_metrics(filtered_df: pd.DataFrame, title: str = "Indicadores principales:") -> None:
    """Renderiza las métricas principales."""
    st.subheader(title)

    metrics = []

    metrics.append(("Estudiantes", len(filtered_df)))

    if "PARALELO" in filtered_df.columns:
        metrics.append(("Paralelos", filtered_df["PARALELO"].nunique()))

    if "CARRERA" in filtered_df.columns:
        metrics.append(("Carreras", filtered_df["CARRERA"].nunique()))
    elif "COD" in filtered_df.columns:
        metrics.append(("Carreras", filtered_df["COD"].nunique()))

    if "ESTADO" in filtered_df.columns and len(filtered_df):
        approved_pct = (filtered_df["ESTADO"] == "AP").mean() * 100
        metrics.append(("Aprobados (%)", f"{approved_pct:.1f}%"))

    if "TRABAJOS_EXTRA" in filtered_df.columns:
        extra_students = int((filtered_df["TRABAJOS_EXTRA"].fillna(0) == 1).sum())
        metrics.append(("Estudiantes (trabajo extra)", extra_students))

    review_column_map = {
        "1E": "REVISADO_X_ESTUDIANTE 1E",
        "2E": "REVISADO_X_ESTUDIANTE 2E",
        "3E": "REVISADO_X_ESTUDIANTE 3E",
    }

    for exam_key, review_col in review_column_map.items():
        status_col = f"ESTADO {exam_key}"

        if review_col not in filtered_df.columns or status_col not in filtered_df.columns:
            continue

        exam_df = filtered_df.loc[filtered_df[status_col] == 1]
        if exam_df.empty:
            continue

        review_pct = exam_df[review_col].fillna(0).mean() * 100
        metrics.append((f"% Revisó {exam_key}", f"{review_pct:.1f}%"))

    if not metrics:
        return

    first_row = metrics[:4]
    second_row = metrics[4:8]

    cols = st.columns(len(first_row))
    for col, (label, value) in zip(cols, first_row):
        col.metric(label, value)

    if second_row:
        cols = st.columns(len(second_row))
        for col, (label, value) in zip(cols, second_row):
            col.metric(label, value)


def render_historical_main_metrics(filtered_df: pd.DataFrame) -> None:
    """Renderiza las métricas principales para vista histórica."""
    total_students = len(filtered_df)
    total_semesters = filtered_df["SEMESTRE"].nunique()
    total_careers = filtered_df["CARRERA"].nunique()
    approved_pct = (filtered_df["ESTADO"] == "AP").mean() * 100

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Registros", total_students)
    col2.metric("Semestres", total_semesters)
    col3.metric("Carreras", total_careers)
    col4.metric("Aprobados (%)", f"{approved_pct:.1f}%")


# ============== Componentes de gráficos de estado ==============

def build_state_distribution_df(filtered_df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
    """Construye el DataFrame para el gráfico de distribución por estado."""
    state_counts = filtered_df["ESTADO"].value_counts()
    state_percent = filtered_df["ESTADO"].value_counts(normalize=True) * 100

    state_df_plot = state_counts.rename_axis("ESTADO").reset_index(name="Cantidad")
    state_df_plot["Porcentaje"] = (
        state_df_plot["Cantidad"] / state_df_plot["Cantidad"].sum()
    ) * 100
    state_df_plot["ESTADO"] = pd.Categorical(
        state_df_plot["ESTADO"],
        categories=STATE_ORDER,
        ordered=True,
    )
    state_df_plot = state_df_plot.sort_values("ESTADO")
    state_df_plot["ESTADO_LABEL"] = state_df_plot["ESTADO"].map(STATE_LABELS)

    return state_counts, state_percent, state_df_plot


def render_state_distribution_chart(state_df_plot: pd.DataFrame, title: str = "Estudiantes por estado") -> None:
    """Renderiza el gráfico de distribución por estado."""
    st.subheader(title)
    fig = px.bar(
        state_df_plot,
        x="ESTADO_LABEL",
        y="Porcentaje",
        color="ESTADO",
        text=state_df_plot["Porcentaje"].map(lambda value: f"{value:.1f}%"),
        color_discrete_map=STATE_COLORS,
        custom_data=["ESTADO", "Cantidad", "Porcentaje"],
    )

    fig.update_traces(
        hovertemplate=(
            "Estado: %{customdata[0]}<br>"
            "Cantidad: %{customdata[1]}<br>"
            "Porcentaje: %{customdata[2]:.2f}%<extra></extra>"
        )
    )

    fig.update_layout(
        xaxis_title="Estado",
        yaxis_title="Porcentaje (%)",
        showlegend=False,
    )

    fig.update_yaxes(ticksuffix="%")

    st.plotly_chart(fig, width="stretch")


def render_state_distribution_table(state_counts: pd.Series, state_percent: pd.Series) -> None:
    """Renderiza la tabla de distribución por estado en un expander."""
    with st.expander("Distribución por estado", expanded=False):
        state_df = pd.DataFrame(
            {
                "Estado": state_counts.index.map(lambda value: STATE_LABELS.get(value, value)),
                "Abreviación": state_counts.index,
                "Cantidad": state_counts.values,
                "Porcentaje (%)": state_percent.round(2).values,
            }
        )
        st.dataframe(state_df, width="stretch", hide_index=True)


# ============== Componentes de distribución SIT ==============

def render_sit_distribution(filtered_df: pd.DataFrame, title: str = "Estudiantes por veces tomada") -> None:
    """Renderiza el gráfico de distribución por SIT."""
    st.subheader(title)

    sit_counts = (
        filtered_df["SIT"]
        .value_counts()
        .sort_index()
        .reset_index()
    )

    sit_counts.columns = ["SIT", "Cantidad"]
    sit_counts["Porcentaje"] = (
        sit_counts["Cantidad"] / sit_counts["Cantidad"].sum() * 100
    )

    fig = px.bar(
        sit_counts,
        x="SIT",
        y="Porcentaje",
        text=sit_counts["Porcentaje"].map(lambda x: f"{x:.1f}%"),
        color_discrete_sequence=["#7CC2F3"],
        custom_data=["Cantidad", "Porcentaje"],
    )

    fig.update_traces(
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "Veces tomada: %{x}<br>"
            "Cantidad: %{customdata[0]}<br>"
            "Porcentaje: %{customdata[1]:.2f}%<extra></extra>"
        ),
        marker_line_width=0,
    )

    fig.update_layout(
        xaxis_title="Veces tomada (SIT)",
        yaxis_title="Porcentaje (%)",
        showlegend=False,
    )

    fig.update_yaxes(ticksuffix="%", range=[0, 110])

    st.plotly_chart(fig, width="stretch")


# ============== Componentes de estudiantes por carrera ==============

def render_students_by_career_and_state(
    filtered_df: pd.DataFrame,
) -> list[str]:
    """Renderiza el gráfico de estudiantes por carrera."""
    st.subheader("Estudiantes por carrera")

    grouped = (
        filtered_df.groupby(["CARRERA", "ESTADO"])
        .size()
        .reset_index(name="Cantidad")
    )

    totals = (
        grouped.groupby("CARRERA", as_index=False)["Cantidad"]
        .sum()
        .rename(columns={"Cantidad": "Total"})
    )

    grouped = grouped.merge(totals, on="CARRERA", how="left")
    grouped["ESTADO"] = pd.Categorical(
        grouped["ESTADO"],
        categories=STATE_ORDER,
        ordered=True,
    )

    grouped["CARRERA_SHORT"] = grouped["CARRERA"].astype(str).apply(
        lambda x: x[:20] + "..." if len(x) > 20 else x
    )

    totals["CARRERA_SHORT"] = totals["CARRERA"].astype(str).apply(
        lambda x: x[:20] + "..." if len(x) > 20 else x
    )

    # Usar el valor del radio button para ordenar
    sort_order = st.session_state.career_sort_order
    
    if sort_order == "approved":
        career_summary = (
            filtered_df.groupby("CARRERA")
            .agg(
                Total=("ESTADO", "size"),
                Aprobados=("ESTADO", lambda s: (s == "AP").sum()),
            )
            .reset_index()
        )
        career_summary["Porcentaje_AP"] = (
            career_summary["Aprobados"] / career_summary["Total"] * 100
        )
        career_summary = career_summary.merge(totals[["CARRERA", "CARRERA_SHORT"]], on="CARRERA")
        career_order = career_summary.sort_values("Porcentaje_AP", ascending=False)["CARRERA_SHORT"].tolist()
    else:
        career_order = totals.sort_values("Total", ascending=False)["CARRERA_SHORT"].tolist()

    fig = px.bar(
        grouped,
        x="Cantidad",
        y="CARRERA_SHORT",
        color="ESTADO",
        orientation="h",
        color_discrete_map=STATE_COLORS,
        category_orders={"CARRERA_SHORT": career_order, "ESTADO": STATE_ORDER},
        custom_data=["CARRERA", "ESTADO", "Cantidad", "Total"],
    )

    fig.update_traces(
        hovertemplate=(
            "Carrera: %{customdata[0]}<br>"
            "Estado: %{customdata[1]}<br>"
            "Cantidad: %{customdata[2]}<br>"
            "Total carrera: %{customdata[3]}<extra></extra>"
        )
    )

    num_carreras = filtered_df["CARRERA"].nunique()
    dynamic_height = max(400, num_carreras * 25)

    fig.update_layout(
        xaxis_title="Número de estudiantes",
        yaxis_title="",
        barmode="stack",
        height=dynamic_height,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=0.15,
            xanchor="right",
        ),
    )

    # Agregar anotaciones con el total de estudiantes por carrera
    for career in career_order:
        total = totals[totals['CARRERA_SHORT'] == career]['Total'].values[0]
        fig.add_annotation(
            x=total,
            y=career,
            text=f'{total}',
            showarrow=False,
            xanchor='left',
            xshift=5,
            font=dict(size=10, color='black')
        )

    st.plotly_chart(fig, width="stretch", key="students_by_career_chart")

    return career_order


def render_approved_percentage_by_career(
    filtered_df: pd.DataFrame,
    career_order: list[str],
) -> None:
    """Renderiza el gráfico de porcentaje de aprobados por carrera."""
    st.subheader("Aprobados por carrera")
    
    # Usar el valor del radio button para ordenar
    sort_order = st.session_state.career_sort_order

    career_summary = (
        filtered_df.groupby("CARRERA")
        .agg(
            Total=("ESTADO", "size"),
            Aprobados=("ESTADO", lambda s: (s == "AP").sum()),
        )
        .reset_index()
    )

    career_summary["Porcentaje_AP"] = (
        career_summary["Aprobados"] / career_summary["Total"] * 100
    )

    career_summary["CARRERA_SHORT"] = career_summary["CARRERA"].astype(str).apply(
        lambda x: x[:20] + "..." if len(x) > 20 else x
    )

    if sort_order == "approved":
        career_order = career_summary.sort_values("Porcentaje_AP", ascending=False)["CARRERA_SHORT"].tolist()

    fig = px.bar(
        career_summary,
        x="Porcentaje_AP",
        y="CARRERA_SHORT",
        orientation="h",
        text=career_summary["Porcentaje_AP"].map(lambda x: f"{x:.1f}%"),
        category_orders={"CARRERA_SHORT": career_order},
        custom_data=["CARRERA", "Aprobados", "Total", "Porcentaje_AP"],
        color_discrete_sequence=["#B7E4C7"],
        opacity=0.6,
    )

    fig.update_traces(
        textposition="outside",
        cliponaxis=False,
        marker_line_width=0,
        hovertemplate=(
            "Carrera: %{customdata[0]}<br>"
            "Aprobados: %{customdata[1]}<br>"
            "Total carrera: %{customdata[2]}<br>"
            "Porcentaje AP: %{customdata[3]:.2f}%<extra></extra>"
        )
    )

    num_carreras = filtered_df["CARRERA"].nunique()
    dynamic_height = max(400, num_carreras * 25)

    fig.update_layout(
        xaxis_title="Aprobados (%)",
        yaxis_title="",
        showlegend=False,
        height=dynamic_height,
    )

    fig.update_xaxes(range=[0, 110], ticksuffix="%")
    fig.add_vline(
        x=60,
        line_dash="dash",
        line_color="#888888",
        line_width=2,
        annotation_text="60%",
        annotation_position="top",
        layer="below",
    )

    st.plotly_chart(fig, width="stretch", key="approved_by_career_chart")


# ============== Componentes de detalle de semestre ==============

def render_totals(df: pd.DataFrame) -> None:
    """Renderiza el gráfico de totales principales."""
    st.subheader("Totales principales")

    rows = []
    for col in ["TOTAL TEORICO", "PRACTICO", "NOTA FINAL"]:
        if col not in df.columns:
            continue

        avg = float(df[col].dropna().mean()) if not df[col].dropna().empty else 0.0
        rows.append(
            {
                "Componente": col,
                "Promedio": avg,
                "Porcentaje": avg,
                "Color": TOTALS_COMPONENT_COLORS[col],
            }
        )

    chart_df = pd.DataFrame(rows)
    if chart_df.empty:
        return

    fig = px.bar(
        chart_df,
        x="Componente",
        y="Porcentaje",
        color="Componente",
        text=chart_df["Porcentaje"].map(lambda x: f"{x:.1f}%"),
        color_discrete_map={row["Componente"]: row["Color"] for _, row in chart_df.iterrows()},
        custom_data=["Promedio", "Porcentaje"],
        opacity=0.85,
    )

    fig.update_traces(
        textposition="outside",
        cliponaxis=False,
        marker_line_width=0,
        hovertemplate=(
            "Componente: %{x}<br>"
            "Porcentaje: %{customdata[1]:.2f}%<extra></extra>"
        ),
    )

    fig.update_layout(
        xaxis_title="Componente",
        yaxis_title="Porcentaje (%)",
        showlegend=False,
    )

    fig.update_yaxes(range=[0, 110], ticksuffix="%")
    st.plotly_chart(fig, width="stretch")


def render_theory(df: pd.DataFrame) -> None:
    """Renderiza el gráfico de componentes teóricos."""
    st.subheader("Componentes teóricos", help="Los promedios se calculan solo con estudiantes que sí dieron el examen.")
    st.caption("Selecciona un componente para ver el detalle por temas en el gráfico de abajo.")
    
    rows = []

    if "TOTAL TEORICO" in df.columns:
        rows.append(("TOTAL TEORICO", float(df["TOTAL TEORICO"].mean())))

    if "PARCIAL" in df.columns:
        rows.append(("PARCIAL", mean_exam(df, "PARCIAL", "1E")))

    if "FINAL" in df.columns:
        rows.append(("FINAL", mean_exam(df, "FINAL", "2E")))

    if "MEJORAMIENTO" in df.columns:
        rows.append(("MEJORAMIENTO", mean_exam(df, "MEJORAMIENTO", "3E")))

    chart_df = pd.DataFrame(rows, columns=["Componente", "Promedio"])
    if chart_df.empty:
        return

    chart_df["Porcentaje"] = chart_df["Promedio"]
    chart_df["Color"] = chart_df["Componente"].map(THEORY_COMPONENT_COLORS)

    fig = px.bar(
        chart_df,
        x="Componente",
        y="Porcentaje",
        color="Componente",
        text=chart_df["Porcentaje"].map(lambda x: f"{x:.1f}%"),
        color_discrete_map={row["Componente"]: row["Color"] for _, row in chart_df.iterrows()},
        custom_data=["Componente", "Promedio", "Porcentaje"],
        opacity=0.85,
    )

    fig.update_traces(
        textposition="outside",
        cliponaxis=False,
        marker_line_width=0,
        hovertemplate=(
            "Componente: %{customdata[0]}<br>"
            "Promedio bruto: %{customdata[1]:.2f}<br>"
            "Porcentaje: %{customdata[2]:.2f}%<extra></extra>"
        ),
    )

    fig.update_layout(
        xaxis_title="Componente teórico",
        yaxis_title="Porcentaje (%)",
        showlegend=False,
    )

    fig.update_yaxes(range=[0, 110], ticksuffix="%")

    event = st.plotly_chart(
        fig,
        width="stretch",
        key="theory_components_chart",
        on_select="rerun",
        selection_mode="points",
    )

    if event and event.selection.points:
        selected_component = event.selection.points[0]["customdata"][0]
        selected_exam = component_to_exam(selected_component)
        if selected_exam is not None:
            st.session_state.selected_exam_detail = selected_exam
            st.session_state.topics_expander_expanded = True


def render_practical(df: pd.DataFrame, semester: str) -> None:
    """Renderiza el gráfico de componentes prácticos."""
    st.subheader("Componentes prácticos")
    
    practical_max_map = load_practical_max_map_for_semester(semester)

    rows = []

    for col in ["PRACTICO", "TALLERES", "PARTICIPACION"]:
        if col not in df.columns:
            continue

        max_value = float(practical_max_map.get(col, 100.0 if col == "PRACTICO" else 80.0 if col == "TALLERES" else 20.0))
        avg = float(df[col].dropna().mean()) if not df[col].dropna().empty else 0.0

        rows.append(
            {
                "Componente": col,
                "Promedio": avg,
                "Maximo": max_value,
                "Porcentaje": (avg / max_value * 100) if max_value else 0.0,
            }
        )

    chart_df = pd.DataFrame(rows)
    if chart_df.empty:
        return

    chart_df["Color"] = chart_df["Componente"].map(PRACTICAL_COMPONENT_COLORS)

    fig = px.bar(
        chart_df,
        x="Componente",
        y="Porcentaje",
        color="Componente",
        text=chart_df["Porcentaje"].map(lambda x: f"{x:.1f}%"),
        color_discrete_map={row["Componente"]: row["Color"] for _, row in chart_df.iterrows()},
        custom_data=["Promedio", "Maximo", "Porcentaje"],
        opacity=0.85,
    )

    fig.update_traces(
        textposition="outside",
        cliponaxis=False,
        marker_line_width=0,
        hovertemplate=(
            "Componente: %{x}<br>"
            "Promedio bruto: %{customdata[0]:.2f}<br>"
            "Máximo: %{customdata[1]:.2f}<br>"
            "Porcentaje: %{customdata[2]:.2f}%<extra></extra>"
        ),
    )

    fig.update_layout(
        xaxis_title="Componente práctico",
        yaxis_title="Porcentaje (%)",
        showlegend=False,
    )

    fig.update_yaxes(range=[0, 110], ticksuffix="%")
    st.plotly_chart(fig, width="stretch")


def render_topics(df: pd.DataFrame, semester: str) -> None:
    """Renderiza el gráfico de detalle por temas."""
    topic_max = load_topic_max_map_for_semester(semester)
    topic_knowledge_map = load_topic_knowledge_map_for_semester(semester)

    topic_columns = [col for col in df.columns if col.upper().startswith("TEMA")]
    if not topic_columns:
        st.caption("No hay columnas de temas en este semestre.")
        return

    import re
    exams = sorted(set(re.search(r"\d+[A-Z]", str(col).upper()).group() for col in topic_columns))

    default_exam = st.session_state.get("selected_exam_detail")
    if default_exam not in exams:
        default_exam = exams[0]
    selected_exam = default_exam
    selected_exam_label = EXAM_LABELS.get(selected_exam, selected_exam)

    if "topics_expander_expanded" not in st.session_state:
        st.session_state.topics_expander_expanded = False

    exp = st.expander(
        f"Detalle por temas del examen: {selected_exam_label}",
        expanded=st.session_state.topics_expander_expanded,
    )
    with exp:
        st.caption("💡 Para cambiar de examen, haz click sobre el componente teórico correspondiente en el gráfico de arriba.")
        
        rows = []
        mask = valid_exam_mask(df, selected_exam)

        exam_col = f"EXAMEN {selected_exam}"
        if exam_col in df.columns:
            exam_series = df.loc[mask, exam_col].dropna()
            if selected_exam == "3E":
                exam_series = exam_series[exam_series > 0]

            exam_avg = float(exam_series.mean()) if not exam_series.empty else 0.0
            rows.append(("PROMEDIO DEL EXAMEN", exam_avg, 100.0, ""))

        selected_topic_columns = [col for col in topic_columns if selected_exam in str(col).upper()]
        topic_groups = group_topic_columns_by_base(selected_topic_columns)

        for base_topic, base_columns in topic_groups.items():
            topic_totals = df.loc[mask, base_columns].fillna(0).sum(axis=1)
            avg = float(topic_totals.mean()) if not topic_totals.empty else 0.0

            metadata_max = topic_max.get(base_topic)
            if metadata_max is not None:
                max_value = float(metadata_max)
            else:
                observed_max = topic_totals.max() if not topic_totals.empty else 0.0
                max_value = float(observed_max) if pd.notna(observed_max) and observed_max > 0 else 100.0

            knowledge_text = format_knowledge_list(topic_knowledge_map.get(base_topic, []))
            rows.append((base_topic, avg, max_value, knowledge_text))

        chart_df = pd.DataFrame(rows, columns=["Elemento", "Promedio", "Maximo", "Conocimientos"])
        if chart_df.empty:
            st.caption("No hay datos para ese examen.")
            return

        chart_df["Porcentaje"] = chart_df["Promedio"] / chart_df["Maximo"] * 100
        chart_df["ElementoLabel"] = chart_df["Elemento"]

        chart_df["KnowledgeText"] = chart_df.apply(
            lambda row: ""
            if row["Elemento"] == "PROMEDIO DEL EXAMEN"
            else (
                str(row["Conocimientos"]).strip()
                if str(row["Conocimientos"]).strip()
                else "Sin conocimientos"
            ),
            axis=1,
        )
        chart_df["PercentText"] = chart_df["Porcentaje"].map(lambda x: f"{x:.1f}%")

        colors = []
        topic_color_index = 0
        for _, row in chart_df.iterrows():
            if row["Elemento"] == "PROMEDIO DEL EXAMEN":
                colors.append("#CDB4DB")
            else:
                colors.append(TOPIC_COLORS[topic_color_index % len(TOPIC_COLORS)])
                topic_color_index += 1

        chart_df["Color"] = colors
        chart_df["LegendLabel"] = chart_df.apply(
            lambda row: "Examen = 100"
            if row["Elemento"] == "PROMEDIO DEL EXAMEN"
            else f"{row['Elemento']}: máx {row['Maximo']:.0f}",
            axis=1,
        )

        fig = px.bar(
            chart_df,
            x="ElementoLabel",
            y="Porcentaje",
            color="LegendLabel",
            text="PercentText",
            color_discrete_map={row["LegendLabel"]: row["Color"] for _, row in chart_df.iterrows()},
            custom_data=["Elemento", "Conocimientos", "Promedio", "Maximo", "Porcentaje"],
            opacity=0.85,
        )

        fig.update_traces(
            textposition="outside",
            cliponaxis=False,
            marker_line_width=0,
            textfont=dict(size=11),
            textangle=0,
            hovertemplate=(
                "Promedio: %{customdata[2]:.2f}<br>"
                "Máximo: %{customdata[3]:.2f}<br>"
                "Porcentaje: %{customdata[4]:.2f}%<extra></extra>"
            ),
        )
        fig.add_scatter(
            x=chart_df["ElementoLabel"],
            y=chart_df["Porcentaje"] / 2,
            mode="text",
            text=chart_df["KnowledgeText"],
            textposition="middle center",
            textfont=dict(size=13),
            hoverinfo="skip",
            showlegend=False,
        )

        fig.update_layout(
            xaxis_title=f"{selected_exam} = {selected_exam_label}",
            uniformtext_minsize=12,
            uniformtext_mode="hide",
            yaxis_title="Porcentaje (%)",
            legend_title_text=None,
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1,
            ),
        )

        fig.update_yaxes(ticksuffix="%")
        st.plotly_chart(fig, width="stretch")


# ============== Componentes históricos ==============

def build_historical_state_distribution(filtered_df: pd.DataFrame) -> pd.DataFrame:
    """Construye la distribución de estados para datos históricos."""
    grouped = (
        filtered_df.groupby(["SEMESTRE", "ESTADO"])
        .size()
        .reset_index(name="Cantidad")
    )

    semester_totals = (
        grouped.groupby("SEMESTRE", as_index=False)["Cantidad"]
        .sum()
        .rename(columns={"Cantidad": "Total"})
    )

    grouped = grouped.merge(semester_totals, on="SEMESTRE", how="left")
    grouped["Porcentaje"] = grouped["Cantidad"] / grouped["Total"] * 100
    grouped["ESTADO"] = pd.Categorical(grouped["ESTADO"], categories=STATE_ORDER, ordered=True)
    grouped["ESTADO_LABEL"] = grouped["ESTADO"].map(STATE_LABELS)

    from src.shared.utils import semester_sort_key
    semester_order = sorted(grouped["SEMESTRE"].astype(str).unique().tolist(), key=semester_sort_key)
    grouped["SEMESTRE"] = pd.Categorical(grouped["SEMESTRE"], categories=semester_order, ordered=True)
    grouped = grouped.sort_values(["SEMESTRE", "ESTADO"])

    return grouped


def render_historical_state_chart(grouped: pd.DataFrame) -> None:
    """Renderiza el gráfico de tendencia histórica por estado."""
    st.subheader("Tendencia histórica por estado")

    semester_order = [str(value) for value in grouped["SEMESTRE"].cat.categories]

    ap_line_df = (
        grouped[grouped["ESTADO"] == "AP"][["SEMESTRE", "Porcentaje"]]
        .copy()
        .rename(columns={"Porcentaje": "Porcentaje_AP"})
    )
    ap_line_df["SEMESTRE"] = ap_line_df["SEMESTRE"].astype(str)

    fig = px.bar(
        grouped.assign(SEMESTRE=grouped["SEMESTRE"].astype(str)),
        x="SEMESTRE",
        y="Porcentaje",
        color="ESTADO",
        color_discrete_map=STATE_COLORS,
        category_orders={
            "SEMESTRE": semester_order,
            "ESTADO": STATE_ORDER,
        },
        custom_data=["ESTADO", "Cantidad", "Porcentaje", "Total"],
    )

    fig.update_traces(
        hovertemplate=(
            "Semestre: %{x}<br>"
            "Estado: %{customdata[0]}<br>"
            "Cantidad: %{customdata[1]}<br>"
            "Porcentaje: %{customdata[2]:.2f}%<br>"
            "Total semestre: %{customdata[3]}<extra></extra>"
        )
    )

    fig.add_scatter(
        x=ap_line_df["SEMESTRE"],
        y=ap_line_df["Porcentaje_AP"],
        mode="lines+markers+text",
        name="AP (%)",
        text=ap_line_df["Porcentaje_AP"].map(lambda x: f"{x:.1f}%"),
        textposition="top center",
        line=dict(color="#5A7D5A", width=3),
        marker=dict(size=8, color="#5A7D5A"),
        hovertemplate=(
            "Semestre: %{x}<br>"
            "AP (%): %{y:.2f}%<extra></extra>"
        ),
    )

    fig.update_layout(
        xaxis_title="Semestre",
        yaxis_title="Porcentaje (%)",
        barmode="stack",
        xaxis=dict(
            type="category",
            categoryorder="array",
            categoryarray=semester_order,
        ),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.18,
            xanchor="center",
            x=0.5,
        ),
    )

    fig.update_yaxes(ticksuffix="%")

    event = st.plotly_chart(
        fig,
        width="stretch",
        key="historical_state_chart",
        on_select="rerun",
        selection_mode="points",
    )

    if event and event.selection.points:
        selected_semester = event.selection.points[0]["x"]
        st.session_state.selected_year = int(selected_semester.split("-")[0])
        st.session_state.selected_term = int(selected_semester.split("-")[1])
        st.switch_page("pages/2_Resumen_general.py")


def render_historical_state_table(grouped: pd.DataFrame) -> None:
    """Renderiza la tabla de detalle histórico por semestre y estado."""
    with st.expander("Detalle por semestre y estado", expanded=False):
        detail_df = grouped.copy()
        detail_df["Estado"] = detail_df["ESTADO"].map(STATE_LABELS)
        detail_df = detail_df[["SEMESTRE", "Estado", "ESTADO", "Cantidad", "Porcentaje", "Total"]]
        detail_df.columns = ["Semestre", "Estado", "Abreviación", "Cantidad", "Porcentaje (%)", "Total semestre"]
        detail_df["Porcentaje (%)"] = detail_df["Porcentaje (%)"].round(2)
        st.dataframe(detail_df, width="stretch", hide_index=True)


def render_historical_student_counts_chart(grouped: pd.DataFrame) -> None:
    """Renderiza el gráfico de cantidad de estudiantes por semestre."""
    st.subheader("Cantidad de estudiantes por semestre")

    semester_order = [str(value) for value in grouped["SEMESTRE"].cat.categories]

    totals = (
        grouped.groupby("SEMESTRE", as_index=False)["Cantidad"]
        .sum()
        .rename(columns={"Cantidad": "Total"})
    )

    totals["SEMESTRE"] = totals["SEMESTRE"].astype(str)

    fig = px.bar(
        grouped.assign(SEMESTRE=grouped["SEMESTRE"].astype(str)),
        x="SEMESTRE",
        y="Cantidad",
        color="ESTADO",
        color_discrete_map=STATE_COLORS,
        category_orders={
            "SEMESTRE": semester_order,
            "ESTADO": STATE_ORDER,
        },
        custom_data=["ESTADO", "Cantidad", "Porcentaje", "Total"],
    )

    fig.add_scatter(
        x=totals["SEMESTRE"],
        y=totals["Total"],
        mode="text",
        text=totals["Total"],
        textposition="top center",
        showlegend=False,
        hoverinfo="skip",
    )

    fig.update_layout(
        xaxis_title="Semestre",
        yaxis_title="Número de estudiantes",
        barmode="stack",
        xaxis=dict(
            type="category",
            categoryorder="array",
            categoryarray=semester_order,
        ),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.18,
            xanchor="center",
            x=0.5,
        ),
    )

    st.plotly_chart(fig, width="stretch")
