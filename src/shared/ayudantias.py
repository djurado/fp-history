"""Preparación de datos para insights de ayudantías."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st

from config import BASE_DIR


AYUDA_DATASETS_PATH = BASE_DIR / "datasets" / "ayuda"
ASISTENCIA_AYUDANTIAS_FILE = AYUDA_DATASETS_PATH / "asistencia_2025_2.csv"
CLASES_AYUDANTIAS_FILE = AYUDA_DATASETS_PATH / "clases_2025_2.csv"

DAY_LABELS = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sábado",
    6: "Domingo",
}
DAY_ORDER = list(DAY_LABELS.values())
DAY_TYPE_ORDER = ["Lunes a viernes", "Fin de semana"]
MODALITY_ORDER = ["Presencial", "Virtual", "Sin clasificar"]

ATTENDANCE_REQUIRED_COLUMNS = (
    "fecha",
    "hora",
    "matrícula",
    "estudiante",
    "paralelo",
    "ayudante_clean",
)
CLASSES_REQUIRED_COLUMNS = (
    "fecha",
    "hora",
    "ayudante_clean",
    "lugar",
)


@dataclass(frozen=True)
class AyudantiasData:
    """DataFrames listos para los gráficos de la página."""

    attendance: pd.DataFrame
    sessions: pd.DataFrame
    invalid_attendance_dates: int
    invalid_class_dates: int
    duplicated_attendance_rows: int
    unmatched_attendance_sessions: int


def validate_ayudantias_sources(
    attendance_df: pd.DataFrame,
    classes_df: pd.DataFrame,
) -> list[str]:
    """Valida columnas mínimas de los CSV de ayudantías."""
    issues: list[str] = []

    missing_attendance = [
        column for column in ATTENDANCE_REQUIRED_COLUMNS if column not in attendance_df.columns
    ]
    if missing_attendance:
        issues.append(
            "Faltan columnas en asistencia_2025_2.csv: "
            + ", ".join(missing_attendance)
        )

    missing_classes = [
        column for column in CLASSES_REQUIRED_COLUMNS if column not in classes_df.columns
    ]
    if missing_classes:
        issues.append(
            "Faltan columnas en clases_2025_2.csv: "
            + ", ".join(missing_classes)
        )

    return issues


@st.cache_data
def load_ayudantias_sources(
    attendance_path: Path = ASISTENCIA_AYUDANTIAS_FILE,
    classes_path: Path = CLASES_AYUDANTIAS_FILE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Carga los CSV de ayudantías como texto para preservar matrículas."""
    attendance_df = pd.read_csv(attendance_path, dtype=str).copy()
    classes_df = pd.read_csv(classes_path, dtype=str).copy()
    return attendance_df, classes_df


def prepare_ayudantias_data(
    attendance_df: pd.DataFrame,
    classes_df: pd.DataFrame,
) -> AyudantiasData:
    """Limpia, deduplica y cruza asistencia con clases."""
    attendance = _prepare_attendance(attendance_df)
    classes = _prepare_classes(classes_df)

    invalid_attendance_dates = int(attendance["FECHA_DT"].isna().sum())
    invalid_class_dates = int(classes["FECHA_DT"].isna().sum())

    attendance = attendance.dropna(subset=["FECHA_DT"]).copy()
    classes = classes.dropna(subset=["FECHA_DT"]).copy()

    attendance["FECHA"] = attendance["FECHA_DT"].dt.date
    attendance["FECHA_KEY"] = attendance["FECHA_DT"].dt.strftime("%Y-%m-%d")
    attendance["DIA_NUM"] = attendance["FECHA_DT"].dt.weekday
    attendance["DIA"] = attendance["DIA_NUM"].map(DAY_LABELS)
    attendance["TIPO_DIA"] = attendance["DIA_NUM"].map(_classify_day_type)

    classes["FECHA"] = classes["FECHA_DT"].dt.date
    classes["FECHA_KEY"] = classes["FECHA_DT"].dt.strftime("%Y-%m-%d")
    classes["DIA_NUM"] = classes["FECHA_DT"].dt.weekday
    classes["DIA"] = classes["DIA_NUM"].map(DAY_LABELS)
    classes["TIPO_DIA"] = classes["DIA_NUM"].map(_classify_day_type)
    classes["MODALIDAD"] = classes.apply(
        lambda row: classify_modality(
            place=row["lugar"],
            hour=row["HORA"],
            day_number=row["DIA_NUM"],
        ),
        axis=1,
    )

    duplicated_attendance_rows = int(
        attendance.duplicated(["FECHA_KEY", "HORA", "AYUDANTE_KEY", "MATRICULA"]).sum()
    )
    attendance = attendance.drop_duplicates(
        ["FECHA_KEY", "HORA", "AYUDANTE_KEY", "MATRICULA"]
    ).copy()

    sessions = _consolidate_sessions(classes)
    attendance = attendance.merge(
        sessions[
            [
                "FECHA_KEY",
                "HORA",
                "AYUDANTE_KEY",
                "LUGAR",
                "MODALIDAD",
                "TEMAS",
                "RECURSOS",
            ]
        ],
        on=["FECHA_KEY", "HORA", "AYUDANTE_KEY"],
        how="left",
    )
    attendance["MODALIDAD"] = attendance["MODALIDAD"].fillna("Sin clasificar")
    attendance_sessions = attendance.drop_duplicates(["FECHA_KEY", "HORA", "AYUDANTE_KEY"])
    unmatched_attendance_sessions = int(
        (attendance_sessions["MODALIDAD"] == "Sin clasificar").sum()
    )

    attendance_virtual_schedule_mask = (
        attendance["MODALIDAD"].eq("Sin clasificar")
        & attendance.apply(
            lambda row: _is_virtual_schedule(row["HORA"], row["DIA_NUM"]),
            axis=1,
        )
    )
    attendance.loc[attendance_virtual_schedule_mask, "MODALIDAD"] = "Virtual"
    attendance.loc[attendance["MODALIDAD"].eq("Sin clasificar"), "MODALIDAD"] = "Presencial"

    attendance["LUGAR"] = attendance["LUGAR"].fillna("Sin registro de lugar")
    attendance["TEMAS"] = attendance["TEMAS"].fillna("")
    attendance["RECURSOS"] = attendance["RECURSOS"].fillna("")

    session_attendance_counts = (
        attendance.groupby(["FECHA_KEY", "HORA", "AYUDANTE_KEY"], dropna=False)
        .agg(ASISTENCIAS=("MATRICULA", "nunique"))
        .reset_index()
    )
    sessions = sessions.merge(
        session_attendance_counts,
        on=["FECHA_KEY", "HORA", "AYUDANTE_KEY"],
        how="left",
    )
    sessions["ASISTENCIAS"] = sessions["ASISTENCIAS"].fillna(0).astype(int)

    return AyudantiasData(
        attendance=attendance,
        sessions=sessions,
        invalid_attendance_dates=invalid_attendance_dates,
        invalid_class_dates=invalid_class_dates,
        duplicated_attendance_rows=duplicated_attendance_rows,
        unmatched_attendance_sessions=unmatched_attendance_sessions,
    )


def filter_ayudantias_attendance(
    attendance: pd.DataFrame,
    date_range: tuple[pd.Timestamp, pd.Timestamp] | None = None,
    hours: list[str] | None = None,
    modalities: list[str] | None = None,
    day_types: list[str] | None = None,
) -> pd.DataFrame:
    """Aplica filtros principales a las asistencias deduplicadas."""
    filtered = attendance.copy()

    if date_range is not None:
        start_date, end_date = date_range
        filtered = filtered[
            (filtered["FECHA_DT"] >= pd.Timestamp(start_date))
            & (filtered["FECHA_DT"] <= pd.Timestamp(end_date))
        ]

    if hours:
        filtered = filtered[filtered["HORA"].isin(hours)]

    if modalities:
        filtered = filtered[filtered["MODALIDAD"].isin(modalities)]

    if day_types:
        filtered = filtered[filtered["TIPO_DIA"].isin(day_types)]

    return filtered


def build_attendance_by_hour(attendance: pd.DataFrame) -> pd.DataFrame:
    """Cuenta asistencias por horario."""
    return (
        attendance.groupby("HORA", dropna=False)
        .size()
        .rename("Asistencias")
        .reset_index()
        .sort_values("HORA", key=lambda serie: serie.astype(str))
    )


def build_attendance_day_hour(attendance: pd.DataFrame) -> pd.DataFrame:
    """Cuenta asistencias por día y hora con grilla completa."""
    hours = sorted(attendance["HORA"].dropna().astype(str).unique().tolist())
    index = pd.MultiIndex.from_product(
        [DAY_ORDER, hours],
        names=["DIA", "HORA"],
    )
    counts = (
        attendance.groupby(["DIA", "HORA"], dropna=False)
        .size()
        .rename("Asistencias")
        .reindex(index, fill_value=0)
        .reset_index()
    )
    counts["DIA"] = pd.Categorical(counts["DIA"], categories=DAY_ORDER, ordered=True)
    return counts.sort_values(["DIA", "HORA"], key=_sort_day_hour_columns)


def build_modality_day_type_comparison(attendance: pd.DataFrame) -> pd.DataFrame:
    """Compara asistencias por modalidad y tipo de día."""
    modalities = [
        modality
        for modality in MODALITY_ORDER
        if modality in set(attendance["MODALIDAD"].dropna().astype(str))
    ]
    index = pd.MultiIndex.from_product(
        [DAY_TYPE_ORDER, modalities],
        names=["TIPO_DIA", "MODALIDAD"],
    )
    comparison = (
        attendance.groupby(["TIPO_DIA", "MODALIDAD"], dropna=False)
        .size()
        .rename("Asistencias")
        .reindex(index, fill_value=0)
        .reset_index()
    )
    comparison["TIPO_DIA"] = pd.Categorical(
        comparison["TIPO_DIA"],
        categories=DAY_TYPE_ORDER,
        ordered=True,
    )
    comparison["MODALIDAD"] = pd.Categorical(
        comparison["MODALIDAD"],
        categories=MODALITY_ORDER,
        ordered=True,
    )
    return comparison.sort_values(["TIPO_DIA", "MODALIDAD"])


def build_student_attendance_distribution(attendance: pd.DataFrame) -> pd.DataFrame:
    """Calcula el número de asistencias por estudiante."""
    students = (
        attendance.groupby("MATRICULA", dropna=False)
        .agg(
            Asistencias=("MATRICULA", "size"),
            Estudiante=("ESTUDIANTE", _first_non_empty),
            Paralelo=("PARALELO", _first_non_empty),
        )
        .reset_index()
    )
    students["Etiqueta"] = students["MATRICULA"] + " - " + students["Estudiante"]
    return students.sort_values("Asistencias", ascending=False)


def classify_modality(
    place: object,
    hour: object | None = None,
    day_number: object | None = None,
) -> str:
    """Clasifica modalidad desde lugar, horario y día de la ayudantía."""
    if _is_virtual_schedule(hour, day_number):
        return "Virtual"

    place_text = str(place).strip().lower()
    if not place_text or place_text == "nan":
        return "Sin clasificar"
    if "virtual" in place_text or "teams" in place_text:
        return "Virtual"
    return "Presencial"


def _is_virtual_schedule(hour: object | None, day_number: object | None) -> bool:
    if str(hour).strip() == "19-21":
        return True

    numeric_day = pd.to_numeric(day_number, errors="coerce")
    return pd.notna(numeric_day) and int(numeric_day) >= 5


def _prepare_attendance(attendance_df: pd.DataFrame) -> pd.DataFrame:
    attendance = attendance_df.copy()
    attendance["FECHA_DT"] = _parse_dates(attendance["fecha"])
    attendance["HORA"] = attendance["hora"].astype(str).str.strip()
    attendance["MATRICULA"] = attendance["matrícula"].astype(str).str.strip()
    attendance["ESTUDIANTE"] = attendance["estudiante"].astype(str).str.strip()
    attendance["PARALELO"] = attendance["paralelo"].astype(str).str.strip()
    attendance["AYUDANTE_KEY"] = _normalize_key(attendance["ayudante_clean"])
    return attendance


def _prepare_classes(classes_df: pd.DataFrame) -> pd.DataFrame:
    classes = classes_df.copy()
    classes["FECHA_DT"] = _parse_dates(classes["fecha"])
    classes["HORA"] = classes["hora"].astype(str).str.strip()
    classes["AYUDANTE_KEY"] = _normalize_key(classes["ayudante_clean"])
    classes["lugar"] = classes["lugar"].fillna("").astype(str).str.strip()
    classes["temas"] = _optional_text_column(classes, "temas")
    classes["recurso"] = _optional_text_column(classes, "recurso")
    return classes


def _parse_dates(values: pd.Series) -> pd.Series:
    raw = values.fillna("").astype(str).str.strip()
    raw = raw.str.replace(r"^205-", "2025-", regex=True)
    iso_mask = raw.str.match(r"^\d{4}-\d{1,2}-\d{1,2}$")

    parsed = pd.Series(pd.NaT, index=raw.index, dtype="datetime64[ns]")
    parsed.loc[iso_mask] = pd.to_datetime(
        raw.loc[iso_mask],
        format="%Y-%m-%d",
        errors="coerce",
    )
    parsed.loc[~iso_mask] = pd.to_datetime(
        raw.loc[~iso_mask],
        dayfirst=True,
        errors="coerce",
    )
    return parsed


def _consolidate_sessions(classes: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        classes.groupby(["FECHA_KEY", "HORA", "AYUDANTE_KEY"], dropna=False)
        .agg(
            FECHA_DT=("FECHA_DT", "first"),
            FECHA=("FECHA", "first"),
            DIA_NUM=("DIA_NUM", "first"),
            DIA=("DIA", "first"),
            TIPO_DIA=("TIPO_DIA", "first"),
            LUGAR=("lugar", _join_unique),
            MODALIDAD=("MODALIDAD", _merge_modalities),
            TEMAS=("temas", _join_unique),
            RECURSOS=("recurso", _join_unique),
        )
        .reset_index()
    )
    return grouped.sort_values(["FECHA_DT", "HORA", "AYUDANTE_KEY"])


def _normalize_key(values: pd.Series) -> pd.Series:
    return values.fillna("").astype(str).str.strip().str.lower()


def _optional_text_column(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series("", index=df.index)
    return df[column].fillna("").astype(str).str.strip()


def _classify_day_type(day_number: int) -> str:
    return "Fin de semana" if int(day_number) >= 5 else "Lunes a viernes"


def _merge_modalities(values: pd.Series) -> str:
    collected = set(values.dropna().astype(str))
    if "Virtual" in collected:
        return "Virtual"
    if "Presencial" in collected:
        return "Presencial"
    return "Sin clasificar"


def _join_unique(values: pd.Series) -> str:
    cleaned = []
    for value in values.dropna().astype(str):
        value = value.strip()
        if value and value != "nan" and value not in cleaned:
            cleaned.append(value)
    return " | ".join(cleaned)


def _first_non_empty(values: pd.Series) -> str:
    for value in values.dropna().astype(str):
        value = value.strip()
        if value and value != "nan":
            return value
    return ""


def _sort_day_hour_columns(column: pd.Series) -> pd.Series:
    if column.name == "DIA":
        return column.map({day: index for index, day in enumerate(DAY_ORDER)})
    if column.name == "HORA":
        return column.astype(str)
    return column
