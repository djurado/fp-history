from pathlib import Path
import re

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(layout="wide")

DATASETS_PATH = Path("datasets")
METADATA_FILE = Path("metadata/metadata_estadisticas_FP.xlsx")
METADATA_SHEET_PREFIX = "TPL_"

EXAM_LABELS = {
    "1E": "Examen parcial",
    "2E": "Examen final",
    "3E": "Mejoramiento",
}

THEORY_COMPONENT_COLORS = {
    "TOTAL TEORICO": "#F4A261",
    "PARCIAL": "#F7B267",
    "FINAL": "#F79D65",
    "MEJORAMIENTO": "#E76F51",
}

PRACTICAL_COMPONENT_COLORS = {
    "PRACTICO": "#A8DADC",
    "TALLERES": "#90E0EF",
    "PARTICIPACION": "#BDE0FE",
}

TOTALS_COMPONENT_COLORS = {
    "TOTAL TEORICO": "#F4A261",
    "PRACTICO": "#A8DADC",
    "NOTA FINAL": "#CDB4DB",
}

TOPIC_COLORS = [
    "#F9C5D1",
    "#F7D6BF",
    "#FAEDCB",
    "#CDEAC0",
    "#BDE0FE",
    "#D7C5F2",
]


@st.cache_data
def load_data(path: Path) -> pd.DataFrame:
    return pd.read_excel(path)


@st.cache_data
def load_topic_max_map_for_semester(semester_name: str) -> dict[str, float]:
    sheet_name = f"{METADATA_SHEET_PREFIX}{semester_name.replace('-', '_')}"

    try:
        metadata_df = pd.read_excel(METADATA_FILE, sheet_name=sheet_name)
    except ValueError:
        st.warning(
            f"No se encontraron metadatos para el semestre {semester_name}. "
            f"No se podrán calcular los máximos por tema para ese semestre."
        )
        return {}
    except FileNotFoundError:
        st.warning(
            "No se encontró el archivo de metadatos. "
            "No se podrán calcular los máximos por tema."
        )
        return {}
    except Exception as exc:
        st.warning(
            f"Ocurrió un problema al cargar los metadatos del semestre {semester_name}: {exc}"
        )
        return {}

    if metadata_df.empty:
        st.warning(
            f"La hoja de metadatos del semestre {semester_name} está vacía."
        )
        return {}

    max_row = metadata_df.iloc[0]
    topic_max_map: dict[str, float] = {}
    pattern = re.compile(r"^TEMA\s+\d+[A-Z]-\d+$")

    for col in metadata_df.columns:
        if not pattern.match(str(col)):
            continue

        value = max_row.get(col)
        if pd.isna(value):
            continue

        try:
            topic_max_map[str(col)] = float(value)
        except Exception:
            continue

    return topic_max_map

@st.cache_data
def load_practical_max_map_for_semester(semester_name: str) -> dict[str, float]:
    sheet_name = f"{METADATA_SHEET_PREFIX}{semester_name.replace('-', '_')}"

    default_map = {
        "TALLERES": 80.0,
        "PARTICIPACION": 20.0,
        "PRACTICO": 100.0,
    }

    try:
        metadata_df = pd.read_excel(METADATA_FILE, sheet_name=sheet_name)
    except Exception:
        return default_map

    if metadata_df.empty:
        return default_map

    max_row = metadata_df.iloc[0].copy()
    result = default_map.copy()

    for column_name in ["PRACTICO", "TALLERES", "PARTICIPACION"]:
        if column_name not in metadata_df.columns:
            continue

        raw_value = max_row.get(column_name)
        if pd.isna(raw_value):
            continue

        try:
            result[column_name] = float(raw_value)
        except Exception:
            continue

    return result

def load_available_datasets() -> list[Path]:
    return sorted(DATASETS_PATH.glob("estadisticas_FP_*.xlsx"))


def extract_semester_name(path: Path) -> str:
    return path.stem.replace("estadisticas_FP_", "")


def get_dataset_map() -> dict[str, Path]:
    return {extract_semester_name(path): path for path in load_available_datasets()}

def get_default_semester(dataset_map: dict[str, Path]) -> str:
    available_semesters = sorted(dataset_map.keys(), reverse=True)

    selected_year = st.session_state.get("selected_year")
    selected_term = st.session_state.get("selected_term")

    if selected_year is not None and selected_term is not None:
        candidate = f"{selected_year}-{selected_term}"
        if candidate in dataset_map:
            return candidate

    return available_semesters[0]

def valid_exam_mask(df: pd.DataFrame, exam_key: str) -> pd.Series:
    status_col = f"ESTADO {exam_key}"
    if status_col not in df.columns:
        return pd.Series([False] * len(df), index=df.index)
    return df[status_col] == 1


def mean_exam(df: pd.DataFrame, col: str, exam: str) -> float:
    if col not in df.columns:
        return 0.0

    mask = valid_exam_mask(df, exam)
    series = df.loc[mask, col].dropna()

    if exam == "3E":
        series = series[series > 0]

    return float(series.mean()) if not series.empty else 0.0


def find_review_columns(df: pd.DataFrame) -> list[str]:
    return [col for col in df.columns if str(col).startswith("REVISADO_X_ESTUDIANTE")]


def render_page_legend() -> None:
    st.info(
        "Los promedios teóricos y por tema se calculan solo con estudiantes que sí dieron el examen."
    )


def apply_filters(
    df: pd.DataFrame,
    carreras: list[str],
    sit: list,
    estados: list[str],
    paralelos: list[str],
) -> pd.DataFrame:
    filtered_df = df.copy()

    if carreras:
        filtered_df = filtered_df[filtered_df["CARRERA"].astype(str).isin(carreras)]

    if sit:
        filtered_df = filtered_df[filtered_df["SIT"].isin(sit)]

    if estados:
        filtered_df = filtered_df[filtered_df["ESTADO"].astype(str).isin(estados)]

    if paralelos:
        filtered_df = filtered_df[filtered_df["PARALELO"].astype(str).isin(paralelos)]

    return filtered_df

def render_main_metrics(df: pd.DataFrame, semester: str) -> None:
    st.subheader(f"Indicadores principales del semestre: {semester}")

    metrics = []

    metrics.append(("Estudiantes", len(df)))

    if "PARALELO" in df.columns:
        metrics.append(("Paralelos", df["PARALELO"].nunique()))

    if "CARRERA" in df.columns:
        metrics.append(("Carreras", df["CARRERA"].nunique()))
    elif "COD" in df.columns:
        metrics.append(("Carreras", df["COD"].nunique()))

    if "ESTADO" in df.columns and len(df):
        approved_pct = (df["ESTADO"] == "AP").mean() * 100
        metrics.append(("Aprobados (%)", f"{approved_pct:.1f}%"))

    if "TRABAJOS_EXTRA" in df.columns:
        extra_students = int((df["TRABAJOS_EXTRA"].fillna(0) == 1).sum())
        metrics.append(("Estudiantes (trabajo extra)", extra_students))

    review_column_map = {
        "1E": "REVISADO_X_ESTUDIANTE 1E",
        "2E": "REVISADO_X_ESTUDIANTE 2E",
        "3E": "REVISADO_X_ESTUDIANTE 3E",
    }

    for exam_key, review_col in review_column_map.items():
        status_col = f"ESTADO {exam_key}"

        if review_col not in df.columns or status_col not in df.columns:
            continue

        exam_df = df.loc[df[status_col] == 1]
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


def render_totals(df: pd.DataFrame) -> None:
    st.subheader("Totales principales (%)")

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
            "Promedio bruto: %{customdata[0]:.2f}<br>"
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
    st.subheader("Componentes teóricos (%)")

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
        custom_data=["Promedio", "Porcentaje"],
        opacity=0.85,
    )

    fig.update_traces(
        textposition="outside",
        cliponaxis=False,
        marker_line_width=0,
        hovertemplate=(
            "Componente: %{x}<br>"
            "Promedio bruto: %{customdata[0]:.2f}<br>"
            "Porcentaje: %{customdata[1]:.2f}%<extra></extra>"
        ),
    )

    fig.update_layout(
        xaxis_title="Componente teórico",
        yaxis_title="Porcentaje (%)",
        showlegend=False,
    )

    fig.update_yaxes(range=[0, 110], ticksuffix="%")
    st.plotly_chart(fig, width="stretch")


def render_practical(df: pd.DataFrame, semester: str) -> None:
    st.subheader("Componentes prácticos (%)")

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
    st.subheader("Promedio por tema (%)")
    st.caption("Selecciona un examen para ver el promedio del examen y de cada tema normalizados por su puntaje máximo.")

    topic_max = load_topic_max_map_for_semester(semester)

    topic_columns = [col for col in df.columns if re.match(r"^TEMA", str(col))]
    if not topic_columns:
        st.caption("No hay columnas de temas en este semestre.")
        return

    exams = sorted(set(re.search(r"\d+[A-Z]", col).group() for col in topic_columns))

    selected_exam = st.radio(
        "Examen",
        exams,
        format_func=lambda x: f"{x} = {EXAM_LABELS[x]}",
        horizontal=True,
    )
    st.markdown(f"**Gráfico del {selected_exam} = {EXAM_LABELS[selected_exam]}**")

    rows = []
    mask = valid_exam_mask(df, selected_exam)

    exam_col = f"EXAMEN {selected_exam}"
    if exam_col in df.columns:
        exam_series = df.loc[mask, exam_col].dropna()
        if selected_exam == "3E":
            exam_series = exam_series[exam_series > 0]

        exam_avg = float(exam_series.mean()) if not exam_series.empty else 0.0
        rows.append(("PROMEDIO DEL EXAMEN", exam_avg, 100.0))

    for col in topic_columns:
        if selected_exam not in col:
            continue

        series = df.loc[mask, col].dropna()
        avg = float(series.mean()) if not series.empty else 0.0
        max_value = float(topic_max.get(col, 100.0))
        rows.append((col, avg, max_value))

    chart_df = pd.DataFrame(rows, columns=["Elemento", "Promedio", "Maximo"])
    if chart_df.empty:
        st.caption("No hay datos para ese examen.")
        return

    chart_df["Porcentaje"] = chart_df["Promedio"] / chart_df["Maximo"] * 100

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
        x="Elemento",
        y="Porcentaje",
        color="LegendLabel",
        text=chart_df["Porcentaje"].map(lambda x: f"{x:.1f}%"),
        color_discrete_map={row["LegendLabel"]: row["Color"] for _, row in chart_df.iterrows()},
        custom_data=["Promedio", "Maximo", "Porcentaje"],
        opacity=0.85,
    )

    fig.update_traces(
        textposition="outside",
        cliponaxis=False,
        marker_line_width=0,
        hovertemplate=(
            "Elemento: %{x}<br>"
            "Promedio: %{customdata[0]:.2f}<br>"
            "Máximo: %{customdata[1]:.2f}<br>"
            "Porcentaje: %{customdata[2]:.2f}%<extra></extra>"
        ),
    )

    fig.update_layout(
        xaxis_title=f"{selected_exam} = {EXAM_LABELS[selected_exam]}",
        yaxis_title="Porcentaje (%)",
        legend_title_text="Puntajes máximos",
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,
        ),
    )

    fig.update_yaxes(range=[0, 110], ticksuffix="%")
    st.plotly_chart(fig, width="stretch")

def main() -> None:
    st.title("Detalle de semestre")
    render_page_legend()

    dataset_map = get_dataset_map()
    if not dataset_map:
        st.warning("No hay datasets disponibles. Primero genera un consolidado.")
        return

    available_semesters = sorted(dataset_map.keys(), reverse=True)
    default_semester = get_default_semester(dataset_map)

    selected_semester = st.sidebar.selectbox(
        "Semestre",
        available_semesters,
        index=available_semesters.index(default_semester),
    )
    selected_year_str, selected_term_str = selected_semester.split("-")
    st.session_state.selected_year = int(selected_year_str)
    st.session_state.selected_term = int(selected_term_str)
    df = load_data(dataset_map[selected_semester])

    career_options = sorted(df["CARRERA"].dropna().astype(str).unique()) if "CARRERA" in df.columns else []
    sit_options = sorted(df["SIT"].dropna().unique()) if "SIT" in df.columns else []
    state_options = sorted(df["ESTADO"].dropna().astype(str).unique()) if "ESTADO" in df.columns else []
    parallel_options = sorted(df["PARALELO"].dropna().astype(str).unique()) if "PARALELO" in df.columns else []

    selected_careers = st.sidebar.multiselect("Carrera", career_options)
    selected_sit = st.sidebar.multiselect("Veces tomada (SIT)", sit_options)
    selected_states = st.sidebar.multiselect("Estado", state_options)
    selected_parallels = st.sidebar.multiselect("Paralelo", parallel_options)

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

    render_main_metrics(filtered_df, selected_semester)
    render_totals(filtered_df)

    col1, col2 = st.columns(2)
    with col1:
        render_theory(filtered_df)
    with col2:
        render_practical(filtered_df, selected_semester)

    render_topics(filtered_df, selected_semester)


main()