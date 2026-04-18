"""Constantes y configuraciones compartidas entre todas las páginas."""

from config import DATASETS_PATH, METADATA_PATH, CAREERS_FILE, STATISTICS_METADATA_FILE

METADATA_SHEET_PREFIX = "TPL_"

# Colores para estados
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

# Colores para componentes teóricos
THEORY_COMPONENT_COLORS = {
    "TOTAL TEORICO": "#F4A261",
    "PARCIAL": "#F7B267",
    "FINAL": "#F79D65",
    "MEJORAMIENTO": "#E76F51",
}

# Colores para componentes prácticos
PRACTICAL_COMPONENT_COLORS = {
    "PRACTICO": "#A8DADC",
    "TALLERES": "#90E0EF",
    "PARTICIPACION": "#BDE0FE",
}

# Colores para totales
TOTALS_COMPONENT_COLORS = {
    "TOTAL TEORICO": "#F4A261",
    "PRACTICO": "#A8DADC",
    "NOTA FINAL": "#CDB4DB",
}

# Colores para temas
TOPIC_COLORS = [
    "#F9C5D1",
    "#F7D6BF",
    "#FAEDCB",
    "#CDEAC0",
    "#BDE0FE",
    "#D7C5F2",
]

# Etiquetas de exámenes
EXAM_LABELS = {
    "1E": "Examen parcial",
    "2E": "Examen final",
    "3E": "Mejoramiento",
}

# Conocimientos válidos
VALID_KNOWLEDGES = {
    "STRINGS",
    "LISTAS",
    "FUNCIONES",
    "IF / FOR",
    "WHILE",
    "TUPLAS",
    "CONJUNTOS",
    "DICCIONARIOS",
    "NUMPY",
    "ARCHIVOS",
    "PANDAS",
    "RANDOM",
    "LOGICA Y DEPURACION",
    "LOGICA",
}

# Correcciones de etiquetas de conocimientos
KNOWLEDGE_LABEL_FIXES = {
    "LOGICA Y DEPURACION": "Lógica",
    "LOGICA": "Lógica",
    "IF / FOR": "If / For",
    "WHILE": "While",
    "STRINGS": "Strings",
    "LISTAS": "Listas",
    "FUNCIONES": "Funciones",
    "TUPLAS": "Tuplas",
    "CONJUNTOS": "Conjuntos",
    "DICCIONARIOS": "Diccionarios",
    "NUMPY": "Numpy",
    "ARCHIVOS": "Archivos",
    "PANDAS": "Pandas",
    "RANDOM": "Random",
}