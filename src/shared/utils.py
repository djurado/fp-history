"""Funciones utilitarias compartidas entre todas las páginas."""

import re
import unicodedata
from pathlib import Path

import pandas as pd
import streamlit as st

from src.shared.constants import (
    DATASETS_PATH,
    STATISTICS_METADATA_FILE as METADATA_FILE,
    METADATA_SHEET_PREFIX,
    KNOWLEDGE_LABEL_FIXES,
    VALID_KNOWLEDGES,
)


# ============== Funciones de carga de datos ==============

def load_available_datasets() -> list[Path]:
    """Carga la lista de archivos de datasets disponibles."""
    files = list(DATASETS_PATH.glob("estadisticas_FP_*.xlsx"))
    files.sort()
    return files


def extract_semester_name(file_path: Path) -> str:
    """Extrae el nombre del semestre de un path de archivo."""
    return file_path.stem.replace("estadisticas_FP_", "")


@st.cache_data
def load_data(path: Path) -> pd.DataFrame:
    """Carga un archivo Excel como DataFrame."""
    return pd.read_excel(path)


def get_dataset_map() -> dict[str, Path]:
    """Retorna un mapa de semestres a sus archivos."""
    datasets = load_available_datasets()
    return {extract_semester_name(file_path): file_path for file_path in datasets}


def get_default_semester(dataset_map: dict[str, Path]) -> str:
    """Obtiene el semestre por defecto basado en el estado de sesión."""
    available_semesters = sorted(dataset_map.keys(), reverse=True)

    selected_year = st.session_state.get("selected_year")
    selected_term = st.session_state.get("selected_term")

    if selected_year is not None and selected_term is not None:
        candidate = f"{selected_year}-{selected_term}"
        if candidate in dataset_map:
            return candidate

    return available_semesters[0]


# ============== Funciones de carga de metadata ==============

@st.cache_data
def load_careers_catalog() -> pd.DataFrame:
    """Carga el catálogo de carreras desde el archivo Excel."""
    from src.shared.constants import CAREERS_FILE
    
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


@st.cache_data
def load_historical_data() -> pd.DataFrame:
    """Carga todos los datasets históricos en un solo DataFrame."""
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


@st.cache_data
def load_topic_max_map_for_semester(semester_name: str) -> dict[str, float]:
    """Carga el mapa de máximos por tema para un semestre."""
    from src.shared.constants import STATISTICS_METADATA_FILE
    
    sheet_name = f"{METADATA_SHEET_PREFIX}{semester_name.replace('-', '_')}"

    try:
        metadata_df = pd.read_excel(STATISTICS_METADATA_FILE, sheet_name=sheet_name)
    except ValueError:
        return {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}

    if metadata_df.empty:
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
    """Carga el mapa de máximos para componentes prácticos."""
    from src.shared.constants import STATISTICS_METADATA_FILE
    
    sheet_name = f"{METADATA_SHEET_PREFIX}{semester_name.replace('-', '_')}"

    default_map = {
        "TALLERES": 80.0,
        "PARTICIPACION": 20.0,
        "PRACTICO": 100.0,
    }

    try:
        metadata_df = pd.read_excel(STATISTICS_METADATA_FILE, sheet_name=sheet_name)
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


@st.cache_data
def load_topic_knowledge_map_for_semester(semester_name: str) -> dict[str, list[str]]:
    """Carga el mapa de conocimientos por tema."""
    from src.shared.constants import STATISTICS_METADATA_FILE
    
    sheet_name = f"{METADATA_SHEET_PREFIX}{semester_name.replace('-', '_')}"

    try:
        metadata_df = pd.read_excel(STATISTICS_METADATA_FILE, sheet_name=sheet_name)
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


# ============== Funciones helper ==============

def extract_topic_base(topic_column: str) -> str:
    """Extrae el tema base de un nombre de columna."""
    normalized = str(topic_column).strip().upper()
    match = re.match(r"^(TEMA\s+\d+[A-Z]-\d+)", normalized)
    return match.group(1) if match else normalized


def group_topic_columns_by_base(columns: list[str]) -> dict[str, list[str]]:
    """Agrupa columnas de temas por su base."""
    grouped: dict[str, list[str]] = {}

    for column in columns:
        base_topic = extract_topic_base(column)
        grouped.setdefault(base_topic, []).append(column)

    return dict(sorted(grouped.items()))


def format_knowledge_list(knowledge_items: list[str]) -> str:
    """Formatea una lista de conocimientos para mostrar."""
    if not knowledge_items:
        return ""
    return "<br>".join(knowledge_items[:2])


def semester_sort_key(semester: str) -> tuple[int, int]:
    """Función de ordenamiento para semestres."""
    year_str, term_str = semester.split("-")
    return int(year_str), int(term_str)


def parallel_sort_key(parallel: str) -> tuple[int, str]:
    """Función de ordenamiento para paralelos (numérico)."""
    try:
        return (int(parallel), "")
    except (ValueError, TypeError):
        return (0, str(parallel))


def build_semester_options(df: pd.DataFrame) -> list[str]:
    """Construye la lista de opciones de semestres."""
    semesters = sorted(df["SEMESTRE"].dropna().astype(str).unique().tolist(), key=semester_sort_key)
    return semesters


# ============== Funciones de filtrado ==============

def apply_filters(
    df: pd.DataFrame,
    carreras: list[str] | None = None,
    sit: list | None = None,
    estados: list[str] | None = None,
    paralelos: list[str] | None = None,
) -> pd.DataFrame:
    """Aplica filtros al DataFrame."""
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


def apply_historical_filters(
    df: pd.DataFrame,
    semester_range: list[str],
    selected_faculties: list[str] | None = None,
    selected_careers: list[str] | None = None,
    selected_sit: list | None = None,
) -> pd.DataFrame:
    """Aplica filtros históricos al DataFrame."""
    filtered_df = df.copy()

    filtered_df = filtered_df[filtered_df["SEMESTRE"].isin(semester_range)]

    if selected_faculties:
        filtered_df = filtered_df[filtered_df["FACULTAD"].astype(str).isin(selected_faculties)]

    if selected_careers:
        filtered_df = filtered_df[filtered_df["CARRERA"].astype(str).isin(selected_careers)]

    if selected_sit:
        filtered_df = filtered_df[filtered_df["SIT"].isin(selected_sit)]

    return filtered_df


# ============== Funciones de examen ==============

def valid_exam_mask(df: pd.DataFrame, exam_key: str) -> pd.Series:
    """Retorna una máscara para estudiantes con examen válido."""
    status_col = f"ESTADO {exam_key}"
    if status_col not in df.columns:
        return pd.Series([False] * len(df), index=df.index)
    return df[status_col] == 1


def mean_exam(df: pd.DataFrame, col: str, exam: str) -> float:
    """Calcula el promedio de un examen."""
    if col not in df.columns:
        return 0.0

    mask = valid_exam_mask(df, exam)
    series = df.loc[mask, col].dropna()

    if exam == "3E":
        series = series[series > 0]

    return float(series.mean()) if not series.empty else 0.0


def component_to_exam(component_name: str) -> str | None:
    """Convierte nombre de componente a clave de examen."""
    mapping = {
        "PARCIAL": "1E",
        "FINAL": "2E",
        "MEJORAMIENTO": "3E",
    }
    return mapping.get(str(component_name).strip().upper())


# ============== Funciones de estado ==============

def init_session_state_defaults() -> None:
    """Inicializa valores por defecto en el estado de sesión."""
    if "selected_year" not in st.session_state:
        st.session_state.selected_year = None
    if "selected_term" not in st.session_state:
        st.session_state.selected_term = None
    if "selected_exam_detail" not in st.session_state:
        st.session_state.selected_exam_detail = "1E"
    if "topics_expander_expanded" not in st.session_state:
        st.session_state.topics_expander_expanded = True
    if "career_sort_order" not in st.session_state:
        st.session_state.career_sort_order = "total"