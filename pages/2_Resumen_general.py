from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(layout="wide")

DATASETS_PATH = Path("datasets")

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


def load_available_datasets() -> list[Path]:
    files = list(DATASETS_PATH.glob("estadisticas_FP_*.xlsx"))
    files.sort()
    return files


def extract_semester_name(file_path: Path) -> str:
    return file_path.stem.replace("estadisticas_FP_", "")


@st.cache_data
def load_data(path: Path) -> pd.DataFrame:
    return pd.read_excel(path)


def get_dataset_map() -> dict[str, Path]:
    datasets = load_available_datasets()
    return {extract_semester_name(file_path): file_path for file_path in datasets}


def get_default_semester(dataset_map: dict[str, Path]) -> str:
    available_semesters = sorted(dataset_map.keys(), reverse=True)

    selected_year = st.session_state.get("selected_year")
    selected_term = st.session_state.get("selected_term")

    if selected_year is not None and selected_term is not None:
        candidate = f"{selected_year}-{selected_term}"
        if candidate in dataset_map:
            return candidate

    return available_semesters[0]

def render_sidebar(dataset_map: dict[str, Path]) -> tuple[str, list[str], list, list[str], list[str]]:
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

    df = load_data(dataset_map[selected_semester]).copy()

    with st.sidebar:
        career_options = (
            sorted(df["CARRERA"].dropna().astype(str).unique().tolist())
            if "CARRERA" in df.columns
            else []
        )
        selected_careers = st.multiselect("Carrera", options=career_options)

        sit_options = (
            sorted(df["SIT"].dropna().unique().tolist())
            if "SIT" in df.columns
            else []
        )
        selected_sit = st.multiselect("Veces tomada (SIT)", options=sit_options)

        state_options = (
            sorted(df["ESTADO"].dropna().astype(str).unique().tolist())
            if "ESTADO" in df.columns
            else []
        )
        selected_states = st.multiselect("Estado", options=state_options)

        parallel_options = (
            sorted(df["PARALELO"].dropna().astype(str).unique().tolist())
            if "PARALELO" in df.columns
            else []
        )
        selected_parallels = st.multiselect("Paralelo", options=parallel_options)

    return selected_semester, selected_careers, selected_sit, selected_states, selected_parallels


def apply_filters(
    df: pd.DataFrame,
    selected_careers: list[str],
    selected_sit: list,
    selected_states: list[str],
    selected_parallels: list[str],
) -> pd.DataFrame:
    filtered_df = df.copy()

    if selected_careers:
        filtered_df = filtered_df[filtered_df["CARRERA"].astype(str).isin(selected_careers)]

    if selected_sit:
        filtered_df = filtered_df[filtered_df["SIT"].isin(selected_sit)]

    if selected_states:
        filtered_df = filtered_df[filtered_df["ESTADO"].astype(str).isin(selected_states)]

    if selected_parallels:
        filtered_df = filtered_df[filtered_df["PARALELO"].astype(str).isin(selected_parallels)]

    return filtered_df


def render_main_metrics(filtered_df: pd.DataFrame, selected_semester: str) -> None:
    st.subheader(f"Indicadores principales del semestre: {selected_semester}")

    aprobados_pct = (filtered_df["ESTADO"] == "AP").mean() * 100

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Estudiantes", len(filtered_df))
    col2.metric("Paralelos", filtered_df["PARALELO"].nunique())
    col3.metric("Carreras", filtered_df["COD"].nunique())
    col4.metric("Aprobados (%)", f"{aprobados_pct:.1f}%")


def build_state_distribution_df(filtered_df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
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


def render_state_distribution_chart(state_df_plot: pd.DataFrame) -> None:
    st.subheader("Distribución de estudiantes por estado")
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
    with st.expander("Distribución por estado", expanded=False):
        state_df = pd.DataFrame(
            {
                "Estado": state_counts.index.map(lambda value: STATE_LABELS.get(value, value)),
                "Abreviación": state_counts.index,
                "Cantidad": state_counts.values,
                "Porcentaje (%)": state_percent.round(2).values,
            }
        )
        st.dataframe(state_df, width="stretch")


def render_sit_distribution(filtered_df: pd.DataFrame) -> None:
    st.subheader("Distribución por veces tomada")

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
        color_discrete_sequence=["#7CC2F3"],  # azul pastel suave
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


def render_students_by_career_and_state(filtered_df: pd.DataFrame) -> list[str]:
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

    career_order = totals.sort_values("Total", ascending=False)["CARRERA_SHORT"].tolist()
    totals_sorted = totals.sort_values("Total", ascending=False)

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

    fig.add_scatter(
        x=totals_sorted["Total"],
        y=totals_sorted["CARRERA_SHORT"],
        mode="text",
        text=totals_sorted["Total"],
        textposition="middle right",
        showlegend=False,
        hoverinfo="skip",
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
            # x=0.5,
        ),
    )

    st.plotly_chart(fig, width="stretch")
    return career_order

def render_approved_percentage_by_career(
    filtered_df: pd.DataFrame,
    career_order: list[str],
) -> None:
    st.subheader("Aprobados por carrera")

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

    fig = px.bar(
        career_summary,
        x="Porcentaje_AP",
        y="CARRERA_SHORT",
        orientation="h",
        text=career_summary["Porcentaje_AP"].map(lambda x: f"{x:.1f}%"),
        category_orders={"CARRERA_SHORT": career_order},
        custom_data=["CARRERA", "Aprobados", "Total", "Porcentaje_AP"],
        color_discrete_sequence=["#B7E4C7"],  # verde pastel (AP)
        opacity=0.6,  # transparencia
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
        line_color="#888888",  # gris suave
        line_width=2,
        annotation_text="60%",
        annotation_position="top",
        layer="below",
    )

    st.plotly_chart(fig, width="stretch")

def main() -> None:
    st.title("Resumen general")

    dataset_map = get_dataset_map()

    if not dataset_map:
        st.warning("No hay datasets disponibles. Primero genera un consolidado para un semestre.")
        st.stop()

    (
        selected_semester,
        selected_careers,
        selected_sit,
        selected_states,
        selected_parallels,
    ) = render_sidebar(dataset_map)

    df = load_data(dataset_map[selected_semester]).copy()

    filtered_df = apply_filters(
        df=df,
        selected_careers=selected_careers,
        selected_sit=selected_sit,
        selected_states=selected_states,
        selected_parallels=selected_parallels,
    )

    if filtered_df.empty:
        st.warning("No hay datos para los filtros seleccionados.")
        st.stop()

    render_main_metrics(filtered_df, selected_semester)

    state_counts, state_percent, state_df_plot = build_state_distribution_df(filtered_df)
    col_left, col_right = st.columns(2)
    with col_left:
        render_state_distribution_chart(state_df_plot)
    with col_right:
        render_sit_distribution(filtered_df)
    
    render_state_distribution_table(state_counts, state_percent)
    
    col_left, col_right = st.columns(2)

    with col_left:
        career_order = render_students_by_career_and_state(filtered_df)

    with col_right:
        render_approved_percentage_by_career(filtered_df, career_order)
    # 


main()