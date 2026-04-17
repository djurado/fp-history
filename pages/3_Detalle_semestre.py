from pathlib import Path
import re
import unicodedata

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


VALID_KNOWLEDGES = {
    "STRINGS",
    "LISTAS",
    "FUNCIONES",
    "IF / FOR",
    "WHILE",
    "TUPLAS",
    "CONJUNTOS",
    "DICCIONARIOS",
    "NUMPY",
    "ARCHIVOS",
    "PANDAS",
    "RANDOM",
    "LOGICA Y DEPURACION",
    "LOGICA",
}

KNOWLEDGE_LABEL_FIXES = {
    "LOGICA Y DEPURACION": "Lógica",
    "LOGICA": "Lógica",
    "IF / FOR": "If / For",
    "WHILE": "While",
    "STRINGS": "Strings",
    "LISTAS": "Listas",
    "FUNCIONES": "Funciones",
    "TUPLAS": "Tuplas",
    "CONJUNTOS": "Conjuntos",
    "DICCIONARIOS": "Diccionarios",
    "NUMPY": "Numpy",
    "ARCHIVOS": "Archivos",
    "PANDAS": "Pandas",
    "RANDOM": "Random",
}


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
    pattern = re.compile(r"^TEMA\s+\d+[A-Z]-\d+.*$")

    for col in metadata_df.columns:
        col_name = str(col).strip().upper()
        if not pattern.match(col_name):
            continue

        value = max_row.get(col)
        if pd.isna(value):
            continue

        try:
            base_topic = extract_topic_base(col_name)
            topic_max_map[base_topic] = topic_max_map.get(base_topic, 0.0) + float(value)
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


# --- Helper functions for knowledge extraction ---

def normalize_knowledge_value(value: str) -> str:
    text = str(value).strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    normalized = text.upper()

    if normalized == "LOGICA Y DEPURACION":
        normalized = "LOGICA"

    return KNOWLEDGE_LABEL_FIXES.get(normalized, text.strip())


@st.cache_data
def load_topic_knowledge_map_for_semester(semester_name: str) -> dict[str, list[str]]:
    sheet_name = f"{METADATA_SHEET_PREFIX}{semester_name.replace('-', '_')}"

    try:
        metadata_df = pd.read_excel(METADATA_FILE, sheet_name=sheet_name)
    except Exception:
        return {}

    if metadata_df.empty or len(metadata_df) <= 1:
        return {}

    topic_columns = [
        col for col in metadata_df.columns
        if re.match(r"^TEMA\s+\d+[A-Z]-\d+.*$", str(col).strip().upper())
    ]

    knowledge_map: dict[str, list[str]] = {}

    for col in topic_columns:
        base_topic = extract_topic_base(col)
        values = metadata_df[col].iloc[1:].dropna().tolist()

        collected: list[str] = knowledge_map.get(base_topic, []).copy()

        for value in values:
            value_str = str(value).strip()
            if not value_str:
                continue

            raw_normalized = unicodedata.normalize("NFKD", value_str)
            raw_normalized = "".join(ch for ch in raw_normalized if not unicodedata.combining(ch)).upper()

            if raw_normalized == "LOGICA Y DEPURACION":
                raw_normalized = "LOGICA"

            if raw_normalized not in VALID_KNOWLEDGES:
                continue

            normalized_value = KNOWLEDGE_LABEL_FIXES.get(raw_normalized, value_str.strip())
            if normalized_value not in collected:
                collected.append(normalized_value)

            if len(collected) == 2:
                break

        if collected:
            knowledge_map[base_topic] = collected[:2]

    return knowledge_map


def format_knowledge_list(knowledge_items: list[str]) -> str:
    if not knowledge_items:
        return ""
    return "<br>".join(knowledge_items[:2])

def load_available_datasets() -> list[Path]:
    return sorted(DATASETS_PATH.glob("estadisticas_FP_*.xlsx"))


def extract_semester_name(path: Path) -> str:
    return path.stem.replace("estadisticas_FP_", "")

def extract_topic_base(topic_column: str) -> str:
    normalized = str(topic_column).strip().upper()
    match = re.match(r"^(TEMA\s+\d+[A-Z]-\d+)", normalized)
    return match.group(1) if match else normalized


def group_topic_columns_by_base(columns: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}

    for column in columns:
        base_topic = extract_topic_base(column)
        grouped.setdefault(base_topic, []).append(column)

    return dict(sorted(grouped.items()))

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


# --- Helper function: component_to_exam ---
def component_to_exam(component_name: str) -> str | None:
    mapping = {
        "PARCIAL": "1E",
        "FINAL": "2E",
        "MEJORAMIENTO": "3E",
    }
    return mapping.get(str(component_name).strip().upper())

def find_review_columns(df: pd.DataFrame) -> list[str]:
    return [col for col in df.columns if str(col).startswith("REVISADO_X_ESTUDIANTE")]


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
    st.subheader(f"Indicadores principales:")

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
    st.subheader("Componentes teóricos", help="Los promedios se calculan solo con estudiantes que sí dieron el examen.")
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
    topic_max = load_topic_max_map_for_semester(semester)
    topic_knowledge_map = load_topic_knowledge_map_for_semester(semester)

    topic_columns = [col for col in df.columns if re.match(r"^TEMA", str(col).strip().upper())]
    if not topic_columns:
        st.caption("No hay columnas de temas en este semestre.")
        return

    exams = sorted(set(re.search(r"\d+[A-Z]", str(col).upper()).group() for col in topic_columns))

    # Determine selected exam from session state (set by theory chart clicks)
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
    with exp:
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

        selected_topic_rows = chart_df[
            chart_df["Elemento"] != "PROMEDIO DEL EXAMEN"
        ][["Elemento", "Conocimientos"]].copy()

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

        fig.update_yaxes( ticksuffix="%")
        st.plotly_chart(fig, width="stretch")
    
    
def main() -> None:
    # Removed initial static title and legend.

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
    st.title(f"Detalle de semestre: {selected_semester}")
    selected_year_str, selected_term_str = selected_semester.split("-")
    st.session_state.selected_year = int(selected_year_str)
    st.session_state.selected_term = int(selected_term_str)

    if "selected_exam_detail" not in st.session_state:
        st.session_state.selected_exam_detail = "1E"
    if st.session_state.selected_exam_detail not in EXAM_LABELS:
        st.session_state.selected_exam_detail = "1E"

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