from datetime import datetime

import streamlit as st

from config import MAX_YEAR, MIN_YEAR, VALID_TERMS
from src.transform.consolidator_service import build_semester_dataset, save_semester_dataset
from src.validation.validator_service import validate_uploaded_file

st.title("Dashboard de Fundamentos de Programación")
st.subheader("Carga de datos (ETL)")

if "validation_summary" not in st.session_state:
    st.session_state.validation_summary = []

if "validation_details" not in st.session_state:
    st.session_state.validation_details = []

if "validated_files_payload" not in st.session_state:
    st.session_state.validated_files_payload = []

if "last_validation_key" not in st.session_state:
    st.session_state.last_validation_key = None


def _current_files_key(uploaded_files: list) -> tuple:
    return tuple((file.name, len(file.getvalue())) for file in uploaded_files)


col_year, col_term = st.columns(2)

with col_year:
    current_year = datetime.now().year
    default_year_index = max(0, min(current_year, MAX_YEAR) - MIN_YEAR)
    year = st.selectbox(
        "Año",
        options=list(range(MIN_YEAR, MAX_YEAR + 1)),
        index=default_year_index,
    )

with col_term:
    term = st.selectbox(
        "Semestre",
        options=list(VALID_TERMS),
        index=1 if 1 in VALID_TERMS else 0,
    )

st.session_state.selected_year = year
st.session_state.selected_term = term

uploaded_files = st.file_uploader(
    "Sube uno o varios archivos Excel del semestre seleccionado",
    type=["xlsx"],
    accept_multiple_files=True,
)

current_files_key = _current_files_key(uploaded_files) if uploaded_files else None
current_validation_key = (year, term, current_files_key)

if st.session_state.last_validation_key != current_validation_key:
    st.session_state.validation_summary = []
    st.session_state.validation_details = []
    st.session_state.validated_files_payload = []
    st.session_state.last_validation_key = current_validation_key

st.subheader("Acciones")
col_validate, col_generate = st.columns(2)

with col_validate:
    validate_clicked = st.button("Validar archivos", use_container_width=True)

if validate_clicked:
    st.session_state.validation_summary = []
    st.session_state.validation_details = []
    st.session_state.validated_files_payload = []

    if not uploaded_files:
        st.warning("Debes subir al menos un archivo para validar.")
    else:
        progress = st.progress(0, text="Iniciando validación...")
        total_files = len(uploaded_files)

        for index, uploaded_file in enumerate(uploaded_files, start=1):
            result = validate_uploaded_file(
                file_name=uploaded_file.name,
                file_bytes=uploaded_file.getvalue(),
                year=year,
                term=term,
            )

            st.session_state.validation_summary.append(
                {
                    "file_name": result.file_name,
                    "is_valid": result.is_valid,
                    "rows_read": result.rows_read,
                    "warning_count": result.warning_count,
                    "error_count": result.error_count,
                    "corrected_df": result.corrected_df,
                }
            )

            st.session_state.validation_details.append(
                {
                    "file_name": result.file_name,
                    "issues": result.issues,
                }
            )

            st.session_state.validated_files_payload.append(
                {
                    "file_name": result.file_name,
                    "is_valid": result.is_valid,
                    "corrected_df": result.corrected_df,
                }
            )

            progress.progress(
                index / total_files,
                text=f"Validando {index}/{total_files}: {uploaded_file.name}",
            )

        progress.progress(1.0, text="Validación finalizada.")

all_valid = bool(st.session_state.validation_summary) and all(
    row["is_valid"] for row in st.session_state.validation_summary
)

with col_generate:
    generate_clicked = st.button(
        "Generar consolidado",
        width='stretch',
        disabled=not all_valid,
    )

st.subheader("Resultado por archivo")

if not st.session_state.validation_summary:
    if not uploaded_files:
        st.info("Todavía no has subido archivos.")
    else:
        pending_rows = [
            {
                "Archivo": file.name,
                "Estado": "Pendiente",
                "Filas leídas": None,
                "Warnings": None,
                "Errores": None,
            }
            for file in uploaded_files
        ]
        st.dataframe(pending_rows, width='stretch', hide_index=True)
else:
    summary_rows = []
    for row in st.session_state.validation_summary:
        summary_rows.append(
            {
                "Archivo": row["file_name"],
                "Estado": "✅ Válido" if row["is_valid"] else "❌ Inválido",
                "Filas leídas": row["rows_read"],
                "Warnings": row["warning_count"],
                "Errores": row["error_count"],
            }
        )

    st.dataframe(summary_rows, width='stretch', hide_index=True)

    valid_count = sum(1 for row in st.session_state.validation_summary if row["is_valid"])
    invalid_count = len(st.session_state.validation_summary) - valid_count

    col_ok, col_bad = st.columns(2)
    col_ok.metric("Archivos válidos", valid_count)
    col_bad.metric("Archivos inválidos", invalid_count)

if generate_clicked:
    try:
        df = build_semester_dataset(
            st.session_state.validation_summary,
            year=year,
            term=term,
        )
        file_path = save_semester_dataset(df, year, term)
        st.session_state.current_dataset_name = file_path.name
        st.success(f"Consolidado generado correctamente: {file_path.name}")
    except Exception as exc:
        st.error(f"Error al generar consolidado: {str(exc)}")

st.subheader("Detalle")

if not st.session_state.validation_details:
    st.caption("Aquí se mostrará el detalle expandible de errores y warnings por archivo.")
else:
    for file_detail in st.session_state.validation_details:
        file_name = file_detail["file_name"]
        issues = file_detail["issues"]

        # with st.expander(f"Detalle: {file_name}"):
        is_valid = next(
            (row["is_valid"] for row in st.session_state.validation_summary if row["file_name"] == file_name),
            False
        )

        icon = "✅" if is_valid else "❌"

        with st.expander(f"{icon} Detalle: {file_name}"):
            if not issues:
                st.success("Sin errores ni warnings.")
            else:
                detail_rows = [issue.to_dict() for issue in issues]
                st.dataframe(detail_rows, width='stretch', hide_index=True)