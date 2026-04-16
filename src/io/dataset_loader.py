from pathlib import Path
import pandas as pd

def list_available_datasets(datasets_path: Path) -> list[str]:
    if not datasets_path.exists():
        return []
    return sorted(file.name for file in datasets_path.glob("*.xlsx"))

def load_dataset(dataset_path: Path) -> pd.DataFrame:
    return pd.read_excel(dataset_path)
