from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATASETS_PATH = Path("datasets")
CAREERS_FILE = Path("metadata/Carreras.xlsx")

STATE_COLORS = {
    "AP": "#B7E4C7",
    "RP": "#D3D3D3",
    "RT": "#FFE8A1",
    "PF": "#F8C8DC",
}

STATE_LABELS = {
    "AP": "Aprobado",
    "RP": "Reprobado",
    "RT": "Retirado",
    "PF": "Perdido por falta",
}

STATE_ORDER = ["AP", "RP", "RT", "PF"]


@st.cache_data
def load_careers_catalog() -> pd.DataFrame:
    careers_df = pd.read_excel(CAREERS_FILE).copy()
    careers_df.columns = [str(col).strip().upper() for col in careers_df.columns]

    expected_cols = {"COD", "CARRERA", "FACULTAD"}
    missing = expected_cols - set(careers_df.columns)
    if missing:
        raise ValueError(f"Faltan columnas en Carreras.xlsx: {sorted(missing)}")

    careers_df["COD"] = careers_df["COD"].astype(str).str.strip()
    careers_df["CARRERA"] = careers_df["CARRERA"].astype(str).str.strip()
    careers_df["FACULTAD"] = careers_df["FACULTAD"].astype(str).str.strip()

    return careers_df[["COD", "CARRERA", "FACULTAD"]].drop_duplicates()


def load_available_datasets() -> list[Path]:
    files = list(DATASETS_PATH.glob("estadisticas_FP_*.xlsx"))
    files.sort()
    return files


def extract_semester_name(file_path: Path) -> str:
    return file_path.stem.replace("estadisticas_FP_", "")


def semester_sort_key(semester: str) -> tuple[int, int]:
    year_str, term_str = semester.split("-")
    return int(year_str), int(term_str)


@st.cache_data
def load_historical_data() -> pd.DataFrame:
    dataset_files = load_available_datasets()
    if not dataset_files:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []

    for file_path in dataset_files:
        semester = extract_semester_name(file_path)
        df = pd.read_excel(file_path).copy()
        df["SEMESTRE"] = semester
        frames.append(df)

    historical_df = pd.concat(frames, ignore_index=True)

    careers_df = load_careers_catalog()

    if "FACULTAD" not in historical_df.columns:
        historical_df = historical_df.merge(
            careers_df[["COD", "FACULTAD"]],
            on="COD",
            how="left",
        )
    else:
        missing_facultad_mask = historical_df["FACULTAD"].isna() | (
            historical_df["FACULTAD"].astype(str).str.strip() == ""
        )
        if missing_facultad_mask.any():
            faculty_map = careers_df[["COD", "FACULTAD"]].drop_duplicates()
            historical_df = historical_df.drop(columns=["FACULTAD"]).merge(
                faculty_map,
                on="COD",
                how="left",
            )

    return historical_df


def build_semester_options(df: pd.DataFrame) -> list[str]:
    semesters = sorted(df["SEMESTRE"].dropna().astype(str).unique().tolist(), key=semester_sort_key)
    return semesters


def render_sidebar_filters(df: pd.DataFrame) -> tuple[list[str], list[str], list[str], list]:
    semesters = build_semester_options(df)

    with st.sidebar:
        st.header("Filtros")

        selected_semesters = st.select_slider(
            "Rango de semestres",
            options=semesters,
            value=(semesters[0], semesters[-1]),
        )

        faculty_options = sorted(df["FACULTAD"].dropna().astype(str).unique().tolist())
        selected_faculties = st.multiselect(
            "Facultad",
            options=faculty_options,
            default=[],
        )

        if selected_faculties:
            careers_source = df[df["FACULTAD"].astype(str).isin(selected_faculties)].copy()
        else:
            careers_source = df.copy()

        career_options = sorted(careers_source["CARRERA"].dropna().astype(str).unique().tolist())
        selected_careers = st.multiselect(
            "Carrera",
            options=career_options,
            default=[],
        )

        sit_options = sorted(df["SIT"].dropna().unique().tolist())
        selected_sit = st.multiselect(
            "Veces tomada (SIT)",
            options=sit_options,
            default=[],
        )

    semester_start, semester_end = selected_semesters
    semester_range = [
        semester
        for semester in semesters
        if semester_sort_key(semester_start) <= semester_sort_key(semester) <= semester_sort_key(semester_end)
    ]

    return semester_range, selected_faculties, selected_careers, selected_sit


def apply_historical_filters(
    df: pd.DataFrame,
    semester_range: list[str],
    selected_faculties: list[str],
    selected_careers: list[str],
    selected_sit: list,
) -> pd.DataFrame:
    filtered_df = df.copy()

    filtered_df = filtered_df[filtered_df["SEMESTRE"].isin(semester_range)]

    if selected_faculties:
        filtered_df = filtered_df[filtered_df["FACULTAD"].astype(str).isin(selected_faculties)]

    if selected_careers:
        filtered_df = filtered_df[filtered_df["CARRERA"].astype(str).isin(selected_careers)]

    if selected_sit:
        filtered_df = filtered_df[filtered_df["SIT"].isin(selected_sit)]

    return filtered_df


def build_historical_state_distribution(filtered_df: pd.DataFrame) -> pd.DataFrame:
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

    semester_order = sorted(grouped["SEMESTRE"].astype(str).unique().tolist(), key=semester_sort_key)
    grouped["SEMESTRE"] = pd.Categorical(grouped["SEMESTRE"], categories=semester_order, ordered=True)
    grouped = grouped.sort_values(["SEMESTRE", "ESTADO"])

    return grouped


def render_historical_main_metrics(filtered_df: pd.DataFrame) -> None:
    total_students = len(filtered_df)
    total_semesters = filtered_df["SEMESTRE"].nunique()
    total_careers = filtered_df["CARRERA"].nunique()
    approved_pct = (filtered_df["ESTADO"] == "AP").mean() * 100

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Registros", total_students)
    col2.metric("Semestres", total_semesters)
    col3.metric("Carreras", total_careers)
    col4.metric("Aprobados (%)", f"{approved_pct:.1f}%")


def render_historical_state_chart(grouped: pd.DataFrame) -> None:
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
        st.switch_page("pages/1_Resumen_general.py")

def render_historical_state_table(grouped: pd.DataFrame) -> None:
    with st.expander("Detalle por semestre y estado", expanded=False):
        detail_df = grouped.copy()
        detail_df["Estado"] = detail_df["ESTADO"].map(STATE_LABELS)
        detail_df = detail_df[["SEMESTRE", "Estado", "ESTADO", "Cantidad", "Porcentaje", "Total"]]
        detail_df.columns = ["Semestre", "Estado", "Abreviación", "Cantidad", "Porcentaje (%)", "Total semestre"]
        detail_df["Porcentaje (%)"] = detail_df["Porcentaje (%)"].round(2)
        st.dataframe(detail_df, width="stretch", hide_index=True)

def render_historical_student_counts_chart(grouped: pd.DataFrame) -> None:
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


def main() -> None:
    st.title("Análisis histórico")

    historical_df = load_historical_data()

    if historical_df.empty:
        st.warning("No hay datasets históricos disponibles. Primero genera consolidados en datasets/.")
        st.stop()

    semester_range, selected_faculties, selected_careers, selected_sit = render_sidebar_filters(historical_df)

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

    render_historical_main_metrics(filtered_df)

    grouped = build_historical_state_distribution(filtered_df)
    render_historical_state_chart(grouped)
    render_historical_student_counts_chart(grouped)
    render_historical_state_table(grouped)


main()