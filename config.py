from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATASETS_PATH = BASE_DIR / "datasets"
METADATA_PATH = BASE_DIR / "metadata"
CAREERS_FILE = METADATA_PATH / "Carreras.xlsx"
STATISTICS_METADATA_FILE = METADATA_PATH / "metadata_estadisticas_FP.xlsx"

VALID_STATES = ("AP", "RP", "RT", "PF")
VALID_TERMS = (0, 1, 2)
MIN_YEAR = 2021
MAX_YEAR = datetime.now().year
DATASET_FILENAME_TEMPLATE = "estadisticas_FP_{year}-{term}.xlsx"
