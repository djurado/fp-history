from dataclasses import dataclass, field
from typing import Any
import pandas as pd


@dataclass
class ValidationIssue:
    level: str
    row_excel: int | None
    col: str | None
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "Nivel": self.level,
            "Fila": self.row_excel,
            "Columna": self.col,
            "Descripción": self.message,
        }


@dataclass
class FileValidationResult:
    file_name: str
    is_valid: bool
    rows_read: int
    warning_count: int
    error_count: int
    issues: list[ValidationIssue] = field(default_factory=list)
    corrected_df: pd.DataFrame | None = None

    def summary_row(self) -> dict[str, Any]:
        return {
            "Archivo": self.file_name,
            "Estado": "✅ Válido" if self.is_valid else "❌ Inválido",
            "Filas leídas": self.rows_read,
            "Warnings": self.warning_count,
            "Errores": self.error_count,
        }
