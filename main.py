from datetime import datetime

import streamlit as st

from config import MAX_YEAR, MIN_YEAR, VALID_TERMS
from src.transform.consolidator_service import build_semester_dataset, save_semester_dataset
from src.validation.validator_service import get_metadata_status, validate_uploaded_file

st.set_page_config(layout="wide", initial_sidebar_state="expanded")

st.title("Dashboard de Fundamentos de Programación")
st.subheader("Carga de datos (ETL)")

st.info("💡 **Consejo para móvil:** El menú de filtros en las otras páginas está en la barra lateral. Si no lo ves, toca el icono >> en la esquina superior izquierda para abrirlo.")


with st.expander("💻 Formato de los archivos Excel", expanded=False):
    st.caption(
    "Puedes descargar archivos Excel de prueba desde "
    "[datasets en GitHub](https://github.com/djurado/fp-history/tree/main/datasets/2025_2T)."
    )
    st.markdown(
    """
 ### Instrucciones para reportar sus estadísticas

- **Descargar plantilla:**  [Excel](https://docs.google.com/spreadsheets/d/1Fj7r2YuKUybM-uRL0_CuamUn2ywQsnm9/edit?usp=share_link&ouid=114490585177627308738&rtpof=true&sd=true)
- **Mantener filas 1 y 2:** no las modifique (encabezado y fila de máximos).  
- **Un archivo por paralelo:** nombre el archivo con `##` como dos dígitos (ej. 02).  
- **No cambie la estructura:** conserve todas las columnas.  
- **Verifique fila 2:** compruebe los puntos máximos y respételos.  
- **Tipo y formato de columnas:**  
  - **`REVISADO X ESTUDIANTE`** y **`TRABAJOS_EXTRA`**: 0=Falso o 1=Verdadero (enteros).  
  - **`PARCIAL`, `FINAL`, `MEJORAMIENTO`, `PRACTICO`**: enteros (sin decimales).  
  - **`TEMA`, `EXAMEN`, `TALLER`, `PARTICIPACION`**: números con hasta 2 decimales máximo (ej. 8.05 o 7.75).  
- **Reglas según `ESTADO` de cada Examen** (entero sin decimales):  
  + 1 = Sí se presentó. El **examen y los temas** pueden tener un valor entre 0 y el máximo definido en la fila 2.
  + 2 = No se presentó. El **examen y los temas** deben tener cero (0).
  + 3 = Medida académica (Ej: copia). El **examen y los temas** deben tener cero (0).
- **Listo para entregar:** verifique que su archivo Excel ha pasado la validación y envíe por correo al coordinador.
    """
    )

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
    year_options = list(range( MAX_YEAR, MIN_YEAR - 1, -1))
    current_year = datetime.now().year

    default_year = st.session_state.get(
        "selected_year",
        max(MIN_YEAR, min(current_year, MAX_YEAR)),
    )

    default_year_index = year_options.index(default_year) if default_year in year_options else 0

    year = st.selectbox(
        "Año",
        options=year_options,
        index=default_year_index,
    )

with col_term:
    term_options = list(VALID_TERMS)

    default_term = st.session_state.get(
        "selected_term",
        1 if 1 in term_options else term_options[0],
    )

    default_term_index = term_options.index(default_term) if default_term in term_options else 0

    term = st.selectbox(
        "Semestre",
        options=term_options,
        index=default_term_index,
    )

st.session_state.selected_year = year
st.session_state.selected_term = term

metadata_available, metadata_message = get_metadata_status(year, term)

if not metadata_available:
    st.warning(metadata_message)

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
    validate_clicked = st.button(
        "Validar archivos",
        use_container_width=True,
        disabled=not metadata_available,
    )

if validate_clicked:
    st.session_state.validation_summary = []
    st.session_state.validation_details = []
    st.session_state.validated_files_payload = []

    if not metadata_available:
        st.error(metadata_message)
    elif not uploaded_files:
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
        disabled=(not metadata_available) or (not all_valid),
    )

if generate_clicked:
    try:
        df = build_semester_dataset(
            st.session_state.validation_summary,
            year=year,
            term=term,
        )
        file_path = save_semester_dataset(df, year, term)
        st.session_state.current_dataset_name = file_path.name
        # Invalidar caché de datos históricos para que Tendencias se actualice
        st.cache_data.clear()
        st.success(f"Consolidado generado correctamente: {file_path.name}")
    except Exception as exc:
        st.error(f"Error al generar consolidado: {str(exc)}")

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

st.subheader("Detalle")

if not st.session_state.validation_details:
    st.caption("Aquí se mostrará el detalle expandible de errores y warnings por archivo.")
else:
    for file_detail in st.session_state.validation_details:
        file_name = file_detail["file_name"]
        issues = file_detail["issues"]

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
