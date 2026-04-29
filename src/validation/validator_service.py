from __future__ import annotations

import re
import unicodedata
from enum import Enum
from io import BytesIO
from typing import Any

import numpy as np
import pandas as pd

from config import STATISTICS_METADATA_FILE, VALID_STATES
from src.validation.models import FileValidationResult, ValidationIssue


VALID_FINAL_STATES = set(VALID_STATES)

COLUMN_PATTERNS = {
    "TEMA": r"^TEMA\s+(\d+[A-Z])\s*-\s*(\d+)$",
    "EXAMEN": r"^EXAMEN\s+(\d+[A-Z])$",
    "ESTADO": r"^ESTADO\s+(\d+[A-Z])$",
    "REVISADO": r"^REVISADO[_\s]+X[_\s]+ESTUDIANTE\s+(\d+[A-Z])$",
    "TEORICO_COMPONENTE": r"^(PARCIAL|FINAL|MEJORAMIENTO)$",
    "PRACTICO": r"^PRACTICO$",
    "TEXTO": r"^(MATRICULA|NOMBRE|COD|ESTADO)(?:\s|_|$)",
    "TALLER": r"^TALLERES?$",
    "PARTICIPACION": r"^PARTICIPACI[OÓ]N$",
    "EXTRA": r"^TRABAJOS[_\s]+EXTRA$",
    "SIT": r"^SIT$",
}


class ColumnType(Enum):
    TEMA = "TEMA"
    EXAMEN = "EXAMEN"
    ESTADO = "ESTADO"
    REVISADO = "REVISADO"
    TEORICO_COMPONENTE = "TEORICO_COMPONENTE"
    PRACTICO = "PRACTICO"
    TEXTO = "TEXTO"
    TALLER = "TALLER"
    PARTICIPACION = "PARTICIPACION"
    EXTRA = "EXTRA"
    SIT = "SIT"
    NUMERIC = "NUMERIC"
    UNKNOWN = "UNKNOWN"


class ColumnInfo:
    def __init__(
        self,
        name: str,
        col_type: ColumnType,
        exam_tag: str | None = None,
        tema_num: int | None = None,
    ) -> None:
        self.name = name
        self.col_type = col_type
        self.exam_tag = exam_tag
        self.tema_num = tema_num


class ColumnClassifier:
    def __init__(self, patterns: dict[str, str]) -> None:
        self.patterns = {key: re.compile(value, re.IGNORECASE) for key, value in patterns.items()}

    def classify(self, col_name: str) -> ColumnInfo:
        match = self.patterns["TEMA"].search(col_name)
        if match:
            return ColumnInfo(
                col_name,
                ColumnType.TEMA,
                exam_tag=match.group(1),
                tema_num=int(match.group(2)),
            )

        match = self.patterns["EXAMEN"].search(col_name)
        if match:
            return ColumnInfo(col_name, ColumnType.EXAMEN, exam_tag=match.group(1))

        match = self.patterns["ESTADO"].search(col_name)
        if match:
            return ColumnInfo(col_name, ColumnType.ESTADO, exam_tag=match.group(1))

        match = self.patterns["REVISADO"].search(col_name)
        if match:
            return ColumnInfo(col_name, ColumnType.REVISADO, exam_tag=match.group(1))

        match = self.patterns["EXTRA"].search(col_name)
        if match:
            return ColumnInfo(col_name, ColumnType.EXTRA)

        match = self.patterns["TALLER"].search(col_name)
        if match:
            return ColumnInfo(col_name, ColumnType.TALLER)

        match = self.patterns["PARTICIPACION"].search(col_name)
        if match:
            return ColumnInfo(col_name, ColumnType.PARTICIPACION)

        match = self.patterns["SIT"].search(col_name)
        if match:
            return ColumnInfo(col_name, ColumnType.SIT)

        match = self.patterns["TEORICO_COMPONENTE"].search(col_name)
        if match:
            return ColumnInfo(col_name, ColumnType.TEORICO_COMPONENTE)

        match = self.patterns["PRACTICO"].search(col_name)
        if match:
            return ColumnInfo(col_name, ColumnType.PRACTICO)

        match = self.patterns["TEXTO"].search(col_name)
        if match:
            return ColumnInfo(col_name, ColumnType.TEXTO)

        return ColumnInfo(col_name, ColumnType.UNKNOWN)


def _normalize_decimal_commas(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace(",", ".").strip()
    return value


def _extract_number_from_text(value: Any) -> Any:
    if pd.isna(value):
        return np.nan
    if isinstance(value, str):
        match = re.search(r"-?\d+(\.\d+)?", value.replace(",", "."))
        return float(match.group()) if match else np.nan
    return value


def _normalize_header_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower().replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_rule_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip().upper()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _build_allowed_map(max_row: pd.Series) -> dict[str, set]:
    allowed: dict[str, set] = {}

    for col, value in max_row.items():
        normalized = _normalize_rule_text(value)
        if not normalized:
            continue

        if re.search(r"\b0\s*O\s*1\b", normalized):
            allowed[col] = {0, 1}
            continue

        if re.search(r"\b1\s*,?\s*2\s*O\s*3\b", normalized):
            allowed[col] = {1, 2, 3}
            continue

        if all(state in normalized for state in VALID_FINAL_STATES):
            allowed[col] = set(VALID_FINAL_STATES)

    return allowed


def _report_mask(
    issues: list[ValidationIssue],
    mask: pd.Series,
    level: str,
    col: str | None,
    message_fn,
    limit: int = 30,
) -> None:
    indexes = np.where(mask)[0][:limit]
    for index in indexes:
        issues.append(ValidationIssue(level, int(index) + 3, col, message_fn(index)))


def _discover_structure(expected_columns: list[str]) -> dict[str, Any]:
    classifier = ColumnClassifier(COLUMN_PATTERNS)
    columns_info: dict[str, ColumnInfo] = {}
    exams: dict[str, dict[str, Any]] = {}
    text_cols: set[str] = set()
    numeric_cols: set[str] = set()
    boolean_cols: set[str] = set()
    unknown_cols: set[str] = set()

    for col_name in expected_columns:
        col_info = classifier.classify(col_name)
        columns_info[col_name] = col_info

        if col_info.col_type == ColumnType.TEXTO:
            text_cols.add(col_name)
        elif col_info.col_type == ColumnType.SIT:
            numeric_cols.add(col_name)
        elif col_info.col_type in {ColumnType.EXTRA, ColumnType.REVISADO}:
            boolean_cols.add(col_name)
        elif col_info.col_type in {
            ColumnType.TEMA,
            ColumnType.EXAMEN,
            ColumnType.TALLER,
            ColumnType.PARTICIPACION,
            ColumnType.TEORICO_COMPONENTE,
            ColumnType.PRACTICO,
        }:
            numeric_cols.add(col_name)
        elif col_info.col_type == ColumnType.ESTADO:
            numeric_cols.add(col_name)
        elif col_info.col_type == ColumnType.UNKNOWN:
            unknown_cols.add(col_name)
        else:
            numeric_cols.add(col_name)

    for col_name, col_info in columns_info.items():
        if col_info.col_type == ColumnType.ESTADO:
            exams.setdefault(
                col_info.exam_tag,
                {
                    "estado_col": col_name,
                    "examen_col": None,
                    "tema_cols": [],
                    "revisado_col": None,
                },
            )

    for col_name, col_info in columns_info.items():
        if col_info.exam_tag not in exams:
            continue

        if col_info.col_type == ColumnType.EXAMEN:
            exams[col_info.exam_tag]["examen_col"] = col_name
        elif col_info.col_type == ColumnType.TEMA:
            exams[col_info.exam_tag]["tema_cols"].append(col_name)
        elif col_info.col_type == ColumnType.REVISADO:
            exams[col_info.exam_tag]["revisado_col"] = col_name

    for _, exam_data in exams.items():
        exam_data["tema_cols"].sort(key=lambda name: columns_info[name].tema_num or 999)

    return {
        "columns_info": columns_info,
        "exams": exams,
        "text_cols": text_cols,
        "numeric_cols": numeric_cols,
        "boolean_cols": boolean_cols,
        "unknown_cols": unknown_cols,
    }


def load_metadata_for_semester(year: int, term: int, metadata_path=STATISTICS_METADATA_FILE) -> pd.DataFrame:
    sheet_name = f"TPL_{year}_{term}"
    workbook = pd.ExcelFile(metadata_path)
    if sheet_name not in workbook.sheet_names:
        available = ", ".join(workbook.sheet_names)
        raise ValueError(f"No existe metadata para {sheet_name}. Hojas disponibles: {available}")
    return pd.read_excel(metadata_path, sheet_name=sheet_name)


def _build_template_from_metadata(metadata_df: pd.DataFrame) -> tuple[list[str], pd.Series]:
    expected_columns = list(metadata_df.columns)
    if metadata_df.empty:
        raise ValueError("La hoja de metadata no contiene la fila de reglas.")
    return expected_columns, metadata_df.iloc[0].copy()


def _validate_input_header_against_official(file_bytes: bytes, expected_columns: list[str]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    raw_header = pd.read_excel(BytesIO(file_bytes), header=None, nrows=1)
    input_columns = raw_header.iloc[0].tolist()

    expected_len = len(expected_columns)
    input_len = len(input_columns)

    if input_len != expected_len:
        issues.append(
            ValidationIssue(
                "ERROR",
                1,
                None,
                f"Cantidad de columnas incorrecta. Archivo usuario: {input_len}. Plantilla oficial: {expected_len}.",
            )
        )

    max_len = max(expected_len, input_len)
    for index in range(max_len):
        expected = expected_columns[index] if index < expected_len else None
        found = input_columns[index] if index < input_len else None

        if _normalize_header_value(expected) != _normalize_header_value(found):
            issues.append(
                ValidationIssue(
                    "ERROR",
                    1,
                    f"columna_{index + 1}",
                    f"Cabecera incorrecta. Esperado: {expected!r}. Encontrado: {found!r}.",
                )
            )

    return issues


def _load_input_data(file_bytes: bytes, expected_columns: list[str]) -> pd.DataFrame:
    raw = pd.read_excel(BytesIO(file_bytes), header=None)

    if raw.shape[0] < 3:
        raise ValueError(
            "El archivo no tiene suficientes filas. Debe incluir cabecera, metadata y al menos una fila de datos."
        )

    data = raw.iloc[2:].copy().reset_index(drop=True)

    input_col_count = data.shape[1]
    expected_col_count = len(expected_columns)

    if input_col_count != expected_col_count:
        raise ValueError(
            f"Cantidad de columnas incorrecta en los datos. Archivo usuario: {input_col_count}. "
            f"Plantilla oficial: {expected_col_count}."
        )

    data.columns = expected_columns
    return data


def _build_early_result(file_name: str, issues: list[ValidationIssue]) -> FileValidationResult:
    warning_count = sum(issue.level == "WARN" for issue in issues)
    error_count = sum(issue.level == "ERROR" for issue in issues)
    return FileValidationResult(
        file_name=file_name,
        is_valid=False,
        rows_read=0,
        warning_count=warning_count,
        error_count=error_count,
        issues=issues,
        corrected_df=None,
    )


def validate_uploaded_file(file_name: str, file_bytes: bytes, year: int, term: int) -> FileValidationResult:
    metadata_df = load_metadata_for_semester(year, term)
    expected_columns, max_row = _build_template_from_metadata(metadata_df)

    issues: list[ValidationIssue] = []

    header_issues = _validate_input_header_against_official(file_bytes, expected_columns)
    issues.extend(header_issues)

    if any(issue.level == "ERROR" for issue in header_issues):
        return _build_early_result(file_name, issues)

    try:
        df = _load_input_data(file_bytes, expected_columns)
    except Exception as exc:
        issues.append(ValidationIssue("ERROR", None, None, f"No se pudo cargar el archivo de datos: {exc}"))
        return _build_early_result(file_name, issues)

    structure = _discover_structure(expected_columns)
    columns_info = structure["columns_info"]
    exams = structure["exams"]
    text_cols = structure["text_cols"]
    numeric_cols = structure["numeric_cols"]
    boolean_cols = structure["boolean_cols"]
    unknown_cols = structure["unknown_cols"]

    for col in sorted(unknown_cols):
        issues.append(ValidationIssue("WARN", None, col, "Columna no reconocida por el clasificador."))

    mask_all_nan = df.isna().all(axis=1)
    if mask_all_nan.any():
        issues.append(
            ValidationIssue(
                "WARN",
                None,
                None,
                f"Filas totalmente vacías: {int(mask_all_nan.sum())}. Se eliminarán.",
            )
        )
        df = df.loc[~mask_all_nan].reset_index(drop=True)

    for row_index in range(len(df)):
        for col in df.columns:
            if pd.isna(df.at[row_index, col]):
                issues.append(ValidationIssue("ERROR", row_index + 3, col, "Celda vacía"))

    numeric_cols_with_max = [col for col in numeric_cols if col in max_row.index]
    for col in numeric_cols_with_max:
        max_value = max_row[col]
        if isinstance(max_value, (int, float)) and pd.notna(max_value):
            cleaned = df[col].map(_normalize_decimal_commas)
            numeric = pd.to_numeric(cleaned, errors="coerce")

            for row_index in range(len(df)):
                current_value = numeric.iloc[row_index]
                if pd.notna(current_value) and (current_value < 0 or current_value > max_value):
                    issues.append(
                        ValidationIssue(
                            "WARN",
                            row_index + 3,
                            col,
                            f"Valor {df.at[row_index, col]} excede el máximo permitido {max_value}",
                        )
                    )
                elif pd.notna(cleaned.iloc[row_index]) and pd.isna(current_value):
                    issues.append(
                        ValidationIssue(
                            "ERROR",
                            row_index + 3,
                            col,
                            f"Valor no numérico: {df.at[row_index, col]!r}",
                        )
                    )

    for col in numeric_cols:
        if col not in df.columns:
            continue

        if columns_info[col].col_type == ColumnType.SIT:
            extracted = df[col].map(_extract_number_from_text)
            candidate_indexes = np.where(df[col].notna() & extracted.notna())[0]

            for row_index in candidate_indexes:
                original = df.at[row_index, col]
                new_value = extracted.iloc[row_index]
                original_numeric = pd.to_numeric(_normalize_decimal_commas(original), errors="coerce")

                if pd.notna(original_numeric) and np.isclose(original_numeric, new_value, atol=1e-9):
                    continue

                if str(original) != str(new_value):
                    issues.append(
                        ValidationIssue(
                            "WARN",
                            row_index + 3,
                            col,
                            f"SIT: se extrajo número desde texto {original!r} → {new_value}",
                        )
                    )

            bad_mask = df[col].notna() & extracted.isna()
            _report_mask(issues, bad_mask, "ERROR", col, lambda idx: f"Valor no numérico: {df.at[idx, col]!r}")
            df[col] = pd.to_numeric(extracted, errors="coerce")

        else:
            cleaned = df[col].map(_normalize_decimal_commas)
            numeric = pd.to_numeric(cleaned, errors="coerce")
            bad_mask = cleaned.notna() & numeric.isna()
            _report_mask(issues, bad_mask, "ERROR", col, lambda idx: f"Valor no numérico: {df.at[idx, col]!r}")
            df[col] = numeric

    for col in boolean_cols:
        if col not in df.columns:
            continue

        cleaned = df[col].map(_normalize_decimal_commas)
        numeric = pd.to_numeric(cleaned, errors="coerce")
        bad_mask = cleaned.notna() & numeric.isna()
        _report_mask(issues, bad_mask, "ERROR", col, lambda idx: f"Valor no numérico: {df.at[idx, col]!r}")
        df[col] = numeric

    allowed_map = _build_allowed_map(max_row)
    for col, allowed_values in allowed_map.items():
        if col not in df.columns:
            continue

        if col in text_cols:
            series = df[col].astype("string").str.upper().str.strip()
            bad_mask = series.notna() & ~series.isin(list(allowed_values))
            df[col] = series
        else:
            series = df[col]
            bad_mask = series.notna() & ~series.isin(list(allowed_values))

        _report_mask(
            issues,
            bad_mask,
            "ERROR",
            col,
            lambda idx, values=allowed_values: f"Valor inválido {df.at[idx, col]!r}; permitido: {sorted(values)}",
        )

    integer_cols = set(boolean_cols)
    integer_cols.update(
        col
        for col in numeric_cols
        if (
            columns_info.get(col, ColumnInfo("", ColumnType.UNKNOWN)).col_type == ColumnType.REVISADO
            or col in {"PARCIAL", "FINAL", "MEJORAMIENTO", "PRACTICO"}
        )
    )

    for col in integer_cols:
        if col not in df.columns:
            continue

        series = df[col]
        non_integer_mask = series.notna() & (np.abs(series - np.round(series)) > 1e-9)
        _report_mask(
            issues,
            non_integer_mask,
            "WARN",
            col,
            lambda idx: f"Tenía decimales ({df.at[idx, col]}). Se redondeará.",
        )
        df.loc[non_integer_mask, col] = np.round(series[non_integer_mask])

    for col in boolean_cols:
        if col not in df.columns:
            continue

        series = df[col]
        bad_mask = series.notna() & ~series.isin([0, 1])
        _report_mask(issues, bad_mask, "ERROR", col, lambda idx: f"Valor inválido {df.at[idx, col]!r}; debe ser 0 o 1")

    for _, exam_info in exams.items():
        estado_col = exam_info["estado_col"]
        examen_col = exam_info["examen_col"]
        tema_cols = exam_info["tema_cols"]

        if estado_col not in df.columns:
            continue

        for row_index, status_value in df[estado_col].items():
            if pd.isna(status_value):
                issues.append(ValidationIssue("ERROR", row_index + 3, estado_col, "Estado del examen vacío"))
                continue

            try:
                status_value = int(status_value)
            except Exception:
                issues.append(ValidationIssue("ERROR", row_index + 3, estado_col, f"Valor inválido: {status_value!r}"))
                continue

            if status_value in (2, 3):
                if examen_col and examen_col in df.columns:
                    value = df.at[row_index, examen_col]
                    if pd.notna(value) and value != 0:
                        issues.append(
                            ValidationIssue(
                                "ERROR",
                                row_index + 3,
                                examen_col,
                                f"{estado_col}={status_value}. El estado no corresponde a una calificación diferente de cero.",
                            )
                        )

                for tema_col in tema_cols:
                    if tema_col not in df.columns:
                        continue
                    value = df.at[row_index, tema_col]
                    if pd.notna(value) and value != 0:
                        issues.append(
                            ValidationIssue(
                                "ERROR",
                                row_index + 3,
                                tema_col,
                                f"{estado_col}={status_value}. El estado no corresponde a una calificación diferente de cero.",
                            )
                        )

            elif status_value == 1:
                if examen_col and examen_col in df.columns and pd.isna(df.at[row_index, examen_col]):
                    issues.append(
                        ValidationIssue(
                            "ERROR",
                            row_index + 3,
                            examen_col,
                            f"{estado_col}=1 pero falta nota de examen.",
                        )
                    )

                for tema_col in tema_cols:
                    if tema_col not in df.columns:
                        continue
                    if pd.isna(df.at[row_index, tema_col]):
                        issues.append(
                            ValidationIssue(
                                "ERROR",
                                row_index + 3,
                                tema_col,
                                f"{estado_col}=1 pero falta nota del tema.",
                            )
                        )
            else:
                issues.append(ValidationIssue("ERROR", row_index + 3, estado_col, f"Valor inválido: {status_value}"))

    if "ESTADO" in df.columns:
        final_states = df["ESTADO"].astype("string").str.upper().str.strip()
        invalid_state_mask = final_states.notna() & ~final_states.isin(list(VALID_FINAL_STATES))
        _report_mask(
            issues,
            invalid_state_mask,
            "ERROR",
            "ESTADO",
            lambda idx: f"Valor inválido {df.at[idx, 'ESTADO']!r}; permitido: {sorted(VALID_FINAL_STATES)}",
        )
        df["ESTADO"] = final_states

    warning_count = sum(issue.level == "WARN" for issue in issues)
    error_count = sum(issue.level == "ERROR" for issue in issues)
    corrected_df = df if error_count == 0 else None

    return FileValidationResult(
        file_name=file_name,
        is_valid=error_count == 0,
        rows_read=len(df),
        warning_count=warning_count,
        error_count=error_count,
        issues=issues,
        corrected_df=corrected_df,
    )


def validate_uploaded_files(files: list[tuple[str, bytes]], year: int, term: int) -> list[FileValidationResult]:
    return [validate_uploaded_file(file_name, file_bytes, year, term) for file_name, file_bytes in files]