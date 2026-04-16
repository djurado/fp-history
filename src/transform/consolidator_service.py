from pathlib import Path
import re

import pandas as pd

from config import (
    CAREERS_FILE,
    DATASETS_PATH,
    DATASET_FILENAME_TEMPLATE,
    STATISTICS_METADATA_FILE,
)


THEORY_EXAMS = ["PARCIAL", "FINAL", "MEJORAMIENTO"]
REQUIRED_COLUMNS = ["MATRICULA", "COD", "SIT", "ESTADO"]


def _extract_parallel(file_name: str) -> str | None:
    match = re.search(r"_P(\d+)", file_name.upper())
    if not match:
        return None
    return str(int(match.group(1)))


def _load_careers_catalog() -> pd.DataFrame:
    careers_df = pd.read_excel(CAREERS_FILE)

    careers_df.columns = [str(col).strip().upper() for col in careers_df.columns]

    if "COD" not in careers_df.columns:
        raise ValueError("El archivo Carreras.xlsx no contiene la columna COD.")

    possible_name_columns = ["CARRERA", "NOMBRE_CARRERA", "NOMBRE", "DESCRIPCION"]
    career_name_col = next((col for col in possible_name_columns if col in careers_df.columns), None)

    if career_name_col is None:
        raise ValueError("No se encontró columna de nombre de carrera en Carreras.xlsx.")

    careers_df = careers_df[["COD", career_name_col]].copy()
    careers_df = careers_df.rename(columns={career_name_col: "CARRERA"})
    careers_df["COD"] = careers_df["COD"].astype(str).str.strip()
    careers_df["CARRERA"] = careers_df["CARRERA"].astype(str).str.strip()

    careers_df["CARRERA_TIPO"] = careers_df["COD"].apply(
        lambda code: "ING" if str(code).upper().startswith("CI-") else "LIC"
    )

    return careers_df.drop_duplicates(subset=["COD"])


def _ensure_required_columns(df: pd.DataFrame) -> None:
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas obligatorias: {', '.join(missing)}")


def _add_parallel_column(df: pd.DataFrame, file_name: str) -> pd.DataFrame:
    result = df.copy()

    if "PARALELO" not in result.columns:
        result["PARALELO"] = _extract_parallel(file_name)

    result["PARALELO"] = (
        result["PARALELO"]
        .astype(str)
        .str.strip()
        .str.replace(r"^P0*", "", regex=True)
    )

    if result["PARALELO"].isna().any() or (result["PARALELO"] == "").any():
        raise ValueError(f"No se pudo determinar el paralelo en {file_name}")

    return result


def _calculate_total_theory(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    for col in THEORY_EXAMS:
        if col not in result.columns:
            raise ValueError(f"Falta la columna {col}")
        result[col] = pd.to_numeric(result[col], errors="coerce")

    result["TOTAL TEORICO"] = result[THEORY_EXAMS].apply(
        lambda row: row.nlargest(2).mean(),
        axis=1,
    )

    return result


def _calculate_final_grade(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    if "PRACTICO" not in result.columns:
        raise ValueError("Falta PRACTICO")

    result["PRACTICO"] = pd.to_numeric(result["PRACTICO"], errors="coerce")

    result["NOTA FINAL"] = result["TOTAL TEORICO"] * 0.7 + result["PRACTICO"] * 0.3

    return result


def _merge_careers(df: pd.DataFrame) -> pd.DataFrame:
    careers_df = _load_careers_catalog()

    result = df.copy()
    result["COD"] = result["COD"].astype(str).str.strip()

    result = result.merge(careers_df, on="COD", how="left")

    if result["CARRERA"].isna().any():
        missing = result.loc[result["CARRERA"].isna(), "COD"].unique()
        raise ValueError(f"No se pudieron mapear carreras: {missing}")

    return result

def _load_metadata_columns(year: int, term: int) -> list[str]:
    sheet_name = f"TPL_{year}_{term}"

    try:
        metadata_df = pd.read_excel(STATISTICS_METADATA_FILE, sheet_name=sheet_name)
    except ValueError as exc:
        raise ValueError(f"No existe la hoja de metadata {sheet_name}.") from exc

    columns = [str(col).strip() for col in metadata_df.columns if str(col).strip()]

    if not columns:
        raise ValueError(f"La hoja {sheet_name} no contiene columnas válidas.")

    return columns

def _insert_after(cols: list[str], ref: str, new_cols: list[str]) -> list[str]:
    result = cols.copy()

    if ref in result:
        idx = result.index(ref) + 1
        for c in new_cols:
            if c not in result:
                result.insert(idx, c)
                idx += 1
    else:
        result.extend([c for c in new_cols if c not in result])

    return result


def _order_columns_from_metadata(df: pd.DataFrame, year: int, term: int) -> pd.DataFrame:
    base_cols = _load_metadata_columns(year, term)

    if "PARALELO" not in base_cols:
        base_cols.insert(0, "PARALELO")

    base_cols = _insert_after(base_cols, "COD", ["CARRERA", "CARRERA_TIPO"])

    for col in ["TOTAL TEORICO", "NOTA FINAL"]:
        if col not in base_cols:
            base_cols.append(col)

    existing = [c for c in base_cols if c in df.columns]
    remaining = [c for c in df.columns if c not in existing]

    return df[existing + remaining]


def build_semester_dataset(validation_results: list, year: int, term: int) -> pd.DataFrame:
    dfs = []

    for result in validation_results:
        if not result["is_valid"]:
            continue

        df = result["corrected_df"]
        file_name = result["file_name"]

        if df is None:
            continue

        _ensure_required_columns(df)
        df = _add_parallel_column(df, file_name)

        dfs.append(df)

    if not dfs:
        raise ValueError("No hay datos válidos")

    final_df = pd.concat(dfs, ignore_index=True)

    final_df = _calculate_total_theory(final_df)
    final_df = _calculate_final_grade(final_df)
    final_df = _merge_careers(final_df)
    final_df = _order_columns_from_metadata(final_df, year, term)

    return final_df


def save_semester_dataset(df: pd.DataFrame, year: int, term: int) -> Path:
    DATASETS_PATH.mkdir(exist_ok=True)

    filename = DATASET_FILENAME_TEMPLATE.format(year=year, term=term)
    path = DATASETS_PATH / filename

    df.to_excel(path, index=False)

    return path