from pathlib import Path
import re
import random
import pandas as pd

# =========================
# CONFIGURACIÓN
# =========================
BASE_DATASETS_DIR = Path(".")
INPUT_DIRS = [
    BASE_DATASETS_DIR / "2025_2T",
    BASE_DATASETS_DIR / "consolidados",
]

# Rango de matrículas ficticias
MATRICULA_MIN = 199500001
MATRICULA_MAX = 199999999

# Porcentaje de muestra aleatorio entre 10% y 40%
MUESTRA_MIN = 0.10
MUESTRA_MAX = 0.40

# Semilla para reproducibilidad
SEED = 42
random.seed(SEED)

# Patron para nombres de carpeta de semestre
SEMESTER_FOLDER_PATTERN = r"^202\d_[12]T$"

# Listas simples para generar nombres inventados
NOMBRES = [
    "Liam","Emma","Noah","Olivia","Mateo","Sofía","Thiago","Valentina","Lucas","Isabella",
    "Daniel","Camila","Samuel","Lucía","Gael","Elena","Adrián","Mia","Julian","Ariana",
    "Nicolás","Renata","Iker","Alma","Bruno","Julia","Leo","Violeta","Dylan","Martina",
    "Sebastián","Paula","Andrés","Clara","Diego","Sara","Tomás","Luna","Emiliano","Victoria",
    "Joaquín","Gabriela","Rodrigo","Daniela","Fernando","Antonia","Álvaro","Carla","Pablo","Elisa",
    "Santiago","María","Iván","Carmen","Hugo","Andrea","Luis","Natalia","Marco","Luciana",
    "Alejandro","Ana","Cristian","Valeria","Eduardo","Rosa","Raúl","Beatriz","Óscar","Silvia",
    "Manuel","Patricia","David","Verónica","Javier","Noelia","Miguel","Rocío","Enrique","Paola",
    "Ricardo","Esther","Arturo","Irene","Guillermo","Marta","Héctor","Alicia","Gerardo","Pilar",
    "Francisco","Teresa","Carlos","Inés","Raquel","Agustín","Lorena","Ezequiel","Nuria","César"
]

APELLIDOS = [
    "Smith","Johnson","Brown","Taylor","Anderson","Clark","Walker","Hall","Young","Allen",
    "King","Wright","Scott","Torres","Rivera","Flores","Mendoza","Castro","Paredes","Salazar",
    "Vega","Ortega","Navarro","Rojas","Molina","Santos","Cruz","Lozano","Herrera","Ibarra",
    "García","Martínez","Rodríguez","López","Hernández","González","Pérez","Sánchez","Ramírez","Torres",
    "Flores","Rivera","Gómez","Díaz","Reyes","Morales","Ortiz","Gutiérrez","Chávez","Ramos",
    "Jiménez","Ruiz","Álvarez","Méndez","Castillo","Silva","Romero","Suárez","Vargas","Delgado",
    "Aguilar","Peña","Guerrero","Valdez","Cabrera","Soto","Vázquez","Rivas","Fuentes","Miranda",
    "Acosta","León","Campos","Cordero","Bravo","Montoya","Escobar","Mejía","Palacios","Zamora",
    "Ponce","Rosales","Benítez","Castañeda","Quintero","Correa","Figueroa","Carrillo","Salinas","Bautista",
    "Mora","Valencia","Lara","Pacheco","Solís","Arroyo","Padilla","Serrano","Velasco","Aguirre"
]


# =========================
# FUNCIONES AUXILIARES
# =========================
def flatten_columns(columns):
    """
    Convierte columnas MultiIndex en texto plano.
    Ejemplo:
    ('DATOS', 'MATRICULA') -> 'DATOS_MATRICULA'
    """
    flat = []
    for col in columns:
        if isinstance(col, tuple):
            parts = [str(x).strip() for x in col if pd.notna(x) and str(x).strip() and "Unnamed" not in str(x)]
            flat.append("_".join(parts) if parts else "COL")
        else:
            flat.append(str(col).strip())
    return flat


def find_column(df, target_name):
    """
    Busca una columna por coincidencia exacta o parcial.
    """
    target = target_name.strip().upper()

    # Coincidencia exacta
    for col in df.columns:
        if str(col).strip().upper() == target:
            return col

    # Coincidencia parcial
    for col in df.columns:
        if target in str(col).strip().upper():
            return col

    return None


def generate_fake_names(n):
    return [f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)}" for _ in range(n)]




# Nuevas funciones auxiliares para matrículas
def build_matricula_pool(size):
    total_posibles = MATRICULA_MAX - MATRICULA_MIN + 1
    if size > total_posibles:
        raise ValueError("El rango de matrículas ficticias no alcanza para generar valores únicos.")
    return iter(random.sample(range(MATRICULA_MIN, MATRICULA_MAX + 1), size))


def normalize_matricula_value(value):
    if pd.isna(value):
        return None

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return str(value).strip()


def assign_fake_matriculas(series, mapping, available_numbers):
    fake_values = []

    for value in series:
        normalized_value = normalize_matricula_value(value)

        if normalized_value is None:
            fake_values.append(value)
            continue

        if normalized_value not in mapping:
            mapping[normalized_value] = next(available_numbers)

        fake_values.append(mapping[normalized_value])

    return fake_values


def is_consolidados_directory(path: Path):
    return path.name.strip().lower() == "consolidados"


def is_semester_directory(path: Path):
    return bool(re.match(SEMESTER_FOLDER_PATTERN, path.name.strip()))


def process_file(file_path, output_dir, matricula_mapping, available_numbers):
    print(f"Procesando: {file_path.name}")

    # Leer Excel usando las 2 primeras filas como cabecera
    df = pd.read_excel(file_path, header=[0, 1])

    # Aplanar cabeceras a una sola fila de nombres de columna
    df.columns = flatten_columns(df.columns)

    # Cargar todo en un DataFrame
    df = df.copy()

    # Buscar columnas objetivo
    col_matricula = find_column(df, "MATRICULA")
    col_nombre = find_column(df, "NOMBRE_ESTUDIANTE")

    if col_matricula is None:
        raise ValueError(f"No se encontró la columna MATRICULA en {file_path.name}")
    if col_nombre is None:
        raise ValueError(f"No se encontró la columna NOMBRE_ESTUDIANTE en {file_path.name}")

    # Escoger porcentaje aleatorio entre 10% y 40%
    frac = random.uniform(MUESTRA_MIN, MUESTRA_MAX)
    n_rows = len(df)

    if n_rows == 0:
        print(f"Archivo vacío: {file_path.name}")
        sampled_df = df.copy()
    else:
        sample_size = max(1, int(n_rows * frac))
        sampled_df = df.sample(n=sample_size, replace=False, random_state=random.randint(1, 10_000)).copy()

    # Reemplazar matrículas preservando consistencia dentro del alcance definido
    sampled_df[col_matricula] = assign_fake_matriculas(
        sampled_df[col_matricula],
        matricula_mapping,
        available_numbers,
    )

    # Reemplazar nombres por nombres inventados
    sampled_df[col_nombre] = generate_fake_names(len(sampled_df))

    # Guardar resultado
    output_path = output_dir / file_path.name
    sampled_df.to_excel(output_path, index=False)

    print(f"Guardado: {output_path} | Filas originales: {n_rows} | Filas muestra: {len(sampled_df)}")




# === Nuevas funciones para procesamiento de directorios múltiples ===
def process_input_directory(input_dir: Path):
    output_dir = input_dir / "anonimos"
    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(
        file_path
        for file_path in input_dir.glob("*.xlsx")
        if file_path.parent != output_dir
    )

    if not files:
        print(f"No se encontraron archivos .xlsx en {input_dir.resolve()}")
        return

    use_shared_semester_mapping = is_semester_directory(input_dir) and not is_consolidados_directory(input_dir)

    shared_mapping = {}
    shared_available_numbers = build_matricula_pool(MATRICULA_MAX - MATRICULA_MIN + 1) if use_shared_semester_mapping else None

    for file_path in files:
        try:
            if use_shared_semester_mapping:
                matricula_mapping = shared_mapping
                available_numbers = shared_available_numbers
            else:
                matricula_mapping = {}
                available_numbers = build_matricula_pool(len(pd.read_excel(file_path, header=[0, 1])))

            process_file(file_path, output_dir, matricula_mapping, available_numbers)
        except Exception as e:
            print(f"Error en {file_path.name}: {e}")


def main():
    for input_dir in INPUT_DIRS:
        if not input_dir.exists():
            print(f"No existe la carpeta: {input_dir.resolve()}")
            continue

        print(f"\nProcesando carpeta: {input_dir.resolve()}")
        process_input_directory(input_dir)

    print("Proceso terminado.")


if __name__ == "__main__":
    main()